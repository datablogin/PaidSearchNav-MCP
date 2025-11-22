"""Tests for Analyzer SQL Bridge."""

import json
from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav.core.interfaces import Analyzer
from paidsearchnav.core.models import (
    AnalysisResult,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.exports.analyzer_sql_bridge import (
    AnalyzerMigrationManager,
    AnalyzerSQLBridge,
)
from paidsearchnav.exports.bigquery_views import BigQueryAnalyzerViews


class TestAnalyzerSQLBridge:
    """Test AnalyzerSQLBridge functionality."""

    @pytest.fixture
    def mock_bigquery_views(self):
        """Create mock BigQuery views."""
        views = MagicMock(spec=BigQueryAnalyzerViews)
        views._get_client = MagicMock()
        views._get_dataset_ref = MagicMock()
        views.validate_view_results = MagicMock()
        return views

    @pytest.fixture
    def mock_analyzer(self):
        """Create mock analyzer."""
        analyzer = MagicMock(spec=Analyzer)

        # Create mock recommendations
        mock_recommendations = [
            MagicMock(
                type=RecommendationType.KEYWORD_BID_ADJUSTMENT,
                priority=RecommendationPriority.HIGH,
                title="Increase bid for high-performing keyword",
                estimated_impact=100.0,
                metadata={"keyword": "test keyword"},
            ),
            MagicMock(
                type=RecommendationType.NEGATIVE_KEYWORD,
                priority=RecommendationPriority.MEDIUM,
                title="Add negative keyword",
                estimated_impact=50.0,
                metadata={"term": "test term"},
            ),
        ]

        # Create mock analysis result
        mock_result = MagicMock(spec=AnalysisResult)
        mock_result.recommendations = mock_recommendations
        analyzer.analyze.return_value = mock_result

        return analyzer

    @pytest.fixture
    def bridge(self, mock_bigquery_views):
        """Create AnalyzerSQLBridge instance."""
        with patch(
            "paidsearchnav.exports.analyzer_sql_bridge.BIGQUERY_AVAILABLE", True
        ):
            return AnalyzerSQLBridge(mock_bigquery_views)

    def test_init_without_bigquery(self, mock_bigquery_views):
        """Test initialization without BigQuery available."""
        with patch(
            "paidsearchnav.exports.analyzer_sql_bridge.BIGQUERY_AVAILABLE", False
        ):
            with pytest.raises(
                ImportError, match="Google Cloud BigQuery is not installed"
            ):
                AnalyzerSQLBridge(mock_bigquery_views)

    def test_compare_analyzer_with_sql_view_success(
        self, bridge, mock_analyzer, mock_bigquery_views
    ):
        """Test successful comparison between analyzer and SQL view."""
        # Mock SQL view results
        mock_sql_results = [
            {"id": 1, "type": "KEYWORD_BID_ADJUSTMENT", "priority": "HIGH"},
            {"id": 2, "type": "NEGATIVE_KEYWORD", "priority": "MEDIUM"},
        ]

        bridge._get_sql_view_results = MagicMock(return_value=mock_sql_results)

        result = bridge.compare_analyzer_with_sql_view(
            mock_analyzer, "test_view", sample_size=100
        )

        assert result["success"] is True
        assert result["analyzer_name"] == mock_analyzer.__class__.__name__
        assert result["view_name"] == "test_view"
        assert "comparison_id" in result
        assert "accuracy_metrics" in result

    def test_compare_analyzer_with_sql_view_failure(self, bridge, mock_analyzer):
        """Test comparison failure handling."""
        # Mock an exception during comparison
        bridge._get_sql_view_results = MagicMock(side_effect=Exception("Test error"))

        result = bridge.compare_analyzer_with_sql_view(mock_analyzer, "test_view")

        assert result["success"] is False
        assert "error" in result
        assert "Test error" in result["error"]

    def test_get_python_analyzer_results(self, bridge, mock_analyzer):
        """Test getting Python analyzer results."""
        results = bridge._get_python_analyzer_results(mock_analyzer, 100)

        assert isinstance(results, list)
        assert len(results) == 2  # Two mock recommendations
        assert results[0]["type"] == "KEYWORD_BID_ADJUSTMENT"
        assert results[1]["type"] == "NEGATIVE_KEYWORD"

    def test_get_sql_view_results(self, bridge, mock_bigquery_views):
        """Test getting SQL view results."""
        # Mock BigQuery client and results
        mock_client = MagicMock()
        mock_dataset_ref = MagicMock()
        mock_dataset_ref.project = "test-project"
        mock_dataset_ref.dataset_id = "test_dataset"

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [
            {"column1": "value1", "column2": "value2"},
            {"column1": "value3", "column2": "value4"},
        ]

        mock_client.query.return_value = mock_query_job
        mock_bigquery_views._get_client.return_value = mock_client
        mock_bigquery_views._get_dataset_ref.return_value = mock_dataset_ref

        results = bridge._get_sql_view_results("test_view", 100)

        assert isinstance(results, list)
        assert len(results) == 2
        mock_client.query.assert_called_once()

    def test_get_sql_view_results_failure(self, bridge, mock_bigquery_views):
        """Test SQL view results failure handling."""
        mock_bigquery_views._get_client.side_effect = Exception("Connection failed")

        results = bridge._get_sql_view_results("test_view", 100)

        assert results == []

    def test_compare_results_with_data(self, bridge):
        """Test result comparison with actual data."""
        python_results = [
            {"id": 1, "type": "KEYWORD", "priority": "HIGH"},
            {"id": 2, "type": "NEGATIVE", "priority": "LOW"},
        ]

        sql_results = [
            {"id": 1, "type": "KEYWORD", "priority": "HIGH", "extra": "data"},
            {"id": 2, "type": "NEGATIVE", "priority": "MEDIUM"},
        ]

        comparison = bridge._compare_results(python_results, sql_results)

        assert "accuracy_percent" in comparison
        assert "key_overlap_percent" in comparison
        assert "common_keys" in comparison
        assert comparison["python_count"] == 2
        assert comparison["sql_count"] == 2

    def test_compare_results_empty_data(self, bridge):
        """Test result comparison with empty data."""
        comparison = bridge._compare_results([], [])

        assert comparison["accuracy_percent"] == 0.0
        assert "Insufficient data" in comparison["message"]

    def test_enhanced_comparison_logic(self, bridge):
        """Test enhanced comparison logic with detailed data validation."""
        python_results = [
            {"id": 1, "cost": 100.0, "conversions": 5, "campaign": "Test Campaign"},
            {"id": 2, "cost": 200.0, "conversions": 10, "campaign": "Another Campaign"},
        ]

        sql_results = [
            {
                "id": 1,
                "cost": 100.05,
                "conversions": 5,
                "campaign": "test campaign",
            },  # Small float diff, case diff
            {"id": 2, "cost": 200.0, "conversions": 10, "campaign": "Another Campaign"},
        ]

        comparison = bridge._compare_results(python_results, sql_results)

        # Should have high accuracy due to tolerance handling
        assert comparison["data_accuracy"] > 95.0
        assert comparison["structural_accuracy"] == 100.0  # Same keys
        assert comparison["count_accuracy"] == 100.0  # Same count
        assert (
            comparison["value_matches"] == 8
        )  # All values match: id, conversions, campaign, cost for both records (cost matches with tolerance)
        assert comparison["total_comparable_values"] == 8

    def test_values_match_tolerance(self, bridge):
        """Test value matching with tolerance for different data types."""
        # Float tolerance
        assert bridge._values_match(100.0, 100.005) is True
        assert bridge._values_match(100.0, 102.0) is False

        # String case insensitive
        assert bridge._values_match("Test Campaign", "test campaign") is True
        assert bridge._values_match("Test Campaign", "Different Campaign") is False

        # None values
        assert bridge._values_match(None, None) is True
        assert bridge._values_match(None, "value") is False

        # Boolean values
        assert bridge._values_match(True, True) is True
        assert bridge._values_match(True, False) is False

        # Integer values
        assert bridge._values_match(5, 5) is True
        assert bridge._values_match(5, 6) is False

    def test_comparison_with_discrepancies(self, bridge):
        """Test comparison reporting discrepancies correctly."""
        python_results = [
            {"cost": 100.0, "conversions": 5},
            {"cost": 200.0, "conversions": 0},  # Different value
        ]

        sql_results = [
            {"cost": 100.0, "conversions": 5},
            {"cost": 200.0, "conversions": 1},  # Different value
        ]

        comparison = bridge._compare_results(python_results, sql_results)

        assert comparison["discrepancy_count"] == 1
        assert len(comparison["data_discrepancies"]) == 1
        assert comparison["data_discrepancies"][0]["field"] == "conversions"
        assert comparison["data_discrepancies"][0]["python_value"] == 0
        assert comparison["data_discrepancies"][0]["sql_value"] == 1

    def test_validate_all_views(self, bridge, mock_bigquery_views):
        """Test validation of all views."""
        mock_bigquery_views.validate_view_results.return_value = {
            "success": True,
            "row_count": 100,
            "view_name": "test_view",
        }

        results = bridge.validate_all_views()

        assert isinstance(results, dict)
        assert len(results) > 0

        # Check that all expected views are included
        expected_views = [
            "analyzer_search_terms_recommendations",
            "analyzer_keywords_bid_recommendations",
            "analyzer_campaign_performance_insights",
        ]

        for view in expected_views:
            assert view in results

    def test_generate_migration_report_empty(self, bridge):
        """Test migration report generation with no comparisons."""
        report = bridge.generate_migration_report()

        assert "report_id" in report
        assert report["total_comparisons"] == 0
        assert report["successful_comparisons"] == 0
        assert report["failed_comparisons"] == 0

    def test_generate_migration_report_with_data(self, bridge):
        """Test migration report generation with comparison data."""
        # Add mock comparison results
        bridge.comparison_results = [
            {"success": True, "accuracy_metrics": {"accuracy_percent": 95.0}},
            {"success": True, "accuracy_metrics": {"accuracy_percent": 88.0}},
            {"success": False, "error": "Test error"},
        ]

        report = bridge.generate_migration_report()

        assert report["total_comparisons"] == 3
        assert report["successful_comparisons"] == 2
        assert report["failed_comparisons"] == 1
        assert "summary" in report
        assert report["summary"]["average_accuracy"] == 91.5

    def test_export_comparison_results(self, bridge, tmp_path):
        """Test exporting comparison results to file."""
        # Add mock comparison data
        bridge.comparison_results = [
            {"success": True, "accuracy_metrics": {"accuracy_percent": 95.0}}
        ]

        file_path = tmp_path / "test_results.json"
        bridge.export_comparison_results(str(file_path))

        assert file_path.exists()

        with open(file_path) as f:
            data = json.load(f)

        assert "report_id" in data
        assert data["total_comparisons"] == 1

    def test_get_performance_benchmark_success(self, bridge, mock_bigquery_views):
        """Test successful performance benchmarking."""
        # Mock BigQuery client and results
        mock_client = MagicMock()
        mock_dataset_ref = MagicMock()
        mock_dataset_ref.project = "test-project"
        mock_dataset_ref.dataset_id = "test_dataset"

        mock_query_job = MagicMock()
        mock_query_job.result.return_value = [{"record_count": 1000}]

        mock_client.query.return_value = mock_query_job
        mock_bigquery_views._get_client.return_value = mock_client
        mock_bigquery_views._get_dataset_ref.return_value = mock_dataset_ref

        benchmark = bridge.get_performance_benchmark("test_view")

        assert "view_name" in benchmark
        assert "execution_time_seconds" in benchmark
        assert "record_count" in benchmark
        assert "performance_category" in benchmark
        assert benchmark["record_count"] == 1000

    def test_get_performance_benchmark_failure(self, bridge, mock_bigquery_views):
        """Test performance benchmarking failure."""
        mock_bigquery_views._get_client.side_effect = Exception("Query failed")

        benchmark = bridge.get_performance_benchmark("test_view")

        assert "error" in benchmark
        assert "Query failed" in benchmark["error"]

    def test_categorize_performance(self, bridge):
        """Test performance categorization."""
        assert bridge._categorize_performance(1.0) == "EXCELLENT"
        assert bridge._categorize_performance(3.0) == "GOOD"
        assert bridge._categorize_performance(7.0) == "ACCEPTABLE"
        assert bridge._categorize_performance(15.0) == "NEEDS_OPTIMIZATION"

    def test_benchmark_all_views(self, bridge):
        """Test benchmarking all views."""
        # Mock the benchmark method
        bridge.get_performance_benchmark = MagicMock(
            return_value={
                "view_name": "test_view",
                "execution_time_seconds": 1.5,
                "performance_category": "EXCELLENT",
            }
        )

        benchmarks = bridge.benchmark_all_views()

        assert isinstance(benchmarks, dict)
        assert len(benchmarks) > 0

        # Verify at least some expected views are benchmarked
        expected_views = [
            "analyzer_search_terms_recommendations",
            "analyzer_keywords_bid_recommendations",
        ]

        for view in expected_views:
            assert view in benchmarks


class TestAnalyzerMigrationManager:
    """Test AnalyzerMigrationManager functionality."""

    @pytest.fixture
    def mock_bridge(self):
        """Create mock analyzer SQL bridge."""
        bridge = MagicMock(spec=AnalyzerSQLBridge)
        bridge.bigquery_views = MagicMock()
        bridge.get_performance_benchmark = MagicMock()
        return bridge

    @pytest.fixture
    def migration_manager(self, mock_bridge):
        """Create AnalyzerMigrationManager instance."""
        return AnalyzerMigrationManager(mock_bridge)

    def test_plan_migration(self, migration_manager):
        """Test migration planning."""
        analyzer_view_mapping = {
            "SearchTermAnalyzer": "analyzer_search_terms_recommendations",
            "KeywordAnalyzer": "analyzer_keywords_bid_recommendations",
            "ComplexAnalyzer": "analyzer_complex_view",
        }

        plan = migration_manager.plan_migration(analyzer_view_mapping)

        assert "migration_id" in plan
        assert plan["total_analyzers"] == 3
        assert "phases" in plan
        assert "phase_1_core" in plan["phases"]
        assert "phase_2_advanced" in plan["phases"]
        assert "phase_3_complex" in plan["phases"]

        # Check that core analyzers are in phase 1
        phase_1_analyzers = [
            item["analyzer_name"] for item in plan["phases"]["phase_1_core"]
        ]
        assert "SearchTermAnalyzer" in phase_1_analyzers
        assert "KeywordAnalyzer" in phase_1_analyzers

    def test_execute_migration_phase(self, migration_manager, mock_bridge):
        """Test migration phase execution."""
        phase_analyzers = [{"analyzer_name": "TestAnalyzer", "view_name": "test_view"}]

        # Mock successful validation and benchmarking
        mock_bridge.bigquery_views.validate_view_results.return_value = {
            "success": True,
            "view_name": "test_view",
        }
        mock_bridge.get_performance_benchmark.return_value = {
            "view_name": "test_view",
            "execution_time_seconds": 1.5,
        }

        results = migration_manager.execute_migration_phase(phase_analyzers)

        assert "phase_id" in results
        assert results["total_items"] == 1
        assert results["completed_items"] == 1
        assert results["failed_items"] == 0
        assert migration_manager.migration_status["TestAnalyzer"] == "MIGRATED"

    def test_execute_migration_phase_with_failure(self, migration_manager, mock_bridge):
        """Test migration phase execution with validation failure."""
        phase_analyzers = [{"analyzer_name": "TestAnalyzer", "view_name": "test_view"}]

        # Mock failed validation
        mock_bridge.bigquery_views.validate_view_results.return_value = {
            "success": False,
            "view_name": "test_view",
            "error": "Validation failed",
        }

        results = migration_manager.execute_migration_phase(phase_analyzers)

        assert results["failed_items"] == 1
        assert migration_manager.migration_status["TestAnalyzer"] == "FAILED"

    def test_execute_migration_phase_with_exception(
        self, migration_manager, mock_bridge
    ):
        """Test migration phase execution with exception."""
        phase_analyzers = [{"analyzer_name": "TestAnalyzer", "view_name": "test_view"}]

        # Mock exception during validation
        mock_bridge.bigquery_views.validate_view_results.side_effect = Exception(
            "Test error"
        )

        results = migration_manager.execute_migration_phase(phase_analyzers)

        assert results["failed_items"] == 1
        assert migration_manager.migration_status["TestAnalyzer"] == "ERROR"

    def test_get_migration_status_empty(self, migration_manager):
        """Test getting migration status when empty."""
        status = migration_manager.get_migration_status()

        assert "timestamp" in status
        assert "migration_status" in status
        assert "summary" in status
        assert status["summary"]["total_analyzers"] == 0

    def test_get_migration_status_with_data(self, migration_manager):
        """Test getting migration status with data."""
        # Set up migration status
        migration_manager.migration_status = {
            "Analyzer1": "MIGRATED",
            "Analyzer2": "FAILED",
            "Analyzer3": "ERROR",
            "Analyzer4": "PENDING",
        }

        status = migration_manager.get_migration_status()

        assert status["summary"]["total_analyzers"] == 4
        assert status["summary"]["migrated"] == 1
        assert status["summary"]["failed"] == 1
        assert status["summary"]["errors"] == 1
        assert status["summary"]["pending"] == 1

    def test_migration_phases_categorization(self, migration_manager):
        """Test that analyzers are correctly categorized into phases."""
        analyzer_view_mapping = {
            "SearchTermAnalyzer": "view1",
            "KeywordAnalyzer": "view2",
            "CampaignPerformanceAnalyzer": "view3",
            "GeoPerformanceAnalyzer": "view4",
            "QualityScoreAnalyzer": "view5",
            "CustomAnalyzer": "view6",
        }

        plan = migration_manager.plan_migration(analyzer_view_mapping)

        # Core analyzers should be in phase 1
        phase_1_names = [
            item["analyzer_name"] for item in plan["phases"]["phase_1_core"]
        ]
        assert "SearchTermAnalyzer" in phase_1_names
        assert "KeywordAnalyzer" in phase_1_names
        assert "CampaignPerformanceAnalyzer" in phase_1_names

        # Advanced analyzers should be in phase 2
        phase_2_names = [
            item["analyzer_name"] for item in plan["phases"]["phase_2_advanced"]
        ]
        assert "GeoPerformanceAnalyzer" in phase_2_names
        assert "QualityScoreAnalyzer" in phase_2_names

        # Unknown analyzers should be in phase 3
        phase_3_names = [
            item["analyzer_name"] for item in plan["phases"]["phase_3_complex"]
        ]
        assert "CustomAnalyzer" in phase_3_names
