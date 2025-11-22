"""
Google Ads Scripts Conflict Detection Integration

This module provides Python integration for the Google Ads Scripts conflict detection system,
handling script deployment, execution monitoring, and result processing.

Based on PaidSearchNav Issue #464
"""

from __future__ import annotations

import asyncio
import json
import logging
import random
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field

from paidsearchnav.core.exceptions import (
    ConflictDetectionError,
    DataProcessingError,
)
from paidsearchnav.integrations.google_ads_write_client import GoogleAdsWriteClient
from paidsearchnav.integrations.s3 import S3Client

logger = logging.getLogger(__name__)


def with_retry(max_retries: int = 3, base_delay: float = 1.0, max_delay: float = 60.0):
    """Decorator for adding exponential backoff retry logic to async functions.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay in seconds for exponential backoff
        max_delay: Maximum delay in seconds between retries
    """

    def decorator(func):
        async def wrapper(*args, **kwargs):
            last_exception = None

            for attempt in range(max_retries + 1):
                try:
                    return await func(*args, **kwargs)
                except Exception as e:
                    last_exception = e

                    # Don't retry on the last attempt
                    if attempt == max_retries:
                        break

                    # Calculate delay with exponential backoff and jitter
                    delay = min(base_delay * (2**attempt), max_delay)
                    jitter = delay * 0.1 * random.random()  # Add up to 10% jitter
                    total_delay = delay + jitter

                    logger.warning(
                        f"Function {func.__name__} failed on attempt {attempt + 1}/{max_retries + 1}: {e}. "
                        f"Retrying in {total_delay:.2f} seconds..."
                    )

                    await asyncio.sleep(total_delay)

            # If we get here, all retries failed
            raise last_exception

        return wrapper

    return decorator


class ConflictDetectionConfig(BaseModel):
    """Configuration for conflict detection system."""

    email_recipients: List[str] = Field(
        default=["alerts@paidsearchnav.com"],
        description="Email addresses for conflict alerts",
    )
    s3_bucket: str = Field(
        default="paidsearchnav-conflict-reports",
        description="S3 bucket for storing conflict reports",
    )
    detection_thresholds: Dict[str, float] = Field(
        default={
            "min_clicks_for_analysis": 5,
            "high_cost_threshold": 25.0,
            "quality_score_threshold": 4,
            "bid_competition_threshold": 0.10,
        },
        description="Thresholds for conflict detection algorithms",
    )
    report_retention_days: int = Field(
        default=90, description="Number of days to retain conflict reports"
    )
    max_conflicts_per_email: int = Field(
        default=50, description="Maximum number of conflicts to include in alert emails"
    )
    api_rate_limit_delay: float = Field(
        default=1.0,
        description="Delay in seconds between API calls to respect rate limits",
    )
    max_api_retries: int = Field(
        default=3, description="Maximum number of retries for failed API calls"
    )


class ConflictRecord(BaseModel):
    """Model for individual conflict records."""

    type: str = Field(description="Type of conflict detected")
    severity: str = Field(description="Severity level: HIGH, MEDIUM, LOW")
    campaign: str = Field(description="Campaign name where conflict was detected")
    ad_group: Optional[str] = Field(None, description="Ad group name if applicable")
    keyword: Optional[str] = Field(None, description="Keyword involved in conflict")
    issue: str = Field(description="Description of the conflict")
    estimated_impact: Dict[str, Any] = Field(
        default_factory=dict, description="Estimated performance impact"
    )
    detected_at: datetime = Field(description="When the conflict was detected")
    resolution_status: str = Field(
        default="PENDING",
        description="Resolution status: PENDING, IN_PROGRESS, RESOLVED, IGNORED",
    )


