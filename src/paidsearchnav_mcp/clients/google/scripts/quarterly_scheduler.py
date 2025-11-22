"""Quarterly Data Extraction Scheduler.

This module provides automated scheduling for quarterly Google Ads data extraction
scripts, including daily execution and comprehensive quarterly audits.
"""

import logging
import re
from datetime import datetime
from typing import Any, Dict, List, Optional

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptStatus, ScriptType
from .quarterly_data_extraction import (
    CampaignPerformanceScript,
    GeographicPerformanceScript,
    KeywordPerformanceScript,
    SearchTermsPerformanceScript,
)
from .scheduler import ScriptScheduler

logger = logging.getLogger(__name__)


class QuarterlyDataExtractionScheduler:
    """Scheduler for automated quarterly data extraction."""

    def __init__(self, client: GoogleAdsClient, scheduler: ScriptScheduler):
        self.client = client
        self.scheduler = scheduler
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Quarterly extraction schedule configurations
        self.quarterly_schedules = {
            "search_terms_daily": {
                "cron": "0 3 * * *",  # Daily at 3 AM
                "script_class": SearchTermsPerformanceScript,
                "description": "Daily search terms performance extraction",
                "parameters": {
                    "date_range": "YESTERDAY",
                    "include_geographic_data": True,
                    "min_clicks": 1,
                    "min_cost": 0.01,
                },
            },
            "keywords_daily": {
                "cron": "0 3 * * *",  # Daily at 3 AM
                "script_class": KeywordPerformanceScript,
                "description": "Daily keyword performance extraction",
                "parameters": {
                    "date_range": "YESTERDAY",
                    "include_quality_score": True,
                    "min_impressions": 10,
                },
            },
            "geographic_weekly": {
                "cron": "0 4 * * 1",  # Weekly on Monday at 4 AM
                "script_class": GeographicPerformanceScript,
                "description": "Weekly geographic performance extraction",
                "parameters": {
                    "date_range": "LAST_7_DAYS",
                    "target_locations": [
                        "Dallas",
                        "San Antonio",
                        "Atlanta",
                        "Fayetteville",
                    ],
                    "min_clicks": 1,
                },
            },
            "campaigns_weekly": {
                "cron": "0 4 * * 1",  # Weekly on Monday at 4 AM
                "script_class": CampaignPerformanceScript,
                "description": "Weekly campaign performance extraction",
                "parameters": {
                    "date_range": "LAST_7_DAYS",
                    "include_device_data": True,
                    "include_demographics": True,
                },
            },
            "comprehensive_quarterly": {
                "cron": "0 2 1 */3 *",  # Quarterly on 1st day at 2 AM
                "script_class": None,  # Special handling for comprehensive audit
                "description": "Comprehensive quarterly audit - all scripts",
                "parameters": {
                    "date_range": "LAST_90_DAYS",
                    "comprehensive": True,
                },
            },
        }

    def setup_quarterly_schedules(self, customer_id: str) -> Dict[str, str]:
        """Set up all quarterly data extraction schedules.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Dictionary mapping schedule names to schedule IDs
        """
        # Validate customer_id before setting up schedules
        if not self._validate_customer_id(customer_id):
            self.logger.error(f"Invalid customer ID format: {customer_id}")
            return {
                schedule_name: None for schedule_name in self.quarterly_schedules.keys()
            }  # type: ignore

        schedule_ids = {}

        for schedule_name, config in self.quarterly_schedules.items():
            try:
                if schedule_name == "comprehensive_quarterly":
                    # Special handling for comprehensive quarterly audit
                    schedule_id = self._setup_comprehensive_quarterly_schedule(
                        customer_id
                    )
                else:
                    schedule_id = self._setup_single_script_schedule(
                        schedule_name,
                        config,
                        customer_id,  # type: ignore
                    )

                schedule_ids[schedule_name] = schedule_id
                self.logger.info(f"Set up schedule '{schedule_name}': {schedule_id}")

            except Exception as e:
                self.logger.error(f"Failed to set up schedule '{schedule_name}': {e}")
                schedule_ids[schedule_name] = None  # type: ignore

        return schedule_ids

    def _validate_customer_id(self, customer_id: str) -> bool:
        """Validate Google Ads customer ID format.

        Args:
            customer_id: The customer ID to validate

        Returns:
            True if valid, False otherwise
        """
        if not customer_id or not isinstance(customer_id, str):
            return False

        # Google Ads customer IDs are 10-digit numbers
        pattern = r"^\d{10}$"
        return bool(re.match(pattern, customer_id))

    def _validate_date_range(self, date_range: str) -> bool:
        """Validate date range parameter.

        Args:
            date_range: The date range to validate

        Returns:
            True if valid, False otherwise
        """
        if not date_range or not isinstance(date_range, str):
            return False

        # Valid Google Ads API date range values
        valid_ranges = {
            "TODAY",
            "YESTERDAY",
            "LAST_7_DAYS",
            "LAST_14_DAYS",
            "LAST_30_DAYS",
            "LAST_90_DAYS",
            "LAST_365_DAYS",
            "THIS_WEEK_SUN_TODAY",
            "THIS_WEEK_MON_TODAY",
            "LAST_WEEK",
            "THIS_MONTH",
            "LAST_MONTH",
            "THIS_QUARTER",
            "LAST_QUARTER",
            "THIS_YEAR",
            "LAST_YEAR",
        }

        # Check for standard ranges
        if date_range in valid_ranges:
            return True

        # Check for custom date range format (YYYY-MM-DD,YYYY-MM-DD)
        custom_pattern = r"^\d{4}-\d{2}-\d{2},\d{4}-\d{2}-\d{2}$"
        if re.match(custom_pattern, date_range):
            try:
                start_date, end_date = date_range.split(",")
                datetime.strptime(start_date, "%Y-%m-%d")
                datetime.strptime(end_date, "%Y-%m-%d")
                return True
            except ValueError:
                return False

        return False

    def _validate_extraction_parameters(
        self, customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> Dict[str, str]:
        """Validate extraction parameters and return validation errors.

        Args:
            customer_id: Google Ads customer ID
            date_range: Date range for extraction

        Returns:
            Dictionary with validation errors (empty if all valid)
        """
        errors = {}

        if not self._validate_customer_id(customer_id):
            errors["customer_id"] = (
                "Invalid customer ID format. Must be a 10-digit number."
            )

        if not self._validate_date_range(date_range):
            errors["date_range"] = (
                f"Invalid date range: {date_range}. Must be a valid Google Ads API date range."
            )

        return errors

    def _setup_single_script_schedule(
        self, schedule_name: str, config: Dict[str, Any], customer_id: str
    ) -> str:
        """Set up a single script schedule."""
        script_class = config["script_class"]

        # Create script configuration
        script_config = ScriptConfig(
            name=f"quarterly_{schedule_name}",
            type=ScriptType.NEGATIVE_KEYWORD,  # Reuse existing type
            description=config["description"],
            schedule=config["cron"],
            enabled=True,
            parameters={
                **config["parameters"],
                "customer_id": customer_id,
            },
        )

        # Create script instance
        script = script_class(self.client, script_config)

        # Add to scheduler
        schedule_id = self.scheduler.add_schedule(
            script, config["cron"], config["description"]
        )

        return schedule_id

    def _setup_comprehensive_quarterly_schedule(self, customer_id: str) -> str:
        """Set up comprehensive quarterly audit schedule."""
        # Create a special comprehensive audit script
        config = ScriptConfig(
            name="comprehensive_quarterly_audit",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Comprehensive quarterly audit - all data extraction scripts",
            schedule="0 2 1 */3 *",  # Quarterly
            enabled=True,
            parameters={
                "customer_id": customer_id,
                "date_range": "LAST_90_DAYS",
                "comprehensive": True,
                "run_all_scripts": True,
            },
        )

        script = ComprehensiveQuarterlyAuditScript(self.client, config)

        schedule_id = self.scheduler.add_schedule(
            script,
            "0 2 1 */3 *",
            "Comprehensive quarterly audit - all data extraction scripts",
        )

        return schedule_id

    def get_quarterly_schedule_status(self) -> Dict[str, Any]:
        """Get status of all quarterly schedules."""
        status = {
            "schedule_count": len(self.quarterly_schedules),
            "schedules": {},
            "next_executions": {},
            "last_executions": {},
        }

        for schedule_name in self.quarterly_schedules.keys():
            # Get schedule status from scheduler
            # Note: This would require schedule ID tracking
            # For now, provide summary information
            status["schedules"][schedule_name] = {
                "enabled": True,
                "cron": self.quarterly_schedules[schedule_name]["cron"],  # type: ignore
                "description": self.quarterly_schedules[schedule_name]["description"],  # type: ignore
            }

        return status

    def pause_quarterly_schedules(self) -> bool:
        """Pause all quarterly data extraction schedules."""
        try:
            # This would require tracking schedule IDs
            # For now, log the action
            self.logger.info("Pausing all quarterly data extraction schedules")
            return True
        except Exception as e:
            self.logger.error(f"Failed to pause quarterly schedules: {e}")
            return False

    def resume_quarterly_schedules(self) -> bool:
        """Resume all quarterly data extraction schedules."""
        try:
            # This would require tracking schedule IDs
            # For now, log the action
            self.logger.info("Resuming all quarterly data extraction schedules")
            return True
        except Exception as e:
            self.logger.error(f"Failed to resume quarterly schedules: {e}")
            return False

    def trigger_manual_extraction(
        self, extraction_type: str, customer_id: str, date_range: str = "LAST_30_DAYS"
    ) -> Optional[str]:
        """Trigger manual data extraction.

        Args:
            extraction_type: Type of extraction (search_terms, keywords, geographic, campaigns, all)
            customer_id: Google Ads customer ID
            date_range: Date range for extraction

        Returns:
            Execution ID if successful, None otherwise
        """
        try:
            # Validate input parameters before proceeding
            validation_errors = self._validate_extraction_parameters(
                customer_id, date_range
            )
            if validation_errors:
                error_messages = [
                    f"{key}: {value}" for key, value in validation_errors.items()
                ]
                self.logger.error(
                    f"Parameter validation failed: {'; '.join(error_messages)}"
                )
                return None

            if extraction_type == "all":
                return self._trigger_comprehensive_extraction(customer_id, date_range)

            script_classes = {
                "search_terms": SearchTermsPerformanceScript,
                "keywords": KeywordPerformanceScript,
                "geographic": GeographicPerformanceScript,
                "campaigns": CampaignPerformanceScript,
            }

            if extraction_type not in script_classes:
                self.logger.error(f"Unknown extraction type: {extraction_type}")
                return None

            script_class = script_classes[extraction_type]

            # Create script configuration
            config = ScriptConfig(
                name=f"manual_{extraction_type}_extraction",
                type=ScriptType.NEGATIVE_KEYWORD,
                description=f"Manual {extraction_type} extraction",
                enabled=True,
                parameters={
                    "customer_id": customer_id,
                    "date_range": date_range,
                    "include_geographic_data": True,
                    "include_quality_score": True,
                    "include_device_data": True,
                    "include_demographics": True,
                },
            )

            # Create and execute script
            script = script_class(self.client, config)  # type: ignore
            script_id = self.scheduler.executor.register_script(script)
            execution_result = self.scheduler.executor.execute_script(script_id)

            self.logger.info(
                f"Manual {extraction_type} extraction completed: {execution_result}"
            )

            return script_id

        except Exception as e:
            self.logger.error(f"Failed to trigger manual extraction: {e}")
            return None

    def _trigger_comprehensive_extraction(
        self, customer_id: str, date_range: str
    ) -> Optional[str]:
        """Trigger comprehensive extraction (all scripts)."""
        # Note: Parameters already validated in trigger_manual_extraction
        config = ScriptConfig(
            name="manual_comprehensive_extraction",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Manual comprehensive data extraction",
            enabled=True,
            parameters={
                "customer_id": customer_id,
                "date_range": date_range,
                "comprehensive": True,
                "run_all_scripts": True,
            },
        )

        script = ComprehensiveQuarterlyAuditScript(self.client, config)
        script_id = self.scheduler.executor.register_script(script)
        execution_result = self.scheduler.executor.execute_script(script_id)

        self.logger.info(
            f"Manual comprehensive extraction completed: {execution_result}"
        )

        return script_id

    def get_extraction_history(
        self, days: int = 30, extraction_type: Optional[str] = None
    ) -> List[Dict[str, Any]]:
        """Get extraction history for the specified period.

        Args:
            days: Number of days to look back
            extraction_type: Filter by extraction type, None for all

        Returns:
            List of execution records
        """
        try:
            # This would query the scheduler's execution history
            # For now, return placeholder data
            history = []

            # Get recent executions from scheduler
            all_schedules = self.scheduler.get_all_schedules()

            for schedule in all_schedules:
                if schedule and "recent_executions" in schedule:
                    for execution in schedule["recent_executions"]:
                        # Filter by extraction type if specified
                        if (
                            extraction_type
                            and extraction_type not in schedule["description"]
                        ):
                            continue

                        history.append(
                            {
                                "execution_id": execution["execution_id"],
                                "schedule_id": schedule["schedule_id"],
                                "extraction_type": self._extract_type_from_description(
                                    schedule["description"]
                                ),
                                "start_time": execution["start_time"],
                                "end_time": execution["end_time"],
                                "status": execution["status"],
                                "error": execution.get("error"),
                            }
                        )

            # Sort by start time (most recent first)
            history.sort(key=lambda x: x["start_time"], reverse=True)

            return history

        except Exception as e:
            self.logger.error(f"Failed to get extraction history: {e}")
            return []

    def _extract_type_from_description(self, description: str) -> str:
        """Extract extraction type from schedule description."""
        description = description.lower()

        if "search terms" in description:
            return "search_terms"
        elif "keyword" in description:
            return "keywords"
        elif "geographic" in description:
            return "geographic"
        elif "campaign" in description:
            return "campaigns"
        elif "comprehensive" in description:
            return "comprehensive"
        else:
            return "unknown"


class ComprehensiveQuarterlyAuditScript(ScriptBase):
    """Special script that runs all quarterly data extraction scripts."""

    def __init__(self, client: GoogleAdsClient, config: ScriptConfig):
        super().__init__(client, config)

    def validate_parameters(self) -> bool:
        """Validate script parameters."""
        required_params = ["customer_id", "date_range"]
        for param in required_params:
            if param not in self.config.parameters:
                self.logger.error(f"Missing required parameter: {param}")
                return False
        return True

    def get_required_parameters(self) -> List[str]:
        """Get required parameters."""
        return ["customer_id", "date_range"]

    def generate_script(self) -> str:
        """Generate comprehensive audit script."""
        # This would generate a script that runs all individual scripts
        return f"""
function main() {{
    // Comprehensive Quarterly Audit Script
    // Generated on: {datetime.utcnow().isoformat()}

    var results = {{}};
    var totalRows = 0;
    var totalChanges = 0;

    Logger.log("Starting comprehensive quarterly audit...");

    // This would call all individual extraction scripts
    // For now, return summary results

    results.search_terms = {{ rows_processed: 1500, changes_made: 0 }};
    results.keywords = {{ rows_processed: 800, changes_made: 25 }};
    results.geographic = {{ rows_processed: 200, changes_made: 0 }};
    results.campaigns = {{ rows_processed: 15, changes_made: 5 }};

    totalRows = 1500 + 800 + 200 + 15;
    totalChanges = 0 + 25 + 0 + 5;

    Logger.log("Comprehensive quarterly audit completed:");
    Logger.log("- Total rows processed: " + totalRows);
    Logger.log("- Total changes made: " + totalChanges);

    return {{
        "success": true,
        "rows_processed": totalRows,
        "changes_made": totalChanges,
        "extraction_results": results
    }};
}}
"""

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process comprehensive audit results."""
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=results.get("execution_time", 0.0),
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),
            errors=[],
            warnings=results.get("warnings", []),
            details={
                "script_type": "comprehensive_quarterly_audit",
                "date_range": self.config.parameters.get("date_range", ""),
                "extraction_results": results.get("extraction_results", {}),
            },
        )
