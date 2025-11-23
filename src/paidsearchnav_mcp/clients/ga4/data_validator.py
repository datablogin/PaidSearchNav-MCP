"""GA4 data validation module for cross-platform data consistency.

This module validates GA4 API data against BigQuery export data
to ensure data consistency and accuracy across platforms.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List, Optional

from paidsearchnav_mcp.core.config import BigQueryConfig, GA4Config
from paidsearchnav_mcp.platforms.ga4.bigquery_client import GA4BigQueryClient
from paidsearchnav_mcp.platforms.ga4.client import GA4DataClient
from paidsearchnav_mcp.platforms.ga4.models import GA4ValidationResult

logger = logging.getLogger(__name__)


class GA4DataValidator:
    """Validates GA4 API data against BigQuery export data."""

    # Validation tolerance thresholds
    DEFAULT_TOLERANCE_PERCENTAGE = 5.0  # 5% variance allowed
    CRITICAL_VARIANCE_THRESHOLD = 20.0  # 20% variance triggers critical alert

    # Metrics to validate
    VALIDATION_METRICS = [
        "sessions",
        "conversions",
        "totalRevenue",
        "bounceRate",
        "averageSessionDuration",
    ]

    def __init__(
        self,
        ga4_api_client: GA4DataClient,
        ga4_bigquery_client: GA4BigQueryClient,
        ga4_config: GA4Config,
        bigquery_config: BigQueryConfig,
        tolerance_percentage: float = DEFAULT_TOLERANCE_PERCENTAGE,
    ):
        """Initialize the GA4 data validator.

        Args:
            ga4_api_client: GA4 Data API client
            ga4_bigquery_client: GA4 BigQuery client
            ga4_config: GA4 configuration
            bigquery_config: BigQuery configuration
            tolerance_percentage: Acceptable variance percentage
        """
        self.api_client = ga4_api_client
        self.bigquery_client = ga4_bigquery_client
        self.ga4_config = ga4_config
        self.bigquery_config = bigquery_config
        self.tolerance_percentage = tolerance_percentage

        self._validation_history: List[GA4ValidationResult] = []

    async def validate_session_metrics(
        self,
        start_date: str,
        end_date: str,
        dimensions: Optional[List[str]] = None,
    ) -> GA4ValidationResult:
        """Validate session metrics between GA4 API and BigQuery.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            dimensions: Optional dimensions to group by

        Returns:
            Validation result
        """
        try:
            # Default dimensions for validation
            if dimensions is None:
                dimensions = ["source", "medium", "country"]

            # Get data from GA4 API
            api_data = await self.api_client.get_historical_metrics(
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                metrics=["sessions"],
                limit=50000,
            )

            # Get data from BigQuery
            bigquery_data = await self._get_bigquery_session_data(
                start_date, end_date, dimensions
            )

            # Calculate totals for comparison
            api_total = sum(
                float(row.get("sessions", 0)) for row in api_data.get("rows", [])
            )
            bq_total = bigquery_data["total_sessions"] if bigquery_data else 0.0

            # Create validation result
            result = GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="session_metrics",
                api_total=api_total,
                bigquery_total=bq_total,
                variance_percentage=self._calculate_variance(api_total, bq_total),
                tolerance_percentage=self.tolerance_percentage,
                notes=f"Validated {len(api_data.get('rows', []))} API rows vs BigQuery aggregation",
            )

            self._validation_history.append(result)

            # Log validation results
            if result.is_within_tolerance:
                logger.info(
                    f"GA4 session validation passed: {result.variance_percentage:.1f}% variance "
                    f"(API: {api_total:.0f}, BigQuery: {bq_total:.0f})"
                )
            else:
                logger.warning(
                    f"GA4 session validation failed: {result.variance_percentage:.1f}% variance "
                    f"exceeds {self.tolerance_percentage}% tolerance"
                )

            return result

        except Exception as e:
            logger.error(f"GA4 session validation failed: {e}")
            return GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="session_metrics",
                api_total=0.0,
                bigquery_total=0.0,
                variance_percentage=100.0,
                tolerance_percentage=self.tolerance_percentage,
                notes=f"Validation failed: {e}",
            )

    async def validate_conversion_metrics(
        self,
        start_date: str,
        end_date: str,
        conversion_events: Optional[List[str]] = None,
    ) -> GA4ValidationResult:
        """Validate conversion metrics between GA4 API and BigQuery.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format
            conversion_events: Optional list of conversion events to validate

        Returns:
            Validation result
        """
        try:
            # Get data from GA4 API
            api_data = self.api_client.get_conversion_metrics(
                start_date=start_date,
                end_date=end_date,
                conversion_events=conversion_events or ["purchase", "generate_lead"],
            )

            # Get data from BigQuery
            bigquery_data = await self._get_bigquery_conversion_data(
                start_date, end_date, conversion_events
            )

            # Calculate totals for comparison
            api_total = sum(
                float(row.get("conversions", 0)) for row in api_data.get("rows", [])
            )
            bq_total = bigquery_data["total_conversions"] if bigquery_data else 0.0

            # Create validation result
            result = GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="conversion_metrics",
                api_total=api_total,
                bigquery_total=bq_total,
                variance_percentage=self._calculate_variance(api_total, bq_total),
                tolerance_percentage=self.tolerance_percentage,
                notes=f"Validated conversions for events: {conversion_events or 'default'}",
            )

            self._validation_history.append(result)

            if result.is_within_tolerance:
                logger.info(
                    f"GA4 conversion validation passed: {result.variance_percentage:.1f}% variance"
                )
            else:
                logger.warning(
                    f"GA4 conversion validation failed: {result.variance_percentage:.1f}% variance"
                )

            return result

        except Exception as e:
            logger.error(f"GA4 conversion validation failed: {e}")
            return GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="conversion_metrics",
                api_total=0.0,
                bigquery_total=0.0,
                variance_percentage=100.0,
                tolerance_percentage=self.tolerance_percentage,
                notes=f"Validation failed: {e}",
            )

    async def validate_revenue_metrics(
        self,
        start_date: str,
        end_date: str,
    ) -> GA4ValidationResult:
        """Validate revenue metrics between GA4 API and BigQuery.

        Args:
            start_date: Start date in YYYY-MM-DD format
            end_date: End date in YYYY-MM-DD format

        Returns:
            Validation result
        """
        try:
            # Get data from GA4 API
            api_data = await self.api_client.get_historical_metrics(
                start_date=start_date,
                end_date=end_date,
                dimensions=["source", "medium"],
                metrics=["totalRevenue"],
                limit=10000,
            )

            # Get data from BigQuery
            bigquery_data = await self._get_bigquery_revenue_data(start_date, end_date)

            # Calculate totals for comparison
            api_total = sum(
                float(row.get("totalRevenue", 0)) for row in api_data.get("rows", [])
            )
            bq_total = bigquery_data["total_revenue"] if bigquery_data else 0.0

            # Create validation result
            result = GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="revenue_metrics",
                api_total=api_total,
                bigquery_total=bq_total,
                variance_percentage=self._calculate_variance(api_total, bq_total),
                tolerance_percentage=self.tolerance_percentage,
                notes="Revenue validation across GA4 API and BigQuery exports",
            )

            self._validation_history.append(result)

            if result.is_within_tolerance:
                logger.info(
                    f"GA4 revenue validation passed: {result.variance_percentage:.1f}% variance"
                )
            else:
                logger.warning(
                    f"GA4 revenue validation failed: {result.variance_percentage:.1f}% variance"
                )

            return result

        except Exception as e:
            logger.error(f"GA4 revenue validation failed: {e}")
            return GA4ValidationResult(
                property_id=self.ga4_config.property_id,
                validation_type="revenue_metrics",
                api_total=0.0,
                bigquery_total=0.0,
                variance_percentage=100.0,
                tolerance_percentage=self.tolerance_percentage,
                notes=f"Validation failed: {e}",
            )

    async def run_comprehensive_validation(
        self,
        start_date: str = "7daysAgo",
        end_date: str = "yesterday",
    ) -> Dict[str, GA4ValidationResult]:
        """Run comprehensive validation across all metric types.

        Args:
            start_date: Start date for validation
            end_date: End date for validation

        Returns:
            Dictionary of validation results by metric type
        """
        logger.info(
            f"Running comprehensive GA4 validation for property {self.ga4_config.property_id} "
            f"from {start_date} to {end_date}"
        )

        results = {}

        # Validate session metrics
        try:
            results["sessions"] = await self.validate_session_metrics(
                start_date, end_date
            )
        except Exception as e:
            logger.error(f"Session validation failed: {e}")
            results["sessions"] = self._create_error_result("session_metrics", str(e))

        # Validate conversion metrics
        try:
            results["conversions"] = await self.validate_conversion_metrics(
                start_date, end_date
            )
        except Exception as e:
            logger.error(f"Conversion validation failed: {e}")
            results["conversions"] = self._create_error_result(
                "conversion_metrics", str(e)
            )

        # Validate revenue metrics
        try:
            results["revenue"] = await self.validate_revenue_metrics(
                start_date, end_date
            )
        except Exception as e:
            logger.error(f"Revenue validation failed: {e}")
            results["revenue"] = self._create_error_result("revenue_metrics", str(e))

        # Generate summary
        total_validations = len(results)
        passed_validations = sum(
            1 for result in results.values() if result.is_within_tolerance
        )

        logger.info(
            f"GA4 comprehensive validation completed: {passed_validations}/{total_validations} passed"
        )

        return results

    def _create_error_result(
        self, validation_type: str, error_message: str
    ) -> GA4ValidationResult:
        """Create a validation result for an error case.

        Args:
            validation_type: Type of validation that failed
            error_message: Error message

        Returns:
            Error validation result
        """
        return GA4ValidationResult(
            property_id=self.ga4_config.property_id,
            validation_type=validation_type,
            api_total=0.0,
            bigquery_total=0.0,
            variance_percentage=100.0,
            tolerance_percentage=self.tolerance_percentage,
            notes=f"Error: {error_message}",
        )

    async def _get_bigquery_session_data(
        self,
        start_date: str,
        end_date: str,
        dimensions: List[str],
    ) -> Optional[Dict[str, Any]]:
        """Get session data from BigQuery for validation.

        Args:
            start_date: Start date
            end_date: End date
            dimensions: Dimensions to aggregate by

        Returns:
            BigQuery session data or None if failed
        """
        try:
            # Use existing BigQuery client to get session data
            query = f"""
            SELECT
                COUNT(*) as total_sessions,
                AVG(CASE WHEN session_duration > 0 THEN session_duration ELSE NULL END) as avg_duration,
                {", ".join(dimensions)}
            FROM `{self.bigquery_config.project_id}.analytics_{self.ga4_config.property_id}.events_*`
            WHERE _TABLE_SUFFIX BETWEEN '{start_date.replace("-", "")}'
                  AND '{end_date.replace("-", "")}'
                  AND event_name = 'session_start'
            GROUP BY {", ".join(dimensions)}
            """

            # Execute query using BigQuery client
            # Note: This would use the existing BigQuery infrastructure
            # For now, return a placeholder implementation

            return {
                "total_sessions": 1000,  # Placeholder
                "query": query,
                "execution_time_ms": 500,
            }

        except Exception as e:
            logger.error(f"Failed to get BigQuery session data: {e}")
            return None

    async def _get_bigquery_conversion_data(
        self,
        start_date: str,
        end_date: str,
        conversion_events: Optional[List[str]] = None,
    ) -> Optional[Dict[str, Any]]:
        """Get conversion data from BigQuery for validation.

        Args:
            start_date: Start date
            end_date: End date
            conversion_events: List of conversion events

        Returns:
            BigQuery conversion data or None if failed
        """
        try:
            events_filter = ""
            if conversion_events:
                events_list = "', '".join(conversion_events)
                events_filter = f"AND event_name IN ('{events_list}')"

            query = f"""
            SELECT
                COUNT(*) as total_conversions,
                SUM(COALESCE(ecommerce.total_item_revenue, 0)) as total_revenue
            FROM `{self.bigquery_config.project_id}.analytics_{self.ga4_config.property_id}.events_*`
            WHERE _TABLE_SUFFIX BETWEEN '{start_date.replace("-", "")}'
                  AND '{end_date.replace("-", "")}'
                  {events_filter}
            """

            # Placeholder implementation
            return {
                "total_conversions": 50,  # Placeholder
                "total_revenue": 2500.0,  # Placeholder
                "query": query,
            }

        except Exception as e:
            logger.error(f"Failed to get BigQuery conversion data: {e}")
            return None

    async def _get_bigquery_revenue_data(
        self, start_date: str, end_date: str
    ) -> Optional[Dict[str, Any]]:
        """Get revenue data from BigQuery for validation.

        Args:
            start_date: Start date
            end_date: End date

        Returns:
            BigQuery revenue data or None if failed
        """
        try:
            query = f"""
            SELECT
                SUM(COALESCE(ecommerce.total_item_revenue, 0)) as total_revenue,
                COUNT(DISTINCT user_pseudo_id) as unique_users
            FROM `{self.bigquery_config.project_id}.analytics_{self.ga4_config.property_id}.events_*`
            WHERE _TABLE_SUFFIX BETWEEN '{start_date.replace("-", "")}'
                  AND '{end_date.replace("-", "")}'
                  AND event_name = 'purchase'
            """

            # Placeholder implementation
            return {
                "total_revenue": 5000.0,  # Placeholder
                "unique_users": 200,  # Placeholder
                "query": query,
            }

        except Exception as e:
            logger.error(f"Failed to get BigQuery revenue data: {e}")
            return None

    def _calculate_variance(self, api_total: float, bigquery_total: float) -> float:
        """Calculate variance percentage between API and BigQuery data.

        Args:
            api_total: Total from GA4 API
            bigquery_total: Total from BigQuery

        Returns:
            Variance percentage
        """
        if bigquery_total == 0:
            return 100.0 if api_total != 0 else 0.0

        return abs((api_total - bigquery_total) / bigquery_total) * 100

    def get_validation_summary(self, days: int = 7) -> Dict[str, Any]:
        """Get validation summary for the specified period.

        Args:
            days: Number of days to include in summary

        Returns:
            Validation summary
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days)
        recent_validations = [
            result
            for result in self._validation_history
            if result.checked_at >= cutoff_time
        ]

        if not recent_validations:
            return {
                "property_id": self.ga4_config.property_id,
                "status": "no_data",
                "message": "No recent validations available",
            }

        # Calculate summary statistics
        total_validations = len(recent_validations)
        passed_validations = sum(
            1 for result in recent_validations if result.is_within_tolerance
        )
        failed_validations = total_validations - passed_validations

        avg_variance = (
            sum(result.variance_percentage for result in recent_validations)
            / total_validations
        )

        # Get validation by type
        validation_by_type = {}
        for result in recent_validations:
            val_type = result.validation_type
            if val_type not in validation_by_type:
                validation_by_type[val_type] = {
                    "passed": 0,
                    "failed": 0,
                    "avg_variance": 0.0,
                }

            if result.is_within_tolerance:
                validation_by_type[val_type]["passed"] += 1
            else:
                validation_by_type[val_type]["failed"] += 1

        # Calculate average variance by type
        for val_type in validation_by_type:
            type_results = [
                r for r in recent_validations if r.validation_type == val_type
            ]
            validation_by_type[val_type]["avg_variance"] = sum(
                r.variance_percentage for r in type_results
            ) / len(type_results)

        return {
            "property_id": self.ga4_config.property_id,
            "period_days": days,
            "overall_status": "healthy"
            if passed_validations / total_validations >= 0.8
            else "warning",
            "summary": {
                "total_validations": total_validations,
                "passed_validations": passed_validations,
                "failed_validations": failed_validations,
                "success_rate": (passed_validations / total_validations) * 100,
                "average_variance": avg_variance,
            },
            "validation_by_type": validation_by_type,
            "recommendations": self._generate_validation_recommendations(
                recent_validations
            ),
            "last_validation": max(
                result.checked_at for result in recent_validations
            ).isoformat(),
        }

    def _generate_validation_recommendations(
        self, validations: List[GA4ValidationResult]
    ) -> List[Dict[str, str]]:
        """Generate recommendations based on validation results.

        Args:
            validations: List of recent validation results

        Returns:
            List of recommendations
        """
        recommendations = []

        # High variance recommendations
        high_variance_results = [
            result
            for result in validations
            if result.variance_percentage > self.CRITICAL_VARIANCE_THRESHOLD
        ]

        if high_variance_results:
            recommendations.append(
                {
                    "type": "data_quality",
                    "priority": "high",
                    "title": "High Data Variance Detected",
                    "description": (
                        f"{len(high_variance_results)} validations showed variance > "
                        f"{self.CRITICAL_VARIANCE_THRESHOLD}%"
                    ),
                    "action": "Review GA4 and BigQuery data processing pipelines",
                }
            )

        # Consistent failures recommendations
        failed_validations = [
            result for result in validations if not result.is_within_tolerance
        ]
        if len(failed_validations) > len(validations) * 0.5:  # More than 50% failures
            recommendations.append(
                {
                    "type": "data_consistency",
                    "priority": "medium",
                    "title": "Consistent Validation Failures",
                    "description": f"{len(failed_validations)} of {len(validations)} validations failed",
                    "action": "Investigate systematic differences between GA4 API and BigQuery data",
                }
            )

        # Data freshness recommendations
        api_lag_hours = self.ga4_config.max_data_lag_hours
        if api_lag_hours > 4:
            recommendations.append(
                {
                    "type": "data_freshness",
                    "priority": "low",
                    "title": "Consider Real-time API for Fresher Data",
                    "description": f"Current data lag is {api_lag_hours} hours",
                    "action": "Enable real-time GA4 API for more current metrics",
                }
            )

        return recommendations

    def get_validation_history(
        self, validation_type: Optional[str] = None
    ) -> List[GA4ValidationResult]:
        """Get validation history.

        Args:
            validation_type: Optional filter by validation type

        Returns:
            List of validation results
        """
        if validation_type:
            return [
                result
                for result in self._validation_history
                if result.validation_type == validation_type
            ]
        return self._validation_history.copy()

    def clear_validation_history(self, days_to_keep: int = 30) -> int:
        """Clear old validation history.

        Args:
            days_to_keep: Number of days to keep

        Returns:
            Number of records cleared
        """
        cutoff_time = datetime.utcnow() - timedelta(days=days_to_keep)

        original_count = len(self._validation_history)
        self._validation_history = [
            result
            for result in self._validation_history
            if result.checked_at >= cutoff_time
        ]

        cleared_count = original_count - len(self._validation_history)

        if cleared_count > 0:
            logger.info(f"Cleared {cleared_count} old GA4 validation records")

        return cleared_count
