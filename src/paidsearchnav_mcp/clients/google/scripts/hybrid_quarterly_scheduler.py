"""Enhanced Quarterly Data Extraction Scheduler with Hybrid Output Support.

This module extends the quarterly scheduler to support both CSV and BigQuery outputs
based on customer tier configuration and feature flags.
"""

import logging
from typing import Any, Dict, List, Optional

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.client import GoogleAdsClient

from .base import ScriptBase, ScriptConfig, ScriptResult, ScriptType
from .hybrid_quarterly_extraction import HybridQuarterlyDataExtractionScript
from .quarterly_scheduler import (
    QuarterlyDataExtractionScheduler,
)
from .scheduler import ScriptScheduler

logger = logging.getLogger(__name__)


class HybridQuarterlyDataExtractionScheduler(QuarterlyDataExtractionScheduler):
    """Enhanced scheduler supporting hybrid CSV + BigQuery extraction modes."""

    def __init__(
        self,
        client: GoogleAdsClient,
        scheduler: ScriptScheduler,
        settings: Optional[Settings] = None,
    ):
        super().__init__(client, scheduler)
        self.settings = settings
        self.logger = logging.getLogger(f"{__name__}.{self.__class__.__name__}")

        # Enhanced quarterly extraction schedule configurations with hybrid support
        self.hybrid_quarterly_schedules = {
            "search_terms_daily_hybrid": {
                "cron": "0 3 * * *",  # Daily at 3 AM
                "script_class": HybridQuarterlyDataExtractionScript,
                "description": "Daily hybrid search terms performance extraction (CSV + BigQuery)",
                "parameters": {
                    "date_range": "YESTERDAY",
                    "include_geographic_data": True,
                    "min_clicks": 1,
                    "min_cost": 0.01,
                    "extraction_type": "search_terms",
                    "output_mode": "auto",  # auto, csv, bigquery, both
                    "include_bigquery": True,
                },
                "tier_requirements": ["premium", "enterprise"],
            },
            "keywords_daily_hybrid": {
                "cron": "0 3 15 * *",  # Monthly on 15th at 3 AM
                "script_class": HybridQuarterlyDataExtractionScript,
                "description": "Monthly hybrid keyword performance extraction (CSV + BigQuery)",
                "parameters": {
                    "date_range": "LAST_30_DAYS",
                    "include_quality_score": True,
                    "min_impressions": 10,
                    "extraction_type": "keywords",
                    "output_mode": "auto",
                    "include_bigquery": True,
                },
                "tier_requirements": ["premium", "enterprise"],
            },
            "geographic_weekly_hybrid": {
                "cron": "0 4 * * 1",  # Weekly on Monday at 4 AM
                "script_class": HybridQuarterlyDataExtractionScript,
                "description": "Weekly hybrid geographic performance extraction (CSV + BigQuery)",
                "parameters": {
                    "date_range": "LAST_7_DAYS",
                    "target_locations": [
                        "Dallas",
                        "San Antonio",
                        "Atlanta",
                        "Fayetteville",
                    ],
                    "min_clicks": 1,
                    "extraction_type": "geographic",
                    "output_mode": "auto",
                    "include_bigquery": True,
                },
                "tier_requirements": ["premium", "enterprise"],
            },
            "campaigns_weekly_hybrid": {
                "cron": "0 4 * * 1",  # Weekly on Monday at 4 AM
                "script_class": HybridQuarterlyDataExtractionScript,
                "description": "Weekly hybrid campaign performance extraction (CSV + BigQuery)",
                "parameters": {
                    "date_range": "LAST_7_DAYS",
                    "include_device_data": True,
                    "include_demographics": True,
                    "extraction_type": "campaigns",
                    "output_mode": "auto",
                    "include_bigquery": True,
                },
                "tier_requirements": ["premium", "enterprise"],
            },
            "comprehensive_quarterly_hybrid": {
                "cron": "0 2 1 */3 *",  # Quarterly on 1st day at 2 AM
                "script_class": HybridQuarterlyDataExtractionScript,
                "description": "Comprehensive quarterly hybrid audit - all extraction types (CSV + BigQuery)",
                "parameters": {
                    "date_range": "LAST_90_DAYS",
                    "comprehensive": True,
                    "extraction_type": "all",
                    "output_mode": "both",  # Always generate both for quarterly audits
                    "include_bigquery": True,
                    "include_geographic_data": True,
                    "include_quality_score": True,
                    "include_device_data": True,
                    "include_demographics": True,
                },
                "tier_requirements": [
                    "standard",
                    "premium",
                    "enterprise",
                ],  # Available to all tiers
            },
        }

        # Merge with standard schedules for backward compatibility
        self.all_schedules = {
            **self.quarterly_schedules,
            **self.hybrid_quarterly_schedules,
        }

    def get_customer_tier(self, customer_id: str) -> str:
        """Get customer tier for schedule determination.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Customer tier (standard, premium, enterprise)
        """
        # This would be replaced with actual customer tier lookup
        # For now, use a simple mapping
        tier_map = {
            "1234567890": "premium",
            "0987654321": "enterprise",
        }
        return tier_map.get(customer_id, "standard")

    def is_bigquery_enabled(self) -> bool:
        """Check if BigQuery is enabled in settings.

        Returns:
            True if BigQuery is enabled and properly configured
        """
        if not self.settings or not self.settings.bigquery:
            return False

        return (
            self.settings.bigquery.enabled
            and self.settings.bigquery.tier.value != "disabled"
            and bool(self.settings.bigquery.project_id)
        )

    def setup_hybrid_quarterly_schedules(self, customer_id: str) -> Dict[str, str]:
        """Set up hybrid quarterly data extraction schedules based on customer tier.

        Args:
            customer_id: Google Ads customer ID

        Returns:
            Dictionary mapping schedule names to schedule IDs
        """
        # Validate customer_id
        if not self._validate_customer_id(customer_id):
            self.logger.error(f"Invalid customer ID format: {customer_id}")
            return {
                schedule_name: None
                for schedule_name in self.hybrid_quarterly_schedules.keys()
            }

        customer_tier = self.get_customer_tier(customer_id)
        bigquery_enabled = self.is_bigquery_enabled()

        self.logger.info(
            f"Setting up hybrid schedules for customer {customer_id} "
            f"(tier: {customer_tier}, BigQuery: {bigquery_enabled})"
        )

        schedule_ids = {}

        for schedule_name, config in self.hybrid_quarterly_schedules.items():
            try:
                # Check tier requirements
                tier_requirements = config.get("tier_requirements", ["standard"])
                if customer_tier not in tier_requirements:
                    self.logger.info(
                        f"Skipping schedule '{schedule_name}' - customer tier '{customer_tier}' "
                        f"not in requirements {tier_requirements}"
                    )
                    schedule_ids[schedule_name] = None
                    continue

                # Set up the schedule
                if schedule_name == "comprehensive_quarterly_hybrid":
                    schedule_id = self._setup_comprehensive_hybrid_schedule(
                        customer_id, config
                    )
                else:
                    schedule_id = self._setup_single_hybrid_script_schedule(
                        schedule_name, config, customer_id
                    )

                schedule_ids[schedule_name] = schedule_id
                self.logger.info(
                    f"Set up hybrid schedule '{schedule_name}': {schedule_id}"
                )

            except Exception as e:
                self.logger.error(
                    f"Failed to set up hybrid schedule '{schedule_name}': {e}"
                )
                schedule_ids[schedule_name] = None

        return schedule_ids

    def _setup_single_hybrid_script_schedule(
        self, schedule_name: str, config: Dict[str, Any], customer_id: str
    ) -> str:
        """Set up a single hybrid script schedule.

        Args:
            schedule_name: Name of the schedule
            config: Schedule configuration
            customer_id: Google Ads customer ID

        Returns:
            Schedule ID
        """
        script_class = config["script_class"]

        # Determine output mode based on customer tier and BigQuery availability
        customer_tier = self.get_customer_tier(customer_id)
        bigquery_enabled = self.is_bigquery_enabled()

        # Adjust parameters based on customer tier
        parameters = config["parameters"].copy()
        parameters["customer_id"] = customer_id

        # Set BigQuery inclusion based on tier and availability
        if customer_tier == "standard" or not bigquery_enabled:
            parameters["include_bigquery"] = False
            parameters["output_mode"] = "csv"
        else:
            parameters["include_bigquery"] = True
            # Keep the configured output_mode for premium/enterprise

        # Create script configuration
        script_config = ScriptConfig(
            name=f"hybrid_{schedule_name}",
            type=ScriptType.NEGATIVE_KEYWORD,  # Reuse existing type
            description=config["description"],
            schedule=config["cron"],
            enabled=True,
            parameters=parameters,
        )

        # Create script instance with settings
        if script_class == HybridQuarterlyDataExtractionScript:
            script = script_class(self.client, script_config, self.settings)
        else:
            script = script_class(self.client, script_config)

        # Add to scheduler
        schedule_id = self.scheduler.add_schedule(
            script, config["cron"], config["description"]
        )

        return schedule_id

    def _setup_comprehensive_hybrid_schedule(
        self, customer_id: str, config: Dict[str, Any]
    ) -> str:
        """Set up comprehensive hybrid quarterly audit schedule.

        Args:
            customer_id: Google Ads customer ID
            config: Schedule configuration

        Returns:
            Schedule ID
        """
        customer_tier = self.get_customer_tier(customer_id)
        bigquery_enabled = self.is_bigquery_enabled()

        # Adjust parameters for comprehensive audit
        parameters = config["parameters"].copy()
        parameters["customer_id"] = customer_id

        # For comprehensive audits, always generate CSV for backward compatibility
        # Add BigQuery for premium/enterprise tiers if available
        if customer_tier == "standard" or not bigquery_enabled:
            parameters["output_mode"] = "csv"
            parameters["include_bigquery"] = False
        else:
            parameters["output_mode"] = "both"  # Generate both CSV and BigQuery
            parameters["include_bigquery"] = True

        # Create script configuration
        script_config = ScriptConfig(
            name="comprehensive_hybrid_quarterly_audit",
            type=ScriptType.NEGATIVE_KEYWORD,
            description=config["description"],
            schedule=config["cron"],
            enabled=True,
            parameters=parameters,
        )

        # Create hybrid comprehensive audit script
        script = ComprehensiveHybridQuarterlyAuditScript(
            self.client, script_config, self.settings
        )

        schedule_id = self.scheduler.add_schedule(
            script,
            config["cron"],
            config["description"],
        )

        return schedule_id

    def trigger_manual_hybrid_extraction(
        self,
        extraction_type: str,
        customer_id: str,
        date_range: str = "LAST_30_DAYS",
        output_mode: str = "auto",
    ) -> Optional[str]:
        """Trigger manual hybrid data extraction.

        Args:
            extraction_type: Type of extraction (search_terms, keywords, geographic, campaigns, all)
            customer_id: Google Ads customer ID
            date_range: Date range for extraction
            output_mode: Output mode (auto, csv, bigquery, both)

        Returns:
            Execution ID if successful, None otherwise
        """
        try:
            # Validate input parameters
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

            customer_tier = self.get_customer_tier(customer_id)
            bigquery_enabled = self.is_bigquery_enabled()

            # Adjust output mode based on customer tier
            if customer_tier == "standard" or not bigquery_enabled:
                if output_mode in ["bigquery", "both"]:
                    self.logger.warning(
                        f"BigQuery not available for customer {customer_id} (tier: {customer_tier}), "
                        f"falling back to CSV"
                    )
                    output_mode = "csv"

            # Create script configuration
            parameters = {
                "customer_id": customer_id,
                "date_range": date_range,
                "extraction_type": extraction_type,
                "output_mode": output_mode,
                "include_bigquery": bigquery_enabled
                and customer_tier in ["premium", "enterprise"],
                "include_geographic_data": True,
                "include_quality_score": True,
                "include_device_data": True,
                "include_demographics": True,
            }

            config = ScriptConfig(
                name=f"manual_hybrid_{extraction_type}_extraction",
                type=ScriptType.NEGATIVE_KEYWORD,
                description=f"Manual hybrid {extraction_type} extraction",
                enabled=True,
                parameters=parameters,
            )

            # Create and execute script
            script = HybridQuarterlyDataExtractionScript(
                self.client, config, self.settings
            )
            script_id = self.scheduler.executor.register_script(script)
            execution_result = self.scheduler.executor.execute_script(script_id)

            self.logger.info(
                f"Manual hybrid {extraction_type} extraction completed for customer {customer_id}: "
                f"{execution_result}"
            )

            return script_id

        except Exception as e:
            self.logger.error(f"Failed to trigger manual hybrid extraction: {e}")
            return None

    def get_hybrid_schedule_status(self) -> Dict[str, Any]:
        """Get status of all hybrid schedules.

        Returns:
            Status information for hybrid schedules
        """
        status = {
            "hybrid_schedule_count": len(self.hybrid_quarterly_schedules),
            "bigquery_enabled": self.is_bigquery_enabled(),
            "hybrid_schedules": {},
            "standard_schedules": {},
            "next_executions": {},
            "last_executions": {},
        }

        # Get hybrid schedule status
        for schedule_name in self.hybrid_quarterly_schedules.keys():
            config = self.hybrid_quarterly_schedules[schedule_name]
            status["hybrid_schedules"][schedule_name] = {
                "enabled": True,
                "cron": config["cron"],
                "description": config["description"],
                "tier_requirements": config.get("tier_requirements", ["standard"]),
                "extraction_type": config["parameters"].get(
                    "extraction_type", "unknown"
                ),
            }

        # Get standard schedule status for comparison
        for schedule_name in self.quarterly_schedules.keys():
            config = self.quarterly_schedules[schedule_name]
            status["standard_schedules"][schedule_name] = {
                "enabled": True,
                "cron": config["cron"],
                "description": config["description"],
            }

        return status


class ComprehensiveHybridQuarterlyAuditScript(ScriptBase):
    """Special script that runs comprehensive hybrid quarterly audit with all extraction types."""

    def __init__(
        self,
        client: GoogleAdsClient,
        config: ScriptConfig,
        settings: Optional[Settings] = None,
    ):
        super().__init__(client, config)
        self.settings = settings

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
        """Generate comprehensive hybrid audit script."""
        # Create an instance of the hybrid extraction script
        hybrid_script = HybridQuarterlyDataExtractionScript(
            self.client, self.config, self.settings
        )

        # Generate the hybrid script with comprehensive parameters
        return hybrid_script.generate_script()

    def process_results(self, results: Dict[str, Any]) -> ScriptResult:
        """Process comprehensive hybrid audit results."""
        # Use the hybrid script's result processing
        hybrid_script = HybridQuarterlyDataExtractionScript(
            self.client, self.config, self.settings
        )

        script_result = hybrid_script.process_results(results)

        # Update details to indicate this was a comprehensive audit
        if script_result.details:
            script_result.details["script_type"] = (
                "comprehensive_hybrid_quarterly_audit"
            )
            script_result.details["is_comprehensive"] = True

        return script_result