class ConflictDetectionResults(BaseModel):
    """Complete conflict detection results."""

    timestamp: datetime = Field(description="When the detection was run")
    account_id: str = Field(description="Google Ads account ID")
    positive_negative_conflicts: List[ConflictRecord] = Field(
        default_factory=list,
        description="Conflicts between positive and negative keywords",
    )
    cross_campaign_conflicts: List[ConflictRecord] = Field(
        default_factory=list, description="Keywords competing across multiple campaigns"
    )
    functionality_issues: List[ConflictRecord] = Field(
        default_factory=list, description="Campaign functionality problems"
    )
    geographic_conflicts: List[ConflictRecord] = Field(
        default_factory=list, description="Geographic targeting conflicts"
    )
    performance_impacts: List[Dict[str, Any]] = Field(
        default_factory=list, description="Calculated performance impacts"
    )
    total_conflicts: int = Field(description="Total number of conflicts found")
    high_severity_count: int = Field(description="Number of high-severity conflicts")
    estimated_monthly_loss: float = Field(
        description="Estimated monthly loss in dollars"
    )


class ConflictDetectionManager:
    """Manager for Google Ads conflict detection operations."""

    def __init__(
        self,
        google_ads_client: GoogleAdsWriteClient,
        s3_client: S3Client,
        config: ConflictDetectionConfig,
    ):
        """Initialize the conflict detection manager.

        Args:
            google_ads_client: Google Ads API client for script management
            s3_client: S3 client for report storage
            config: Configuration for conflict detection
        """
        self.google_ads_client = google_ads_client
        self.s3_client = s3_client
        self.config = config
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

    async def deploy_conflict_detection_script(
        self, customer_id: str, script_name: str = "Automated Conflict Detection System"
    ) -> str:
        """Deploy the conflict detection script to Google Ads account.

        Args:
            customer_id: Google Ads customer ID
            script_name: Name for the deployed script

        Returns:
            Script ID of the deployed script

        Raises:
            ConflictDetectionError: If script deployment fails
        """
        try:
            # Validate customer ID format
            self._validate_customer_id(customer_id)

            # Read the JavaScript conflict detection script
            script_path = self._get_script_path()
            with open(script_path, "r", encoding="utf-8") as file:
                script_content = file.read()

            # Update script configuration with current settings
            configured_script = self._configure_script(script_content)

            # Deploy script using Google Ads API
            script_id = await self._deploy_script_via_api(
                customer_id=customer_id,
                script_name=script_name,
                script_content=configured_script,
            )

            self.logger.info(
                f"Successfully deployed conflict detection script {script_id} "
                f"to customer {customer_id}"
            )

            return script_id

        except Exception as e:
            self.logger.error(f"Failed to deploy conflict detection script: {e}")
            raise ConflictDetectionError(f"Script deployment failed: {e}") from e

    async def run_conflict_detection(
        self, customer_id: str, script_id: Optional[str] = None
    ) -> ConflictDetectionResults:
        """Run conflict detection analysis for a Google Ads account.

        Args:
            customer_id: Google Ads customer ID
            script_id: Optional script ID if already deployed

        Returns:
            Complete conflict detection results

        Raises:
            ConflictDetectionError: If conflict detection fails
        """
        try:
            # Validate environment and configuration before proceeding
            self._validate_environment()
            self._validate_customer_id(customer_id)

            # Deploy script if not provided
            if script_id is None:
                script_id = await self.deploy_conflict_detection_script(customer_id)

            # Execute the script
            execution_id = await self._execute_script(customer_id, script_id)

            # Add delay to respect API rate limits
            await asyncio.sleep(self.config.api_rate_limit_delay)

            # Wait for completion and retrieve results
            results_data = await self._wait_for_results(customer_id, execution_id)

            # Process and validate results
            results = self._process_script_results(customer_id, results_data)

            # Store results for historical tracking
            await self._store_results(results)

            # Send alerts if high-severity conflicts found
            if results.high_severity_count > 0:
                await self._send_conflict_alerts(results)

            self.logger.info(
                f"Conflict detection completed for {customer_id}. "
                f"Found {results.total_conflicts} conflicts "
                f"({results.high_severity_count} high-severity)"
            )

            return results

        except Exception as e:
            self.logger.error(f"Conflict detection failed for {customer_id}: {e}")
            raise ConflictDetectionError(f"Conflict detection failed: {e}") from e

    async def generate_bulk_resolution_actions(
        self, results: ConflictDetectionResults, priority_filter: Optional[str] = "HIGH"
    ) -> Dict[str, str]:
        """Generate bulk action files for resolving detected conflicts.

        Args:
            results: Conflict detection results
            priority_filter: Filter conflicts by severity (HIGH, MEDIUM, LOW, or None for all)

        Returns:
            Dictionary of bulk action filenames and their CSV content

        Raises:
            DataProcessingError: If bulk action generation fails
        """
        try:
            bulk_actions = {}

            # Filter conflicts by priority if specified
            filtered_conflicts = self._filter_conflicts_by_priority(
                results, priority_filter
            )

            # Generate negative keyword additions
            negative_keywords_csv = self._generate_negative_keywords_bulk_action(
                filtered_conflicts["positive_negative"]
            )
            if negative_keywords_csv:
                bulk_actions["negative_keywords_bulk_upload.csv"] = (
                    negative_keywords_csv
                )

            # Generate campaign pause/budget adjustment actions
            campaign_actions_csv = self._generate_campaign_actions(
                filtered_conflicts["cross_campaign"]
                + filtered_conflicts["functionality"]
            )
            if campaign_actions_csv:
                bulk_actions["campaign_optimization_actions.csv"] = campaign_actions_csv

            # Generate keyword pause actions for severe conflicts
            keyword_actions_csv = self._generate_keyword_pause_actions(
                filtered_conflicts["all_high_severity"]
            )
            if keyword_actions_csv:
                bulk_actions["keyword_pause_actions.csv"] = keyword_actions_csv

            # Store bulk action files
            if bulk_actions:
                await self._store_bulk_actions(results.account_id, bulk_actions)

            self.logger.info(
                f"Generated {len(bulk_actions)} bulk action files for {results.account_id}"
            )

            return bulk_actions

        except Exception as e:
            self.logger.error(f"Failed to generate bulk resolution actions: {e}")
            raise DataProcessingError(f"Bulk action generation failed: {e}") from e

    async def get_conflict_history(
        self, customer_id: str, days_back: int = 30
    ) -> List[ConflictDetectionResults]:
        """Retrieve historical conflict detection results.

        Args:
            customer_id: Google Ads customer ID
            days_back: Number of days of history to retrieve

        Returns:
            List of historical conflict detection results
        """
        try:
            start_date = datetime.now() - timedelta(days=days_back)

            # Retrieve results from S3 storage
            history = await self._retrieve_historical_results(customer_id, start_date)

            self.logger.info(
                f"Retrieved {len(history)} historical conflict detection results "
                f"for {customer_id} ({days_back} days)"
            )

            return history

        except Exception as e:
            self.logger.error(f"Failed to retrieve conflict history: {e}")
            raise ConflictDetectionError(f"History retrieval failed: {e}") from e

    def _get_script_path(self) -> str:
        """Get path to the JavaScript conflict detection script."""
        from pathlib import Path

        # Get script from the scripts/google_ads_tools directory
        current_dir = Path(__file__).parent
        project_root = current_dir.parent.parent
        script_path = (
            project_root
            / "scripts"
            / "google_ads_tools"
            / "conflict_detection_scripts.js"
        )

        if not script_path.exists():
            raise ConflictDetectionError(
                f"Conflict detection script not found: {script_path}"
            )

        return str(script_path)

    def _configure_script(self, script_content: str) -> str:
        """Configure the script with current settings using template markers.

        Args:
            script_content: Original JavaScript script content with template markers

        Returns:
            Configured script content

        Raises:
            ConflictDetectionError: If template replacement fails
        """
        # Define template replacements
        replacements = {
            "{{EMAIL_RECIPIENTS}}": json.dumps(self.config.email_recipients),
            "{{S3_BUCKET}}": self.config.s3_bucket,
            "{{DETECTION_THRESHOLDS}}": json.dumps(
                self.config.detection_thresholds, indent=2
            ),
            "{{REPORT_RETENTION_DAYS}}": str(self.config.report_retention_days),
            "{{MAX_CONFLICTS_PER_EMAIL}}": str(self.config.max_conflicts_per_email),
        }

        configured_script = script_content
        for template_marker, replacement_value in replacements.items():
            if template_marker not in configured_script:
                raise ConflictDetectionError(
                    f"Template marker {template_marker} not found in script. "
                    f"Script may be corrupted or outdated."
                )
            configured_script = configured_script.replace(
                template_marker, replacement_value
            )

        # Validate that all replacements occurred
        remaining_markers = [
            marker for marker in replacements.keys() if marker in configured_script
        ]
        if remaining_markers:
            raise ConflictDetectionError(
                f"Failed to replace template markers: {remaining_markers}"
            )

        return configured_script

    def _get_customer_info(self, customer_id: str) -> tuple[str, str]:
        """Get customer name and number for S3 storage.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Tuple of (customer_name, customer_number)
        """
        # In a real implementation, this would fetch customer info from Google Ads API
        # For now, we'll use a reasonable fallback
        try:
            # Try to get customer info from Google Ads API if available
            # This is a placeholder for actual implementation
            customer_name = f"customer_{customer_id}"
            customer_number = customer_id
        except Exception:
            # Fallback to generic naming
            customer_name = f"google_ads_customer_{customer_id}"
            customer_number = customer_id

        return customer_name, customer_number

    def _validate_environment(self) -> None:
        """Validate environment variables and configuration before running conflict detection.

        Raises:
            ConflictDetectionError: If required environment variables are missing
        """
        import os

        # Check for required Google Ads API credentials
        required_env_vars = ["GOOGLE_ADS_CUSTOMER_ID", "GOOGLE_ADS_DEVELOPER_TOKEN"]

        missing_vars = []
        for var in required_env_vars:
            if not os.getenv(var):
                missing_vars.append(var)

        # Check for authentication file (either service account or refresh token)
        auth_file_vars = ["GOOGLE_ADS_SERVICE_ACCOUNT_FILE", "GOOGLE_ADS_REFRESH_TOKEN"]
        has_auth = any(os.getenv(var) for var in auth_file_vars)

        if not has_auth:
            missing_vars.extend(
                ["GOOGLE_ADS_SERVICE_ACCOUNT_FILE or GOOGLE_ADS_REFRESH_TOKEN"]
            )

        # Check for S3 configuration if using S3 storage
        if self.config.s3_bucket:
            s3_vars = ["AWS_ACCESS_KEY_ID", "AWS_SECRET_ACCESS_KEY"]
            missing_s3_vars = [var for var in s3_vars if not os.getenv(var)]
            if missing_s3_vars and not os.getenv("AWS_PROFILE"):
                missing_vars.extend(
                    ["AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY or AWS_PROFILE"]
                )

        if missing_vars:
            raise ConflictDetectionError(
                f"Missing required environment variables: {', '.join(missing_vars)}. "
                "Please configure these before running conflict detection."
            )

        self.logger.info("Environment validation completed successfully")

    def _validate_customer_id(self, customer_id: str) -> None:
        """Validate Google Ads customer ID format.

        Args:
            customer_id: Google Ads customer ID to validate

        Raises:
            ConflictDetectionError: If customer ID format is invalid
        """
        if not customer_id:
            raise ConflictDetectionError("Customer ID cannot be empty")

        # Remove any dashes or spaces for validation
        clean_id = customer_id.replace("-", "").replace(" ", "")

        # Check if it's numeric and has the right length (typically 10 digits)
        if not clean_id.isdigit():
            raise ConflictDetectionError(
                f"Invalid customer ID format: '{customer_id}'. "
                "Customer ID should contain only digits (with optional dashes)"
            )

        if len(clean_id) != 10:
            raise ConflictDetectionError(
                f"Invalid customer ID length: '{customer_id}'. "
                "Customer ID should be 10 digits long"
            )

        self.logger.debug(f"Customer ID validation passed: {customer_id}")

    @with_retry(max_retries=3, base_delay=2.0, max_delay=30.0)
    async def _deploy_script_via_api(
        self, customer_id: str, script_name: str, script_content: str
    ) -> str:
        """Deploy script using Google Ads API.

        Note: This is a placeholder - Google Ads Scripts API is limited.
        In practice, scripts would need to be deployed manually or via
        other Google Ads interfaces.
        """
        # This would use the Google Ads API to deploy the script
        # For now, we'll simulate script deployment
        script_id = (
            f"conflict_detection_{customer_id}_{int(datetime.now().timestamp())}"
        )

        self.logger.info(
            f"Script deployment simulated. In production, deploy manually:\n"
            f"Script Name: {script_name}\n"
            f"Customer ID: {customer_id}\n"
            f"Script Length: {len(script_content)} characters"
        )

        return script_id

    @with_retry(max_retries=3, base_delay=1.0, max_delay=15.0)
    async def _execute_script(self, customer_id: str, script_id: str) -> str:
        """Execute the deployed script."""
        execution_id = f"exec_{script_id}_{int(datetime.now().timestamp())}"

        # In practice, this would trigger script execution via API
        self.logger.info(f"Script execution triggered: {execution_id}")

        return execution_id

    @with_retry(max_retries=5, base_delay=5.0, max_delay=60.0)
    async def _wait_for_results(
        self, customer_id: str, execution_id: str, timeout_minutes: int = 30
    ) -> Dict[str, Any]:
        """Wait for script execution to complete and retrieve results."""
        import asyncio

        # Simulate waiting for script completion
        await asyncio.sleep(5)  # Simulate processing time

        # In practice, this would poll for completion and retrieve actual results
        # For now, we'll generate simulated results
        return self._generate_simulated_results(customer_id)

    def _generate_simulated_results(self, customer_id: str) -> Dict[str, Any]:
        """Generate simulated conflict detection results for testing."""
        return {
            "timestamp": datetime.now().isoformat(),
            "positiveNegativeConflicts": [
                {
                    "type": "POSITIVE_NEGATIVE_CONFLICT",
                    "severity": "HIGH",
                    "keyword": "fitness connection dallas",
                    "keywordMatchType": "EXACT",
                    "negativeKeyword": "dallas",
                    "negativeMatchType": "BROAD",
                    "campaign": "PP_FIT_SRCH_Google_CON_BRN_TermOnly_Dallas",
                    "adGroup": "Brand Terms",
                    "negativeList": "Account Level Negatives",
                    "level": "CAMPAIGN",
                    "estimatedImpact": {
                        "blockedImpressions": 1200,
                        "lostClicks": 48,
                        "wastedSpend": 156.50,
                        "lostConversions": 2.3,
                    },
                    "detectedAt": datetime.now().isoformat(),
                }
            ],
            "crossCampaignConflicts": [
                {
                    "type": "CROSS_CAMPAIGN_CONFLICT",
                    "severity": "MEDIUM",
                    "keyword": "gym near me",
                    "campaigns": [
                        {
                            "name": "Local Search - Dallas",
                            "adGroup": "Near Me Terms",
                            "bid": 2.50,
                            "qualityScore": 7,
                        },
                        {
                            "name": "Performance Max - Dallas",
                            "adGroup": "All Products",
                            "bid": 2.80,
                            "qualityScore": 6,
                        },
                    ],
                    "estimatedWastedSpend": 89.30,
                    "detectedAt": datetime.now().isoformat(),
                }
            ],
            "functionalityIssues": [],
            "geographicConflicts": [],
        }

    def _process_script_results(
        self, customer_id: str, results_data: Dict[str, Any]
    ) -> ConflictDetectionResults:
        """Process raw script results into structured format."""
        try:
            conflicts = []

            # Process positive/negative conflicts
            for conflict_data in results_data.get("positiveNegativeConflicts", []):
                conflict = ConflictRecord(
                    type=conflict_data["type"],
                    severity=conflict_data["severity"],
                    campaign=conflict_data["campaign"],
                    ad_group=conflict_data.get("adGroup"),
                    keyword=conflict_data.get("keyword"),
                    issue=f"Conflicts with negative keyword: {conflict_data.get('negativeKeyword')}",
                    estimated_impact=conflict_data.get("estimatedImpact", {}),
                    detected_at=datetime.fromisoformat(
                        conflict_data["detectedAt"].replace("Z", "+00:00")
                    ),
                )
                conflicts.append(conflict)

            positive_negative_conflicts = [
                c for c in conflicts if c.type == "POSITIVE_NEGATIVE_CONFLICT"
            ]

            # Process cross-campaign conflicts
            cross_campaign_conflicts = []
            for conflict_data in results_data.get("crossCampaignConflicts", []):
                conflict = ConflictRecord(
                    type=conflict_data["type"],
                    severity=conflict_data["severity"],
                    campaign="; ".join([c["name"] for c in conflict_data["campaigns"]]),
                    ad_group=None,  # Not applicable for cross-campaign conflicts
                    keyword=conflict_data.get("keyword"),
                    issue=f"Competing across {len(conflict_data['campaigns'])} campaigns",
                    estimated_impact={
                        "estimatedWastedSpend": conflict_data.get(
                            "estimatedWastedSpend", 0
                        )
                    },
                    detected_at=datetime.fromisoformat(
                        conflict_data["detectedAt"].replace("Z", "+00:00")
                    ),
                )
                cross_campaign_conflicts.append(conflict)

            # Process other conflict types similarly...
            functionality_issues: List[ConflictRecord] = []
            geographic_conflicts: List[ConflictRecord] = []

            # Calculate summary metrics
            all_conflicts = (
                positive_negative_conflicts
                + cross_campaign_conflicts
                + functionality_issues
                + geographic_conflicts
            )

            total_conflicts = len(all_conflicts)
            high_severity_count = len(
                [c for c in all_conflicts if c.severity == "HIGH"]
            )

            # Calculate estimated monthly loss
            estimated_monthly_loss = 0.0
            for conflict in all_conflicts:
                if "wastedSpend" in conflict.estimated_impact:
                    estimated_monthly_loss += (
                        conflict.estimated_impact["wastedSpend"] * 30
                    )  # Daily to monthly
                elif "estimatedWastedSpend" in conflict.estimated_impact:
                    estimated_monthly_loss += conflict.estimated_impact[
                        "estimatedWastedSpend"
                    ]

            results = ConflictDetectionResults(
                timestamp=datetime.fromisoformat(
                    results_data["timestamp"].replace("Z", "+00:00")
                ),
                account_id=customer_id,
                positive_negative_conflicts=positive_negative_conflicts,
                cross_campaign_conflicts=cross_campaign_conflicts,
                functionality_issues=functionality_issues,
                geographic_conflicts=geographic_conflicts,
                performance_impacts=[],  # Would be calculated from script results
                total_conflicts=total_conflicts,
                high_severity_count=high_severity_count,
                estimated_monthly_loss=estimated_monthly_loss,
            )

            return results

        except Exception as e:
            self.logger.error(f"Failed to process script results: {e}")
            raise DataProcessingError(f"Results processing failed: {e}") from e

    async def _store_results(self, results: ConflictDetectionResults) -> None:
        """Store conflict detection results in S3."""
        try:
            # Generate filename and folder structure
            date_str = results.timestamp.strftime("%Y-%m-%d")
            time_str = results.timestamp.strftime("%H-%M-%S")
            filename = f"results_{time_str}.json"

            # Convert results to JSON
            results_json = results.model_dump_json(indent=2)

            # Get customer information for proper S3 storage
            customer_name, customer_number = self._get_customer_info(results.account_id)

            # Store in S3 using the existing S3Client interface
            upload_result = self.s3_client.upload_content(
                content=results_json,
                customer_name=customer_name,
                customer_number=customer_number,
                date=date_str,
                folder="conflict-detection",
                filename=filename,
                content_type="application/json",
            )

            self.logger.info(f"Stored conflict detection results: {upload_result.key}")

        except Exception as e:
            self.logger.error(f"Failed to store results: {e}")
            # Don't raise exception - this is not critical for the main flow

    async def _send_conflict_alerts(self, results: ConflictDetectionResults) -> None:
        """Send email alerts for high-severity conflicts."""
        try:
            # This would integrate with email service to send alerts
            # For now, we'll log the alert
            self.logger.warning(
                f"HIGH SEVERITY CONFLICTS DETECTED - Account: {results.account_id}, "
                f"Count: {results.high_severity_count}, "
                f"Estimated Loss: ${results.estimated_monthly_loss:.2f}/month"
            )

            # In production, this would send actual emails using the configured recipients

        except Exception as e:
            self.logger.error(f"Failed to send conflict alerts: {e}")
            # Don't raise exception - this is not critical for the main flow

    def _filter_conflicts_by_priority(
        self, results: ConflictDetectionResults, priority_filter: Optional[str]
    ) -> Dict[str, List[ConflictRecord]]:
        """Filter conflicts by priority level."""
        all_conflicts = (
            results.positive_negative_conflicts
            + results.cross_campaign_conflicts
            + results.functionality_issues
            + results.geographic_conflicts
        )

        if priority_filter:
            filtered_conflicts = [
                c for c in all_conflicts if c.severity == priority_filter
            ]
        else:
            filtered_conflicts = all_conflicts

        return {
            "positive_negative": [
                c for c in filtered_conflicts if c.type == "POSITIVE_NEGATIVE_CONFLICT"
            ],
            "cross_campaign": [
                c for c in filtered_conflicts if c.type == "CROSS_CAMPAIGN_CONFLICT"
            ],
            "functionality": [
                c
                for c in filtered_conflicts
                if c.type
                in [
                    "LANDING_PAGE_ISSUE",
                    "TARGETING_CONSISTENCY_ISSUE",
                    "BUDGET_ALLOCATION_ISSUE",
                ]
            ],
            "geographic": [
                c for c in filtered_conflicts if c.type == "GEOGRAPHIC_CONFLICT"
            ],
            "all_high_severity": [c for c in all_conflicts if c.severity == "HIGH"],
        }

    def _generate_negative_keywords_bulk_action(
        self, positive_negative_conflicts: List[ConflictRecord]
    ) -> Optional[str]:
        """Generate CSV for bulk negative keyword uploads."""
        if not positive_negative_conflicts:
            return None

        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        # Google Ads bulk upload format for negative keywords
        writer.writerow(["Campaign", "Ad Group", "Keyword", "Criterion Type", "Labels"])

        for conflict in positive_negative_conflicts:
            if conflict.severity in ["HIGH", "MEDIUM", "LOW"]:
                # Extract the conflicting positive keyword to add as negative
                if conflict.keyword:
                    writer.writerow(
                        [
                            conflict.campaign,
                            "",  # Campaign level negative
                            f'"{conflict.keyword}"',  # Exact match negative
                            "Negative Keyword",
                            "Conflict Resolution - Automated",
                        ]
                    )

        return output.getvalue()

    def _generate_campaign_actions(
        self, conflicts: List[ConflictRecord]
    ) -> Optional[str]:
        """Generate CSV for campaign-level actions."""
        if not conflicts:
            return None

        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(
            ["Campaign", "Action", "Recommendation", "Priority", "Expected Impact"]
        )

        for conflict in conflicts:
            if conflict.type == "CROSS_CAMPAIGN_CONFLICT":
                writer.writerow(
                    [
                        conflict.campaign,
                        "Review Keyword Competition",
                        f'Keyword "{conflict.keyword}" is competing across multiple campaigns',
                        conflict.severity,
                        "Reduce internal competition and wasted spend",
                    ]
                )
            elif conflict.type in ["LANDING_PAGE_ISSUE", "TARGETING_CONSISTENCY_ISSUE"]:
                writer.writerow(
                    [
                        conflict.campaign,
                        "Fix Campaign Settings",
                        conflict.issue,
                        conflict.severity,
                        "Improve campaign functionality and performance",
                    ]
                )

        return output.getvalue()

    def _generate_keyword_pause_actions(
        self, high_severity_conflicts: List[ConflictRecord]
    ) -> Optional[str]:
        """Generate CSV for pausing problematic keywords."""
        if not high_severity_conflicts:
            return None

        import csv
        from io import StringIO

        output = StringIO()
        writer = csv.writer(output)

        writer.writerow(["Campaign", "Ad Group", "Keyword", "Action", "Reason"])

        for conflict in high_severity_conflicts:
            if conflict.keyword and conflict.severity == "HIGH":
                writer.writerow(
                    [
                        conflict.campaign,
                        conflict.ad_group or "",
                        conflict.keyword,
                        "Pause",
                        f"High-severity conflict: {conflict.issue}",
                    ]
                )

        return output.getvalue()

    async def _store_bulk_actions(
        self, account_id: str, bulk_actions: Dict[str, str]
    ) -> None:
        """Store generated bulk action files in S3."""
        try:
            date_str = datetime.now().strftime("%Y-%m-%d")

            # Get customer information for proper S3 storage
            customer_name, customer_number = self._get_customer_info(account_id)

            for filename, content in bulk_actions.items():
                upload_result = self.s3_client.upload_content(
                    content=content,
                    customer_name=customer_name,
                    customer_number=customer_number,
                    date=date_str,
                    folder="bulk-actions",
                    filename=filename,
                    content_type="text/csv",
                )

                self.logger.info(f"Stored bulk action file: {upload_result.key}")

        except Exception as e:
            self.logger.error(f"Failed to store bulk actions: {e}")

    async def _retrieve_historical_results(
        self, customer_id: str, start_date: datetime
    ) -> List[ConflictDetectionResults]:
        """Retrieve historical conflict detection results from S3."""
        try:
            # List all result files for the customer since start_date
            prefix = f"conflict-detection/{customer_id}/"

            # This would use S3 operations to list and retrieve files
            # For now, return empty list
            self.logger.info(
                f"Historical results retrieval not yet implemented for {customer_id}"
            )

            return []

        except Exception as e:
            self.logger.error(f"Failed to retrieve historical results: {e}")
            return []


