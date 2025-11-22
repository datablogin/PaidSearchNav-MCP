"""Automated data synchronization between CRM and Google Ads."""

import asyncio
import logging
from dataclasses import dataclass
from datetime import datetime, timedelta
from enum import Enum
from typing import Any, Dict, List, Optional

from paidsearchnav.scheduler.interfaces import JobContext, JobResult, JobStatus

from .base import CRMConnector, Lead, LeadStage, OfflineConversion
from .journey_tracking import CustomerJourneyTracker, Touchpoint, TouchpointType
from .lead_scoring import LeadQualityScorer, ScoringFeatures
from .offline_conversions import EnhancedConversionsTracker, GCLIDTracker

logger = logging.getLogger(__name__)


class SyncStatus(Enum):
    """Synchronization status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    PARTIAL_SUCCESS = "partial_success"


class SyncDirection(Enum):
    """Direction of data synchronization."""

    CRM_TO_GOOGLE = "crm_to_google"
    GOOGLE_TO_CRM = "google_to_crm"
    BIDIRECTIONAL = "bidirectional"


@dataclass
class SyncConfig:
    """Configuration for data synchronization."""

    # Sync settings
    direction: SyncDirection = SyncDirection.BIDIRECTIONAL
    sync_interval_minutes: int = 30
    batch_size: int = 100
    retry_attempts: int = 3
    retry_delay_seconds: int = 60

    # Data settings
    sync_leads: bool = True
    sync_conversions: bool = True
    sync_lead_scores: bool = True
    sync_journey_data: bool = True

    # Time windows
    lead_lookback_days: int = 7
    conversion_window_days: int = 90

    # Field mappings
    field_mappings: Dict[str, str] = None

    def __post_init__(self):
        if self.field_mappings is None:
            self.field_mappings = {}


@dataclass
class SyncResult:
    """Result of a synchronization operation."""

    sync_id: str
    status: SyncStatus
    start_time: datetime
    end_time: Optional[datetime]
    direction: SyncDirection

    # Counts
    leads_synced: int = 0
    conversions_synced: int = 0
    scores_updated: int = 0
    journeys_updated: int = 0

    # Errors
    errors: List[str] = None
    failed_items: List[Dict[str, Any]] = None

    def __post_init__(self):
        if self.errors is None:
            self.errors = []
        if self.failed_items is None:
            self.failed_items = []


class DataSynchronizer:
    """Orchestrates data synchronization between CRM and Google Ads."""

    def __init__(
        self,
        crm_connector: CRMConnector,
        conversion_tracker: EnhancedConversionsTracker,
        journey_tracker: CustomerJourneyTracker,
        lead_scorer: LeadQualityScorer,
        gclid_tracker: GCLIDTracker,
        config: SyncConfig,
    ):
        self.crm = crm_connector
        self.conversion_tracker = conversion_tracker
        self.journey_tracker = journey_tracker
        self.lead_scorer = lead_scorer
        self.gclid_tracker = gclid_tracker
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        self._sync_lock = asyncio.Lock()
        self._last_sync: Optional[datetime] = None

    async def sync_all(self) -> SyncResult:
        """Perform full synchronization based on configuration.

        Returns:
            SyncResult with details of the sync operation
        """
        sync_id = f"sync_{datetime.utcnow().timestamp()}"
        result = SyncResult(
            sync_id=sync_id,
            status=SyncStatus.IN_PROGRESS,
            start_time=datetime.utcnow(),
            end_time=None,
            direction=self.config.direction,
        )

        async with self._sync_lock:
            try:
                self.logger.info(f"Starting synchronization {sync_id}")

                # Sync based on direction
                if self.config.direction == SyncDirection.CRM_TO_GOOGLE:
                    await self._sync_crm_to_google(result)
                elif self.config.direction == SyncDirection.GOOGLE_TO_CRM:
                    await self._sync_google_to_crm(result)
                else:  # BIDIRECTIONAL
                    await self._sync_crm_to_google(result)
                    await self._sync_google_to_crm(result)

                # Update sync metadata if enabled
                if self.config.sync_journey_data:
                    await self._sync_journey_data(result)

                # Determine final status
                if result.errors:
                    result.status = (
                        SyncStatus.PARTIAL_SUCCESS
                        if result.leads_synced > 0 or result.conversions_synced > 0
                        else SyncStatus.FAILED
                    )
                else:
                    result.status = SyncStatus.COMPLETED

                result.end_time = datetime.utcnow()
                self._last_sync = result.end_time

                self.logger.info(
                    f"Sync {sync_id} completed with status {result.status.value}"
                )

            except Exception as e:
                self.logger.error(f"Sync {sync_id} failed: {e}")
                result.status = SyncStatus.FAILED
                result.errors.append(str(e))
                result.end_time = datetime.utcnow()

        return result

    async def _sync_crm_to_google(self, result: SyncResult):
        """Sync data from CRM to Google Ads."""
        try:
            # Get recent leads from CRM
            if self.config.sync_leads:
                start_date = datetime.utcnow() - timedelta(
                    days=self.config.lead_lookback_days
                )
                leads = self.crm.get_leads(start_date=start_date)

                self.logger.info(f"Found {len(leads)} leads to process")

                # Process leads in batches
                for i in range(0, len(leads), self.config.batch_size):
                    batch = leads[i : i + self.config.batch_size]
                    await self._process_lead_batch(batch, result)

            # Sync conversions
            if self.config.sync_conversions:
                await self._sync_conversions_to_google(result)

        except Exception as e:
            self.logger.error(f"Error syncing CRM to Google: {e}")
            result.errors.append(f"CRM to Google sync error: {str(e)}")

    async def _sync_google_to_crm(self, result: SyncResult):
        """Sync data from Google Ads to CRM."""
        try:
            # This would typically:
            # 1. Get recent conversions from Google Ads
            # 2. Match them with CRM leads
            # 3. Update lead stages and values in CRM

            # For now, placeholder implementation
            self.logger.info("Google to CRM sync not fully implemented yet")

        except Exception as e:
            self.logger.error(f"Error syncing Google to CRM: {e}")
            result.errors.append(f"Google to CRM sync error: {str(e)}")

    async def _process_lead_batch(self, leads: List[Lead], result: SyncResult) -> None:
        """Process a batch of leads for synchronization."""
        conversions_to_upload = []

        for lead in leads:
            try:
                # Skip if no GCLID
                if not lead.gclid:
                    continue

                # Score lead if enabled
                if self.config.sync_lead_scores and not lead.quality:
                    features = await self._extract_scoring_features(lead)
                    quality, score, _ = self.lead_scorer.score_lead(lead, features)
                    lead.quality = quality

                    # Update lead in CRM with quality score
                    self.crm.update_lead(
                        lead.id, {"lead_quality": quality.value, "lead_score": score}
                    )
                    result.scores_updated += 1

                # Check if lead should be converted
                if self._should_create_conversion(lead):
                    conversion = self._create_offline_conversion(lead)
                    conversions_to_upload.append(conversion)

                result.leads_synced += 1

            except Exception as e:
                self.logger.error(f"Error processing lead {lead.id}: {e}")
                result.failed_items.append(
                    {"type": "lead", "id": lead.id, "error": str(e)}
                )

        # Upload conversions in batch
        if conversions_to_upload:
            upload_result = self.conversion_tracker.upload_conversions(
                conversions_to_upload
            )
            result.conversions_synced += upload_result.get("successful", 0)

            if upload_result.get("errors"):
                result.errors.extend(upload_result["errors"])

    async def _sync_conversions_to_google(self, result: SyncResult):
        """Sync offline conversions to Google Ads."""
        try:
            # Get leads that have converted offline
            converted_leads = self.crm.get_leads(stage=LeadStage.CLOSED_WON)

            conversions = []
            for lead in converted_leads:
                if lead.gclid and lead.value:
                    # Check if already synced
                    if not self._is_conversion_synced(lead):
                        conversion = self._create_offline_conversion(lead)
                        conversions.append(conversion)

            if conversions:
                # Upload in batches
                for i in range(0, len(conversions), self.config.batch_size):
                    batch = conversions[i : i + self.config.batch_size]
                    upload_result = self.conversion_tracker.upload_conversions(batch)
                    result.conversions_synced += upload_result.get("successful", 0)

                    if upload_result.get("errors"):
                        result.errors.extend(upload_result["errors"])

        except Exception as e:
            self.logger.error(f"Error syncing conversions: {e}")
            result.errors.append(f"Conversion sync error: {str(e)}")

    async def _sync_journey_data(self, result: SyncResult):
        """Sync customer journey data."""
        try:
            # Get leads with journey data
            recent_leads = self.crm.get_leads(
                start_date=datetime.utcnow() - timedelta(days=7)
            )

            for lead in recent_leads:
                if not lead.gclid:
                    continue

                # Find or create journey
                journey = self.journey_tracker.find_journey_by_gclid(lead.gclid)

                if not journey:
                    # Create journey from lead data
                    first_touchpoint = Touchpoint(
                        touchpoint_id=f"tp_{lead.id}",
                        timestamp=lead.created_at,
                        type=TouchpointType.FORM_SUBMISSION,
                        channel=lead.source or "unknown",
                        campaign_id=lead.campaign_id,
                        keyword=lead.keyword,
                    )
                    journey = self.journey_tracker.create_journey(
                        lead.gclid, first_touchpoint
                    )

                # Update journey with lead info
                if journey:
                    journey.lead = lead
                    result.journeys_updated += 1

        except Exception as e:
            self.logger.error(f"Error syncing journey data: {e}")
            result.errors.append(f"Journey sync error: {str(e)}")

    async def _extract_scoring_features(self, lead: Lead) -> ScoringFeatures:
        """Extract features for lead scoring."""
        # This would typically gather data from various sources
        # For now, return basic features
        features = ScoringFeatures(
            time_to_conversion=(
                (datetime.utcnow() - lead.created_at).total_seconds() / 3600
                if lead.created_at
                else None
            ),
            campaign_cpc=lead.custom_fields.get("cpc", 5.0),
        )

        return features

    def _should_create_conversion(self, lead: Lead) -> bool:
        """Determine if a lead should create an offline conversion."""
        # Business logic to determine if lead represents a conversion
        return lead.stage in [
            LeadStage.CLOSED_WON,
            LeadStage.PROPOSAL,
            LeadStage.NEGOTIATION,
        ]

    def _create_offline_conversion(self, lead: Lead) -> OfflineConversion:
        """Create an offline conversion from a lead."""
        conversion_name = "offline_lead_conversion"
        if lead.stage == LeadStage.CLOSED_WON:
            conversion_name = "offline_sale"

        return OfflineConversion(
            conversion_id=f"conv_{lead.id}",
            gclid=lead.gclid,
            conversion_name=conversion_name,
            conversion_time=lead.created_at,
            conversion_value=lead.value or 0.0,
            currency_code="USD",
            lead_id=lead.id,
        )

    def _is_conversion_synced(self, lead: Lead) -> bool:
        """Check if a lead's conversion has already been synced."""
        # This would check a tracking database or custom field
        return lead.custom_fields.get("conversion_synced", False)

    async def schedule_sync(self) -> None:
        """Run synchronization on a schedule."""
        while True:
            try:
                # Wait for next sync interval
                await asyncio.sleep(self.config.sync_interval_minutes * 60)

                # Check if sync is needed
                if self._should_sync():
                    result = await self.sync_all()
                    self.logger.info(
                        f"Scheduled sync completed: {result.leads_synced} leads, "
                        f"{result.conversions_synced} conversions synced"
                    )

            except asyncio.CancelledError:
                break
            except Exception as e:
                self.logger.error(f"Error in scheduled sync: {e}")

    def _should_sync(self) -> bool:
        """Determine if sync should run."""
        if not self._last_sync:
            return True

        time_since_last = datetime.utcnow() - self._last_sync
        return time_since_last.total_seconds() >= (
            self.config.sync_interval_minutes * 60
        )

    def get_sync_status(self) -> Dict[str, Any]:
        """Get current synchronization status."""
        return {
            "last_sync": self._last_sync.isoformat() if self._last_sync else None,
            "sync_interval_minutes": self.config.sync_interval_minutes,
            "next_sync": (
                (
                    self._last_sync
                    + timedelta(minutes=self.config.sync_interval_minutes)
                ).isoformat()
                if self._last_sync
                else None
            ),
            "config": {
                "direction": self.config.direction.value,
                "sync_leads": self.config.sync_leads,
                "sync_conversions": self.config.sync_conversions,
                "batch_size": self.config.batch_size,
            },
        }


class SyncJob:
    """Scheduler job for automated synchronization."""

    def __init__(self, synchronizer: DataSynchronizer):
        self.synchronizer = synchronizer
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def execute(self, context: JobContext) -> JobResult:
        """Execute synchronization job."""
        try:
            self.logger.info(f"Starting sync job {context.job_id}")

            result = await self.synchronizer.sync_all()

            return JobResult(
                job_id=context.job_id,
                status=JobStatus.COMPLETED,
                message=f"Synced {result.leads_synced} leads, {result.conversions_synced} conversions",
                data={
                    "sync_id": result.sync_id,
                    "leads_synced": result.leads_synced,
                    "conversions_synced": result.conversions_synced,
                    "errors": result.errors,
                },
            )

        except Exception as e:
            self.logger.error(f"Sync job {context.job_id} failed: {e}")
            return JobResult(
                job_id=context.job_id,
                status=JobStatus.FAILED,
                message=str(e),
                error=str(e),
            )
