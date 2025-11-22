"""Bridge between Python Analyzers and SQL Views.

This module provides functionality to compare Python analyzer results with
SQL view results for validation and gradual migration as described in Issue #484.
"""

import json
import logging
from datetime import datetime
from typing import Any, Dict, List

try:
    from google.cloud import bigquery

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    bigquery = None

from paidsearchnav.core.interfaces import Analyzer

from .bigquery_views import BigQueryAnalyzerViews

logger = logging.getLogger(__name__)


class AnalyzerSQLBridge:
    """Bridge for comparing Python analyzer results with SQL view results."""

    def __init__(self, bigquery_views: BigQueryAnalyzerViews):
        """Initialize with BigQuery views instance."""
        if not BIGQUERY_AVAILABLE:
            raise ImportError(
                "Google Cloud BigQuery is not installed. "
                "Install with: pip install google-cloud-bigquery"
            )
        self.bigquery_views = bigquery_views
        self.comparison_results = []

    def compare_analyzer_with_sql_view(
        self, analyzer: Analyzer, view_name: str, sample_size: int = 1000
    ) -> Dict[str, Any]:
        """Compare Python analyzer results with SQL view results.

        Args:
            analyzer: Python analyzer instance
            view_name: Name of the corresponding SQL view
            sample_size: Number of records to compare

        Returns:
            Comparison results with accuracy metrics
        """
        comparison_id = (
            f"{analyzer.__class__.__name__}_{view_name}_{datetime.now().isoformat()}"
        )

        try:
            # Get Python analyzer results
            python_results = self._get_python_analyzer_results(analyzer, sample_size)

            # Get SQL view results
            sql_results = self._get_sql_view_results(view_name, sample_size)

            # Perform comparison
            comparison = self._compare_results(python_results, sql_results)

            result = {
                "comparison_id": comparison_id,
                "analyzer_name": analyzer.__class__.__name__,
                "view_name": view_name,
                "timestamp": datetime.now().isoformat(),
                "python_record_count": len(python_results),
                "sql_record_count": len(sql_results),
                "accuracy_metrics": comparison,
                "success": True,
            }

            self.comparison_results.append(result)
            logger.info(f"Comparison completed: {comparison_id}")

            return result

        except Exception as e:
            error_result = {
                "comparison_id": comparison_id,
                "analyzer_name": analyzer.__class__.__name__,
                "view_name": view_name,
                "timestamp": datetime.now().isoformat(),
                "error": str(e),
                "success": False,
            }

            self.comparison_results.append(error_result)
            logger.error(f"Comparison failed: {comparison_id} - {e}")

            return error_result

    def _get_python_analyzer_results(
        self, analyzer: Analyzer, sample_size: int
    ) -> List[Dict[str, Any]]:
        """Get results from Python analyzer."""
        # This is a simplified implementation
        # In practice, you would run the analyzer with appropriate data
        analysis_result = analyzer.analyze()

        if hasattr(analysis_result, "recommendations"):
            results = []
            for i, recommendation in enumerate(
                analysis_result.recommendations[:sample_size]
            ):
                result = {
                    "id": i,
                    "type": recommendation.type.value
                    if hasattr(recommendation.type, "value")
                    else str(recommendation.type),
                    "priority": recommendation.priority.value
                    if hasattr(recommendation.priority, "value")
                    else str(recommendation.priority),
                    "title": recommendation.title,
                    "estimated_impact": getattr(
                        recommendation, "estimated_impact", 0.0
                    ),
                    "metadata": getattr(recommendation, "metadata", {}),
                }
                results.append(result)
            return results

        # Fallback for different analyzer types
        return [{"analyzer_type": analyzer.__class__.__name__, "sample_data": True}]

    def _get_sql_view_results(
        self, view_name: str, sample_size: int
    ) -> List[Dict[str, Any]]:
        """Get results from SQL view."""
        try:
            client = self.bigquery_views._get_client()
            dataset_ref = self.bigquery_views._get_dataset_ref()

            query = f"""
            SELECT *
            FROM `{dataset_ref.project}.{dataset_ref.dataset_id}.{view_name}`
            ORDER BY analysis_timestamp DESC
            LIMIT {sample_size}
            """

            query_job = client.query(query)
            results = query_job.result()

            return [dict(row) for row in results]

        except Exception as e:
            logger.error(f"Failed to get SQL view results: {e}")
            return []

    def _compare_results(
        self, python_results: List[Dict[str, Any]], sql_results: List[Dict[str, Any]]
    ) -> Dict[str, Any]:
        """Compare Python and SQL results for accuracy with detailed data validation."""
        if not python_results or not sql_results:
            return {
                "accuracy_percent": 0.0,
                "message": "Insufficient data for comparison",
                "python_count": len(python_results),
                "sql_count": len(sql_results),
            }

        # Structural comparison
        python_keys = set(python_results[0].keys()) if python_results else set()
        sql_keys = set(sql_results[0].keys()) if sql_results else set()
        common_keys = python_keys.intersection(sql_keys)

        # Enhanced data validation
        value_matches = 0
        total_comparable_values = 0
        data_discrepancies = []

        # Compare actual data values for common keys
        min_records = min(len(python_results), len(sql_results))

        for i in range(min_records):
            python_record = python_results[i]
            sql_record = sql_results[i]

            for key in common_keys:
                if key in python_record and key in sql_record:
                    total_comparable_values += 1
                    python_value = python_record[key]
                    sql_value = sql_record[key]

                    # Normalize and compare values
                    if self._values_match(python_value, sql_value):
                        value_matches += 1
                    else:
                        data_discrepancies.append(
                            {
                                "record_index": i,
                                "field": key,
                                "python_value": python_value,
                                "sql_value": sql_value,
                            }
                        )

        # Calculate comprehensive accuracy metrics
        structural_accuracy = (
            len(common_keys) / max(len(python_keys), len(sql_keys)) * 100
            if python_keys or sql_keys
            else 0
        )

        data_accuracy = (
            value_matches / total_comparable_values * 100
            if total_comparable_values > 0
            else 0
        )

        count_accuracy = (
            1
            - abs(len(python_results) - len(sql_results))
            / max(len(python_results), len(sql_results))
        ) * 100

        # Overall accuracy is weighted average
        overall_accuracy = (
            structural_accuracy * 0.2 + data_accuracy * 0.6 + count_accuracy * 0.2
        )

        return {
            "accuracy_percent": round(overall_accuracy, 2),
            "structural_accuracy": round(structural_accuracy, 2),
            "data_accuracy": round(data_accuracy, 2),
            "count_accuracy": round(count_accuracy, 2),
            "python_count": len(python_results),
            "sql_count": len(sql_results),
            "common_keys": list(common_keys),
            "python_only_keys": list(python_keys - sql_keys),
            "sql_only_keys": list(sql_keys - python_keys),
            "value_matches": value_matches,
            "total_comparable_values": total_comparable_values,
            "data_discrepancies": data_discrepancies[:10],  # Limit to first 10
            "discrepancy_count": len(data_discrepancies),
        }

    def _values_match(
        self, python_value: Any, sql_value: Any, tolerance: float = 0.01
    ) -> bool:
        """Check if two values match with tolerance for floating point numbers."""
        # Handle None values
        if python_value is None and sql_value is None:
            return True
        if python_value is None or sql_value is None:
            return False

        # Handle numeric values with tolerance
        if isinstance(python_value, (int, float)) and isinstance(
            sql_value, (int, float)
        ):
            if python_value == 0 and sql_value == 0:
                return True
            if python_value == 0 or sql_value == 0:
                return abs(python_value - sql_value) <= tolerance
            return (
                abs(python_value - sql_value) / max(abs(python_value), abs(sql_value))
                <= tolerance
            )

        # Handle string values (case insensitive)
        if isinstance(python_value, str) and isinstance(sql_value, str):
            return python_value.lower().strip() == sql_value.lower().strip()

        # Handle boolean values
        if isinstance(python_value, bool) and isinstance(sql_value, bool):
            return python_value == sql_value

        # Handle datetime/timestamp values
        if hasattr(python_value, "isoformat") and hasattr(sql_value, "isoformat"):
            return python_value.isoformat() == sql_value.isoformat()

        # Default exact match
        return python_value == sql_value

    def validate_all_views(self) -> Dict[str, Any]:
        """Validate all SQL views by running sample queries."""
        validation_results = {}

        view_names = [
            "analyzer_search_terms_recommendations",
            "analyzer_keywords_bid_recommendations",
            "analyzer_campaign_performance_insights",
            "analyzer_ad_group_quality_scores",
            "analyzer_geographic_performance",
            "analyzer_local_intent_detection",
            "analyzer_match_type_optimization",
            "analyzer_quality_score_insights",
            "analyzer_cost_efficiency_metrics",
            "analyzer_performance_trends",
            "analyzer_negative_keyword_conflicts",
            "analyzer_budget_allocation_recommendations",
            "analyzer_demographic_performance_insights",
            "analyzer_device_cross_performance",
            "analyzer_seasonal_trend_detection",
        ]

        for view_name in view_names:
            try:
                result = self.bigquery_views.validate_view_results(view_name, 10)
                validation_results[view_name] = result
                logger.info(
                    f"Validated view: {view_name} - Success: {result['success']}"
                )
            except Exception as e:
                validation_results[view_name] = {
                    "success": False,
                    "error": str(e),
                    "view_name": view_name,
                }
                logger.error(f"Failed to validate view {view_name}: {e}")

        return validation_results

    def generate_migration_report(self) -> Dict[str, Any]:
        """Generate a comprehensive migration report."""
        report = {
            "report_id": f"migration_report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "total_comparisons": len(self.comparison_results),
            "successful_comparisons": len(
                [r for r in self.comparison_results if r.get("success", False)]
            ),
            "failed_comparisons": len(
                [r for r in self.comparison_results if not r.get("success", False)]
            ),
            "comparison_details": self.comparison_results,
            "summary": {},
        }

        if self.comparison_results:
            successful_results = [
                r for r in self.comparison_results if r.get("success", False)
            ]

            if successful_results:
                accuracies = [
                    r["accuracy_metrics"]["accuracy_percent"]
                    for r in successful_results
                    if "accuracy_metrics" in r
                ]

                report["summary"] = {
                    "average_accuracy": round(sum(accuracies) / len(accuracies), 2)
                    if accuracies
                    else 0,
                    "min_accuracy": min(accuracies) if accuracies else 0,
                    "max_accuracy": max(accuracies) if accuracies else 0,
                    "high_accuracy_views": len([a for a in accuracies if a >= 90]),
                    "medium_accuracy_views": len(
                        [a for a in accuracies if 70 <= a < 90]
                    ),
                    "low_accuracy_views": len([a for a in accuracies if a < 70]),
                }

        return report

    def export_comparison_results(self, file_path: str) -> None:
        """Export comparison results to JSON file."""
        report = self.generate_migration_report()

        with open(file_path, "w") as f:
            json.dump(report, f, indent=2, default=str)

        logger.info(f"Exported comparison results to: {file_path}")

    def get_performance_benchmark(self, view_name: str) -> Dict[str, Any]:
        """Get performance benchmark for a specific view."""
        try:
            client = self.bigquery_views._get_client()
            dataset_ref = self.bigquery_views._get_dataset_ref()

            # Simple query to measure execution time
            query = f"""
            SELECT COUNT(*) as record_count
            FROM `{dataset_ref.project}.{dataset_ref.dataset_id}.{view_name}`
            """

            start_time = datetime.now()
            query_job = client.query(query)
            results = list(query_job.result())
            end_time = datetime.now()

            execution_time = (end_time - start_time).total_seconds()

            return {
                "view_name": view_name,
                "execution_time_seconds": execution_time,
                "record_count": results[0]["record_count"] if results else 0,
                "performance_category": self._categorize_performance(execution_time),
                "timestamp": datetime.now().isoformat(),
            }

        except Exception as e:
            return {
                "view_name": view_name,
                "error": str(e),
                "timestamp": datetime.now().isoformat(),
            }

    def _categorize_performance(self, execution_time: float) -> str:
        """Categorize query performance based on execution time."""
        if execution_time < 2.0:
            return "EXCELLENT"
        elif execution_time < 5.0:
            return "GOOD"
        elif execution_time < 10.0:
            return "ACCEPTABLE"
        else:
            return "NEEDS_OPTIMIZATION"

    def benchmark_all_views(self) -> Dict[str, Any]:
        """Benchmark performance for all views."""
        view_names = [
            "analyzer_search_terms_recommendations",
            "analyzer_keywords_bid_recommendations",
            "analyzer_campaign_performance_insights",
            "analyzer_ad_group_quality_scores",
            "analyzer_geographic_performance",
        ]

        benchmarks = {}

        for view_name in view_names:
            benchmark = self.get_performance_benchmark(view_name)
            benchmarks[view_name] = benchmark

            if "error" not in benchmark:
                logger.info(
                    f"Benchmarked {view_name}: {benchmark['execution_time_seconds']:.2f}s - {benchmark['performance_category']}"
                )

        return benchmarks