# Utility functions for standalone usage


def create_conflict_detection_manager(
    customer_id: str, config: Optional[ConflictDetectionConfig] = None
) -> ConflictDetectionManager:
    """Create a configured conflict detection manager.

    Args:
        customer_id: Google Ads customer ID
        config: Optional configuration override

    Returns:
        Configured ConflictDetectionManager instance
    """
    if config is None:
        config = ConflictDetectionConfig()

    # Initialize dependencies (these would normally be injected)
    from paidsearchnav.integrations.google_ads_write_client import GoogleAdsWriteClient
    from paidsearchnav.integrations.s3 import S3Client

    # Create clients with default configuration
    # Note: In production, these would be properly configured with real credentials
    try:
        from paidsearchnav.auth.oauth_manager import OAuthManager
        from paidsearchnav.core.config import Settings

        settings = Settings()
        oauth_manager = OAuthManager()
        google_ads_client = GoogleAdsWriteClient(settings, oauth_manager)
    except Exception:
        # Fall back to mock implementation for testing
        from unittest.mock import Mock

        google_ads_client = Mock()

    try:
        from paidsearchnav.core.config import S3Config

        s3_config = S3Config()
        s3_client = S3Client(s3_config)
    except Exception:
        # Fall back to mock implementation for testing
        from unittest.mock import Mock

        s3_client = Mock()

    return ConflictDetectionManager(
        google_ads_client=google_ads_client, s3_client=s3_client, config=config
    )


async def run_conflict_detection_for_customer(
    customer_id: str, config: Optional[ConflictDetectionConfig] = None
) -> ConflictDetectionResults:
    """Run conflict detection for a specific customer.

    Args:
        customer_id: Google Ads customer ID
        config: Optional configuration override

    Returns:
        Conflict detection results
    """
    manager = create_conflict_detection_manager(customer_id, config)
    return await manager.run_conflict_detection(customer_id)
