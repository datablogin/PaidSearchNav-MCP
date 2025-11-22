"""Base classes and interfaces for integrations."""

import logging
import time
from abc import ABC, abstractmethod
from collections import deque
from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional, Protocol

logger = logging.getLogger(__name__)


class LeadStage(Enum):
    """Lead stages in the sales funnel."""

    NEW = "new"
    QUALIFIED = "qualified"
    CONTACTED = "contacted"
    PROPOSAL = "proposal"
    NEGOTIATION = "negotiation"
    CLOSED_WON = "closed_won"
    CLOSED_LOST = "closed_lost"


class LeadQuality(Enum):
    """Lead quality categories."""

    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"
    UNQUALIFIED = "unqualified"


@dataclass
class Lead:
    """Represents a lead from a CRM system."""

    id: str
    email: Optional[str]
    phone: Optional[str]
    gclid: Optional[str]  # Google Click ID
    created_at: datetime
    stage: LeadStage
    quality: Optional[LeadQuality] = None
    value: Optional[float] = None
    source: Optional[str] = None
    campaign_id: Optional[str] = None
    ad_group_id: Optional[str] = None
    keyword: Optional[str] = None
    custom_fields: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_fields is None:
            self.custom_fields = {}


@dataclass
class OfflineConversion:
    """Represents an offline conversion event."""

    conversion_id: str
    gclid: str
    conversion_name: str
    conversion_time: datetime
    conversion_value: float
    currency_code: str = "USD"
    lead_id: Optional[str] = None
    order_id: Optional[str] = None
    custom_variables: Dict[str, Any] = None

    def __post_init__(self):
        if self.custom_variables is None:
            self.custom_variables = {}


@dataclass
class CustomerJourney:
    """Tracks the complete customer journey from ad click to conversion."""

    journey_id: str
    gclid: str
    first_touch: datetime
    last_touch: datetime
    touchpoints: List[Dict[str, Any]]
    lead: Optional[Lead] = None
    conversions: List[OfflineConversion] = None
    total_value: float = 0.0
    attribution_model: str = "last_click"

    def __post_init__(self):
        if self.conversions is None:
            self.conversions = []

    def calculate_total_value(self) -> float:
        """Calculate total value from all conversions."""
        return sum(conv.conversion_value for conv in self.conversions)


class RateLimiter:
    """Rate limiter for API calls."""

    def __init__(self, calls_per_second: float = 10.0, calls_per_minute: int = 100):
        self.calls_per_second = calls_per_second
        self.calls_per_minute = calls_per_minute
        self.call_times: deque = deque(maxlen=calls_per_minute)
        self.min_interval = 1.0 / calls_per_second

    def wait_if_needed(self):
        """Wait if necessary to respect rate limits."""
        now = time.time()

        # Check per-second limit
        if self.call_times and (now - self.call_times[-1]) < self.min_interval:
            sleep_time = self.min_interval - (now - self.call_times[-1])
            time.sleep(sleep_time)
            now = time.time()

        # Check per-minute limit
        if len(self.call_times) >= self.calls_per_minute:
            minute_ago = now - 60
            # Remove old entries
            while self.call_times and self.call_times[0] < minute_ago:
                self.call_times.popleft()

            # If still at limit, wait
            if len(self.call_times) >= self.calls_per_minute:
                wait_time = 60 - (now - self.call_times[0]) + 0.1
                time.sleep(wait_time)
                now = time.time()

        self.call_times.append(now)


class CRMConnector(ABC):
    """Abstract base class for CRM platform connectors."""

    def __init__(self, config: Dict[str, Any]):
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")
        # Initialize rate limiter from config or use defaults
        rate_config = config.get("rate_limits", {})
        self.rate_limiter = RateLimiter(
            calls_per_second=rate_config.get("calls_per_second", 10.0),
            calls_per_minute=rate_config.get("calls_per_minute", 100),
        )

    @abstractmethod
    def authenticate(self) -> bool:
        """Authenticate with the CRM platform."""
        pass

    @abstractmethod
    def get_leads(
        self,
        start_date: Optional[datetime] = None,
        end_date: Optional[datetime] = None,
        stage: Optional[LeadStage] = None,
    ) -> List[Lead]:
        """Retrieve leads from the CRM."""
        pass

    @abstractmethod
    def update_lead(self, lead_id: str, updates: Dict[str, Any]) -> bool:
        """Update a lead in the CRM."""
        pass

    @abstractmethod
    def sync_lead_stages(self, leads: List[Lead]) -> Dict[str, bool]:
        """Sync lead stages with the CRM."""
        pass

    @abstractmethod
    def get_custom_fields(self) -> Dict[str, Any]:
        """Get available custom fields from the CRM."""
        pass

    def test_connection(self) -> bool:
        """Test the CRM connection."""
        try:
            return self.authenticate()
        except Exception as e:
            self.logger.error(f"Connection test failed: {e}")
            return False


class OfflineConversionTracker(ABC):
    """Abstract base class for offline conversion tracking."""

    def __init__(self, google_ads_client):
        self.client = google_ads_client
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    @abstractmethod
    def upload_conversions(
        self, conversions: List[OfflineConversion]
    ) -> Dict[str, Any]:
        """Upload offline conversions to Google Ads."""
        pass

    @abstractmethod
    def validate_conversion(self, conversion: OfflineConversion) -> List[str]:
        """Validate an offline conversion before upload."""
        pass

    @abstractmethod
    def get_conversion_actions(self) -> List[Dict[str, Any]]:
        """Get available conversion actions from Google Ads."""
        pass

    def batch_upload(
        self, conversions: List[OfflineConversion], batch_size: int = 200
    ) -> Dict[str, Any]:
        """Upload conversions in batches."""
        results = {
            "successful": 0,
            "failed": 0,
            "errors": [],
            "batches": [],
        }

        for i in range(0, len(conversions), batch_size):
            batch = conversions[i : i + batch_size]
            try:
                batch_result = self.upload_conversions(batch)
                results["batches"].append(batch_result)
                results["successful"] += batch_result.get("successful", 0)
                results["failed"] += batch_result.get("failed", 0)
            except Exception as e:
                self.logger.error(f"Batch upload failed: {e}")
                results["failed"] += len(batch)
                results["errors"].append(str(e))

        return results


class DataSynchronizer(Protocol):
    """Protocol for data synchronization between CRM and Google Ads."""

    def sync_leads_to_conversions(
        self, leads: List[Lead], conversion_action: str
    ) -> Dict[str, Any]:
        """Sync CRM leads to Google Ads offline conversions."""
        ...

    def sync_conversion_values(
        self, customer_journeys: List[CustomerJourney]
    ) -> Dict[str, Any]:
        """Sync conversion values based on customer journeys."""
        ...

    def get_sync_status(self) -> Dict[str, Any]:
        """Get the current synchronization status."""
        ...