class AnalyzerMigrationManager:
    """Manages the migration from Python analyzers to SQL views."""

    def __init__(self, bridge: AnalyzerSQLBridge):
        """Initialize with analyzer SQL bridge."""
        self.bridge = bridge
        self.migration_status = {}

    def plan_migration(self, analyzer_view_mapping: Dict[str, str]) -> Dict[str, Any]:
        """Plan the migration for given analyzer-view mappings.

        Args:
            analyzer_view_mapping: Dict mapping analyzer names to view names

        Returns:
            Migration plan with priorities and steps
        """
        plan = {
            "migration_id": f"migration_plan_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
            "timestamp": datetime.now().isoformat(),
            "total_analyzers": len(analyzer_view_mapping),
            "phases": {
                "phase_1_core": [],
                "phase_2_advanced": [],
                "phase_3_complex": [],
            },
            "estimated_timeline": "6-8 weeks",
            "success_criteria": {
                "minimum_accuracy": 95.0,
                "maximum_performance_degradation": 10.0,
                "required_validations": ["accuracy", "performance", "data_consistency"],
            },
        }

        # Categorize analyzers by complexity
        core_analyzers = [
            "SearchTermAnalyzer",
            "KeywordAnalyzer",
            "CampaignPerformanceAnalyzer",
        ]

        advanced_analyzers = [
            "GeoPerformanceAnalyzer",
            "QualityScoreAnalyzer",
            "MatchTypeAnalyzer",
        ]

        for analyzer_name, view_name in analyzer_view_mapping.items():
            migration_item = {
                "analyzer_name": analyzer_name,
                "view_name": view_name,
                "priority": "HIGH"
                if analyzer_name in core_analyzers
                else "MEDIUM"
                if analyzer_name in advanced_analyzers
                else "LOW",
            }

            if analyzer_name in core_analyzers:
                plan["phases"]["phase_1_core"].append(migration_item)
            elif analyzer_name in advanced_analyzers:
                plan["phases"]["phase_2_advanced"].append(migration_item)
            else:
                plan["phases"]["phase_3_complex"].append(migration_item)

        return plan

    def execute_migration_phase(
        self, phase_analyzers: List[Dict[str, str]]
    ) -> Dict[str, Any]:
        """Execute a specific migration phase.

        Args:
            phase_analyzers: List of analyzer-view mappings for this phase

        Returns:
            Phase execution results
        """
        phase_id = f"phase_{datetime.now().strftime('%Y%m%d_%H%M%S')}"
        results = {
            "phase_id": phase_id,
            "timestamp": datetime.now().isoformat(),
            "total_items": len(phase_analyzers),
            "completed_items": 0,
            "failed_items": 0,
            "validation_results": [],
            "performance_benchmarks": [],
        }

        for item in phase_analyzers:
            try:
                # Validate the view
                validation = self.bridge.bigquery_views.validate_view_results(
                    item["view_name"]
                )
                results["validation_results"].append(validation)

                # Benchmark performance
                benchmark = self.bridge.get_performance_benchmark(item["view_name"])
                results["performance_benchmarks"].append(benchmark)

                if validation.get("success", False):
                    results["completed_items"] += 1
                    self.migration_status[item["analyzer_name"]] = "MIGRATED"
                else:
                    results["failed_items"] += 1
                    self.migration_status[item["analyzer_name"]] = "FAILED"

            except Exception as e:
                results["failed_items"] += 1
                self.migration_status[item["analyzer_name"]] = "ERROR"
                logger.error(f"Migration failed for {item['analyzer_name']}: {e}")

        return results

    def get_migration_status(self) -> Dict[str, Any]:
        """Get current migration status."""
        return {
            "timestamp": datetime.now().isoformat(),
            "migration_status": self.migration_status,
            "summary": {
                "total_analyzers": len(self.migration_status),
                "migrated": len(
                    [s for s in self.migration_status.values() if s == "MIGRATED"]
                ),
                "failed": len(
                    [s for s in self.migration_status.values() if s == "FAILED"]
                ),
                "errors": len(
                    [s for s in self.migration_status.values() if s == "ERROR"]
                ),
                "pending": len(
                    [s for s in self.migration_status.values() if s == "PENDING"]
                ),
            },
        }
