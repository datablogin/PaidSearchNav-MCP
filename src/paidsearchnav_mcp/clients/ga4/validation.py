"""GA4 data validation and quality assessment for PaidSearchNav exports.

This module validates GA4 BigQuery integration data quality and provides
recommendations for improving attribution accuracy.
"""

import logging
from datetime import datetime, timedelta
from typing import Any, Dict, List

from paidsearchnav_mcp.platforms.ga4.bigquery_client import GA4BigQueryClient

logger = logging.getLogger(__name__)


class GA4DataValidator:
    """Validates GA4 data quality and attribution accuracy."""

    def __init__(self, ga4_client: GA4BigQueryClient):
        """Initialize the GA4 data validator.

        Args:
            ga4_client: GA4 BigQuery client for data access
        """
        self.ga4_client = ga4_client

    def validate_export_data_quality(
        self,
        google_ads_data: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Validate overall data quality for export pipeline.

        Args:
            google_ads_data: Google Ads export data
            start_date: Validation start date
            end_date: Validation end date

        Returns:
            Comprehensive data quality assessment
        """
        validation_report = {
            "validation_timestamp": datetime.utcnow().isoformat(),
            "date_range": {
                "start_date": start_date.isoformat(),
                "end_date": end_date.isoformat(),
                "days_analyzed": (end_date - start_date).days + 1,
            },
            "google_ads_data_quality": {},
            "ga4_data_quality": {},
            "attribution_quality": {},
            "recommendations": [],
            "overall_quality_score": 0.0,
        }

        try:
            # Validate Google Ads data quality
            ads_quality = self._validate_google_ads_data(google_ads_data)
            validation_report["google_ads_data_quality"] = ads_quality

            # Validate GA4 data availability and quality
            ga4_quality = self._validate_ga4_data_availability(start_date, end_date)
            validation_report["ga4_data_quality"] = ga4_quality

            # Validate GCLID attribution matching
            attribution_quality = self.ga4_client.validate_gclid_matching(
                google_ads_data, start_date, end_date
            )
            validation_report["attribution_quality"] = attribution_quality

            # Generate recommendations based on validation results
            recommendations = self._generate_data_quality_recommendations(
                ads_quality, ga4_quality, attribution_quality
            )
            validation_report["recommendations"] = recommendations

            # Calculate overall quality score
            overall_score = self._calculate_overall_quality_score(
                ads_quality, ga4_quality, attribution_quality
            )
            validation_report["overall_quality_score"] = overall_score

            logger.info(
                f"Data quality validation completed. Overall score: {overall_score:.1f}/100"
            )
            return validation_report

        except Exception as e:
            logger.error(f"Data quality validation failed: {e}")
            validation_report["error"] = str(e)
            validation_report["overall_quality_score"] = 0.0
            return validation_report

    def _validate_google_ads_data(
        self, google_ads_data: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Validate Google Ads data completeness and quality.

        Args:
            google_ads_data: Google Ads data to validate

        Returns:
            Google Ads data quality metrics
        """
        if not google_ads_data:
            return {
                "total_records": 0,
                "quality_score": 0.0,
                "has_gclids": False,
                "gclid_coverage": 0.0,
                "data_completeness": 0.0,
            }

        total_records = len(google_ads_data)
        records_with_gclids = sum(
            1 for record in google_ads_data if record.get("gclid")
        )
        records_with_cost = sum(
            1 for record in google_ads_data if record.get("cost", 0) > 0
        )
        records_with_conversions = sum(
            1 for record in google_ads_data if record.get("conversions", 0) > 0
        )

        gclid_coverage = (
            (records_with_gclids / total_records * 100) if total_records > 0 else 0.0
        )
        cost_coverage = (
            (records_with_cost / total_records * 100) if total_records > 0 else 0.0
        )
        conversion_coverage = (
            (records_with_conversions / total_records * 100)
            if total_records > 0
            else 0.0
        )

        # Calculate data completeness score
        completeness_score = (gclid_coverage + cost_coverage + conversion_coverage) / 3

        return {
            "total_records": total_records,
            "records_with_gclids": records_with_gclids,
            "gclid_coverage_percent": round(gclid_coverage, 2),
            "cost_coverage_percent": round(cost_coverage, 2),
            "conversion_coverage_percent": round(conversion_coverage, 2),
            "data_completeness_score": round(completeness_score, 2),
            "has_gclids": records_with_gclids > 0,
            "quality_score": round(completeness_score, 2),
        }

    def _validate_ga4_data_availability(
        self, start_date: datetime, end_date: datetime
    ) -> Dict[str, Any]:
        """Validate GA4 data availability and quality.

        Args:
            start_date: Validation start date
            end_date: Validation end date

        Returns:
            GA4 data quality metrics
        """
        try:
            # Discover available GA4 tables
            available_tables = self.ga4_client.discover_ga4_tables()

            # Check for recent data availability
            recent_tables = []
            target_date = end_date
            for i in range(7):  # Check last 7 days
                table_name = f"events_{target_date.strftime('%Y%m%d')}"
                if table_name in available_tables:
                    recent_tables.append(table_name)
                target_date -= timedelta(days=1)

            # Estimate data freshness
            if recent_tables:
                most_recent_table = max(recent_tables)
                most_recent_date = datetime.strptime(
                    most_recent_table.replace("events_", ""), "%Y%m%d"
                )
                data_lag_days = (datetime.now() - most_recent_date).days
            else:
                data_lag_days = 999  # No recent data

            # Calculate GA4 quality score
            table_availability_score = min(100, len(recent_tables) / 7 * 100)
            freshness_score = max(0, 100 - (data_lag_days * 20))  # Penalty for data lag
            overall_ga4_score = (table_availability_score + freshness_score) / 2

            return {
                "total_tables_available": len(available_tables),
                "recent_tables_count": len(recent_tables),
                "most_recent_table": recent_tables[0] if recent_tables else None,
                "data_lag_days": data_lag_days,
                "table_availability_score": round(table_availability_score, 2),
                "data_freshness_score": round(freshness_score, 2),
                "overall_quality_score": round(overall_ga4_score, 2),
                "ga4_dataset": getattr(self.ga4_client, "ga4_dataset_id", "unknown"),
            }

        except Exception as e:
            logger.error(f"GA4 data validation failed: {e}")
            return {
                "total_tables_available": 0,
                "recent_tables_count": 0,
                "data_lag_days": 999,
                "overall_quality_score": 0.0,
                "error": str(e),
            }

    def _generate_data_quality_recommendations(
        self,
        ads_quality: Dict[str, Any],
        ga4_quality: Dict[str, Any],
        attribution_quality: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Generate recommendations based on data quality assessment.

        Args:
            ads_quality: Google Ads data quality metrics
            ga4_quality: GA4 data quality metrics
            attribution_quality: Attribution matching quality metrics

        Returns:
            List of data quality improvement recommendations
        """
        recommendations = []

        # Google Ads data recommendations
        if ads_quality.get("gclid_coverage_percent", 0) < 80:
            recommendations.append(
                {
                    "type": "google_ads_setup",
                    "priority": "HIGH",
                    "title": "Improve GCLID tracking in Google Ads",
                    "description": f"Only {ads_quality.get('gclid_coverage_percent', 0):.1f}% of clicks have GCLIDs. Enable auto-tagging in all campaigns.",
                    "impact": "Critical for GA4 attribution accuracy",
                }
            )

        # GA4 data recommendations
        if ga4_quality.get("data_lag_days", 999) > 2:
            recommendations.append(
                {
                    "type": "ga4_setup",
                    "priority": "MEDIUM",
                    "title": "Reduce GA4 data lag",
                    "description": f"GA4 data is {ga4_quality.get('data_lag_days')} days behind. Check BigQuery export schedule.",
                    "impact": "Affects real-time analysis capabilities",
                }
            )

        if ga4_quality.get("recent_tables_count", 0) < 5:
            recommendations.append(
                {
                    "type": "ga4_setup",
                    "priority": "HIGH",
                    "title": "Ensure consistent GA4 BigQuery exports",
                    "description": f"Only {ga4_quality.get('recent_tables_count', 0)} recent GA4 tables found. Verify export configuration.",
                    "impact": "Limited historical analysis capabilities",
                }
            )

        # Attribution quality recommendations
        if attribution_quality.get("match_rate_percent", 0) < 60:
            recommendations.append(
                {
                    "type": "attribution_setup",
                    "priority": "HIGH",
                    "title": "Improve GCLID attribution matching",
                    "description": f"Only {attribution_quality.get('match_rate_percent', 0):.1f}% GCLID match rate between Ads and GA4.",
                    "impact": "Severely limits cross-platform attribution accuracy",
                }
            )

        if attribution_quality.get("data_quality_score", 0) < 70:
            recommendations.append(
                {
                    "type": "data_integration",
                    "priority": "MEDIUM",
                    "title": "Enhance data integration quality",
                    "description": f"Overall attribution quality score is {attribution_quality.get('data_quality_score', 0):.1f}/100.",
                    "impact": "Affects reliability of cross-platform insights",
                }
            )

        # Add positive recommendations for high-quality setups
        if (
            ads_quality.get("gclid_coverage_percent", 0) > 90
            and attribution_quality.get("match_rate_percent", 0) > 80
        ):
            recommendations.append(
                {
                    "type": "optimization_opportunity",
                    "priority": "LOW",
                    "title": "Excellent attribution setup detected",
                    "description": "High-quality cross-platform attribution enables advanced analytics.",
                    "impact": "Ready for advanced attribution modeling and optimization",
                }
            )

        return recommendations

    def _calculate_overall_quality_score(
        self,
        ads_quality: Dict[str, Any],
        ga4_quality: Dict[str, Any],
        attribution_quality: Dict[str, Any],
    ) -> float:
        """Calculate overall data quality score.

        Args:
            ads_quality: Google Ads data quality metrics
            ga4_quality: GA4 data quality metrics
            attribution_quality: Attribution matching quality metrics

        Returns:
            Overall quality score (0-100)
        """
        # Weight the different quality components with validation
        ads_raw = ads_quality.get("quality_score", 0)
        ga4_raw = ga4_quality.get("overall_quality_score", 0)
        attribution_raw = attribution_quality.get("data_quality_score", 0)

        # Validate and clamp individual scores to 0-100 range
        ads_clamped = max(0.0, min(100.0, ads_raw))
        ga4_clamped = max(0.0, min(100.0, ga4_raw))
        attribution_clamped = max(0.0, min(100.0, attribution_raw))

        # Apply weights
        ads_score = ads_clamped * 0.3
        ga4_score = ga4_clamped * 0.3
        attribution_score = attribution_clamped * 0.4

        overall_score = ads_score + ga4_score + attribution_score
        return round(min(100.0, max(0.0, overall_score)), 2)

    def validate_real_time_data_sync(self, hours_lookback: int = 24) -> Dict[str, Any]:
        """Validate real-time data synchronization between platforms.

        Args:
            hours_lookback: Number of hours to check for data sync

        Returns:
            Real-time sync validation results
        """
        try:
            sync_end = datetime.utcnow()
            sync_start = sync_end - timedelta(hours=hours_lookback)

            # Check for intraday GA4 tables (real-time data)
            available_tables = self.ga4_client.discover_ga4_tables()
            intraday_tables = [t for t in available_tables if "intraday" in t]

            # Get sample of recent data to check sync quality
            if intraday_tables:
                most_recent_intraday = max(intraday_tables)

                # Quick data availability check
                test_query = f"""
                SELECT COUNT(*) as event_count
                FROM `{getattr(self.ga4_client, "project_id", "unknown")}.{getattr(self.ga4_client, "ga4_dataset_id", "unknown")}.{most_recent_intraday}`
                WHERE event_timestamp >= TIMESTAMP_SUB(CURRENT_TIMESTAMP(), INTERVAL {hours_lookback} HOUR)
                LIMIT 1
                """

                result = self.ga4_client._execute_query(test_query)
                recent_events = result[0].get("event_count", 0) if result else 0

                sync_quality_score = min(
                    100.0, (recent_events / 100) * 100
                )  # Expect at least 100 events per day for 100% score
            else:
                recent_events = 0
                sync_quality_score = 0.0

            return {
                "sync_check_timestamp": sync_end.isoformat(),
                "hours_checked": hours_lookback,
                "intraday_tables_available": len(intraday_tables),
                "most_recent_intraday_table": intraday_tables[-1]
                if intraday_tables
                else None,
                "recent_events_count": recent_events,
                "sync_quality_score": round(sync_quality_score, 2),
                "real_time_ready": sync_quality_score > 50,
            }

        except Exception as e:
            logger.error(f"Real-time sync validation failed: {e}")
            return {
                "sync_check_timestamp": datetime.utcnow().isoformat(),
                "error": str(e),
                "sync_quality_score": 0.0,
                "real_time_ready": False,
            }

    def run_comprehensive_validation(
        self,
        google_ads_data: List[Dict[str, Any]],
        start_date: datetime,
        end_date: datetime,
    ) -> Dict[str, Any]:
        """Run comprehensive validation suitable for export pipeline integration.

        Args:
            google_ads_data: Google Ads export data
            start_date: Validation start date
            end_date: Validation end date

        Returns:
            Complete validation report for export pipeline
        """
        logger.info("Starting comprehensive GA4 data validation for export pipeline")

        # Run all validation checks
        export_validation = self.validate_export_data_quality(
            google_ads_data, start_date, end_date
        )
        sync_validation = self.validate_real_time_data_sync()

        # Combine results
        comprehensive_report = {
            "validation_summary": {
                "validation_timestamp": datetime.utcnow().isoformat(),
                "total_checks_run": 3,
                "overall_quality_score": export_validation.get(
                    "validation_summary", {}
                ).get("overall_quality_score", 0),
                "export_pipeline_ready": export_validation.get(
                    "validation_summary", {}
                ).get("overall_quality_score", 0)
                > 70,
                "real_time_ready": sync_validation.get("real_time_ready", False),
            },
            "export_data_quality": export_validation,
            "real_time_sync_quality": sync_validation,
            "consolidated_recommendations": self._consolidate_recommendations(
                export_validation.get("recommendations", []), sync_validation
            ),
            "next_validation_recommended": (
                datetime.utcnow() + timedelta(hours=24)
            ).isoformat(),
        }

        logger.info(
            f"Comprehensive validation completed. "
            f"Export ready: {comprehensive_report['validation_summary']['export_pipeline_ready']}, "
            f"Real-time ready: {comprehensive_report['validation_summary']['real_time_ready']}"
        )

        return comprehensive_report

    def _consolidate_recommendations(
        self,
        export_recommendations: List[Dict[str, Any]],
        sync_validation: Dict[str, Any],
    ) -> List[Dict[str, Any]]:
        """Consolidate recommendations from all validation checks.

        Args:
            export_recommendations: Recommendations from export validation
            sync_validation: Real-time sync validation results

        Returns:
            Consolidated list of recommendations
        """
        consolidated = export_recommendations.copy()

        # Add sync-specific recommendations
        if not sync_validation.get("real_time_ready", False):
            consolidated.append(
                {
                    "type": "real_time_setup",
                    "priority": "MEDIUM",
                    "title": "Enable real-time GA4 data processing",
                    "description": "Set up intraday GA4 BigQuery exports for real-time analytics",
                    "impact": "Enables real-time campaign optimization",
                }
            )

        # Sort by priority
        priority_order = {"HIGH": 0, "MEDIUM": 1, "LOW": 2}
        consolidated.sort(key=lambda x: priority_order.get(x.get("priority", "LOW"), 2))

        return consolidated
