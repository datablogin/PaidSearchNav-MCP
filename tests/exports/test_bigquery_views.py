"""Tests for BigQuery Analyzer Views."""

from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav_mcp.exports.base import ExportConfig, ExportFormat
from paidsearchnav_mcp.exports.bigquery import BigQueryExporter
from paidsearchnav_mcp.exports.bigquery_views import (
    AnalyzerViewConfig,
    BigQueryAnalyzerViews,
)


class TestBigQueryAnalyzerViews:
    """Test BigQuery analyzer views functionality."""

    @pytest.fixture
    def mock_bigquery_exporter(self):
        """Create a mock BigQuery exporter."""
        config = ExportConfig(
            destination_type=ExportFormat.BIGQUERY,
            project_id="test-project",
            dataset="test_dataset",
            credentials={"service_account_json": "{}"},
        )
        exporter = MagicMock(spec=BigQueryExporter)
        exporter.config = config
        return exporter

    @pytest.fixture
    def mock_bigquery_client(self):
        """Create a mock BigQuery client."""
        client = MagicMock()
        client.create_table = MagicMock()
        client.delete_table = MagicMock()
        client.query = MagicMock()
        return client

    @pytest.fixture
    def mock_dataset_ref(self):
        """Create a mock dataset reference."""
        dataset_ref = MagicMock()
        dataset_ref.project = "test-project"
        dataset_ref.dataset_id = "test_dataset"
        dataset_ref.table = MagicMock(return_value="table_ref")
        return dataset_ref

    @pytest.fixture
    def bigquery_views(self, mock_bigquery_exporter):
        """Create BigQueryAnalyzerViews instance."""
        with patch("paidsearchnav.exports.bigquery_views.BIGQUERY_AVAILABLE", True):
            views = BigQueryAnalyzerViews(mock_bigquery_exporter)
            return views

    def test_init_without_bigquery(self, mock_bigquery_exporter):
        """Test initialization without BigQuery available."""
        with patch("paidsearchnav.exports.bigquery_views.BIGQUERY_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="Google Cloud BigQuery is not installed"
            ):
                BigQueryAnalyzerViews(mock_bigquery_exporter)

    def test_create_view_success(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test successful view creation."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        sql = "SELECT * FROM test_table"
        result = bigquery_views._create_view("test_view", sql)

        assert result is True
        mock_bigquery_client.create_table.assert_called_once()

    def test_create_view_failure(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test view creation failure."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        from paidsearchnav.exports.bigquery_views import GoogleCloudError

        mock_bigquery_client.create_table.side_effect = GoogleCloudError("Test error")

        sql = "SELECT * FROM test_table"
        result = bigquery_views._create_view("test_view", sql)

        assert result is False

    def test_drop_view_success(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test successful view deletion."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        result = bigquery_views.drop_view("test_view")

        assert result is True
        mock_bigquery_client.delete_table.assert_called_once()

    def test_drop_view_failure(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test view deletion failure."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        from paidsearchnav.exports.bigquery_views import GoogleCloudError

        mock_bigquery_client.delete_table.side_effect = GoogleCloudError("Test error")

        result = bigquery_views.drop_view("test_view")

        assert result is False

    def test_validate_view_results_success(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test successful view validation."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        # Mock query results
        mock_results = [{"col1": "value1"}, {"col1": "value2"}]
        mock_query_job = MagicMock()
        mock_query_job.result.return_value = mock_results
        mock_bigquery_client.query.return_value = mock_query_job

        result = bigquery_views.validate_view_results("test_view", 100)

        assert result["success"] is True
        assert result["row_count"] == 2
        assert result["view_name"] == "test_view"

    def test_validate_view_results_failure(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test view validation failure."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        mock_bigquery_client.query.side_effect = Exception("Query failed")

        result = bigquery_views.validate_view_results("test_view")

        assert result["success"] is False
        assert "Query failed" in result["error"]

    def test_create_all_analyzer_views(self, bigquery_views):
        """Test creation of all analyzer views."""
        # Mock the _create_view method to return True for all views
        bigquery_views._create_view = MagicMock(return_value=True)

        results = bigquery_views.create_all_analyzer_views()

        # Should create all views defined in the method
        expected_views = [
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

        assert len(results) == len(expected_views)
        for view_name in expected_views:
            assert view_name in results
            assert results[view_name] is True

    def test_sql_view_definitions_not_empty(self, bigquery_views):
        """Test that all SQL view definitions return non-empty strings."""
        sql_methods = [
            bigquery_views._get_search_terms_recommendations_sql,
            bigquery_views._get_keywords_bid_recommendations_sql,
            bigquery_views._get_campaign_performance_insights_sql,
            bigquery_views._get_ad_group_quality_scores_sql,
            bigquery_views._get_geographic_performance_sql,
            bigquery_views._get_local_intent_detection_sql,
            bigquery_views._get_match_type_optimization_sql,
            bigquery_views._get_quality_score_insights_sql,
            bigquery_views._get_cost_efficiency_metrics_sql,
            bigquery_views._get_performance_trends_sql,
            bigquery_views._get_negative_keyword_conflicts_sql,
            bigquery_views._get_budget_allocation_recommendations_sql,
            bigquery_views._get_demographic_performance_insights_sql,
            bigquery_views._get_device_cross_performance_sql,
            bigquery_views._get_seasonal_trend_detection_sql,
        ]

        for method in sql_methods:
            sql = method()
            assert isinstance(sql, str)
            assert len(sql.strip()) > 0
            assert "SELECT" in sql.upper()

    def test_search_terms_recommendations_sql_structure(self, bigquery_views):
        """Test search terms recommendations SQL contains expected elements."""
        sql = bigquery_views._get_search_terms_recommendations_sql()

        # Check for key elements
        assert "search_term" in sql
        assert "campaign_name" in sql
        assert "local_intent_score" in sql
        assert "recommendation_type" in sql
        assert "HIGH_PRIORITY_NEGATIVE" in sql
        assert "GROUP BY" in sql
        assert "CURRENT_TIMESTAMP()" in sql

    def test_keywords_bid_recommendations_sql_structure(self, bigquery_views):
        """Test keywords bid recommendations SQL contains expected elements."""
        sql = bigquery_views._get_keywords_bid_recommendations_sql()

        # Check for key elements
        assert "keyword_text" in sql
        assert "keyword_match_type" in sql
        assert "bid_recommendation" in sql
        assert "suggested_max_cpc" in sql
        assert "optimization_priority" in sql
        assert "INCREASE_BID" in sql
        assert "DECREASE_BID" in sql

    def test_campaign_performance_insights_sql_structure(self, bigquery_views):
        """Test campaign performance insights SQL contains expected elements."""
        sql = bigquery_views._get_campaign_performance_insights_sql()

        # Check for key elements
        assert "campaign_name" in sql
        assert "performance_category" in sql
        assert "optimization_recommendation" in sql
        assert "HIGH_PERFORMER" in sql
        assert "cost_per_conversion" in sql
        assert "budget_utilization_percent" in sql

    def test_geographic_performance_sql_structure(self, bigquery_views):
        """Test geographic performance SQL contains expected elements."""
        sql = bigquery_views._get_geographic_performance_sql()

        # Check for key elements
        assert "location_name" in sql
        assert "location_type" in sql
        assert "performance_category" in sql
        assert "bid_recommendation" in sql
        assert "local_strategy" in sql
        assert "conversion_rank" in sql

    def test_negative_keyword_conflicts_sql_structure(self, bigquery_views):
        """Test negative keyword conflicts SQL contains expected elements."""
        sql = bigquery_views._get_negative_keyword_conflicts_sql()

        # Check for key elements
        assert "negative_keyword" in sql
        assert "positive_keyword" in sql
        assert "conflict_type" in sql
        assert "EXACT_CONFLICT" in sql
        assert "PHRASE_CONFLICT" in sql
        assert "BROAD_CONFLICT" in sql
        assert "impact_level" in sql

    def test_sql_injection_protection(self, bigquery_views):
        """Test that SQL queries don't contain obvious injection vulnerabilities."""
        sql_methods = [
            bigquery_views._get_search_terms_recommendations_sql,
            bigquery_views._get_keywords_bid_recommendations_sql,
            bigquery_views._get_campaign_performance_insights_sql,
        ]

        for method in sql_methods:
            sql = method()
            # Basic checks for SQL injection patterns
            assert ";" not in sql.replace(
                "';'", ""
            )  # Allow legitimate semicolons in strings
            assert "--" not in sql
            assert "/*" not in sql
            assert "xp_" not in sql.lower()
            assert "sp_" not in sql.lower()

    def test_sql_parameter_substitution(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test that SQL parameter substitution is safe and works correctly."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        # Test with safe project and dataset IDs
        test_sql = "SELECT * FROM `{project_id}.{dataset_id}.test_table`"
        substituted = bigquery_views._substitute_sql_parameters(test_sql)

        assert "{project_id}" not in substituted
        assert "{dataset_id}" not in substituted
        assert "test-project" in substituted
        assert "test_dataset" in substituted

    def test_sql_parameter_validation_rejects_unsafe_ids(
        self, bigquery_views, mock_bigquery_client
    ):
        """Test that unsafe project/dataset IDs are rejected."""
        bigquery_views.client = mock_bigquery_client

        # Create unsafe dataset reference
        unsafe_dataset_ref = MagicMock()
        unsafe_dataset_ref.project = "test'; DROP TABLE users; --"
        unsafe_dataset_ref.dataset_id = "test_dataset"
        bigquery_views.dataset_ref = unsafe_dataset_ref

        test_sql = "SELECT * FROM `{project_id}.{dataset_id}.test_table`"

        with pytest.raises(ValueError, match="Invalid project_id format"):
            bigquery_views._substitute_sql_parameters(test_sql)

    def test_configuration_usage_in_sql(self, mock_bigquery_exporter):
        """Test that SQL uses configuration values instead of hardcoded ones."""

        # Create custom config
        custom_config = AnalyzerViewConfig(
            high_cost_threshold=75.0, low_cost_threshold=25.0, days_lookback=60
        )

        with patch("paidsearchnav.exports.bigquery_views.BIGQUERY_AVAILABLE", True):
            views = BigQueryAnalyzerViews(mock_bigquery_exporter, custom_config)
            sql = views._get_search_terms_recommendations_sql()

            # Check that custom config values are used
            assert "75.0" in sql  # high_cost_threshold
            assert "25.0" in sql  # low_cost_threshold
            assert "60 DAY" in sql  # days_lookback
            # Should not contain default values
            assert "50 THEN" not in sql
            assert "20 THEN" not in sql
            assert "90 DAY" not in sql

    def test_table_validation(
        self, bigquery_views, mock_bigquery_client, mock_dataset_ref
    ):
        """Test that table validation works correctly."""
        bigquery_views.client = mock_bigquery_client
        bigquery_views.dataset_ref = mock_dataset_ref

        # Mock successful table lookup
        mock_bigquery_client.get_table.return_value = MagicMock()

        results = bigquery_views.validate_required_tables()

        # Should validate all required tables
        expected_tables = [
            "search_terms",
            "keywords",
            "campaigns",
            "ad_groups",
            "geographic_performance",
            "negative_keywords",
            "demographics",
            "device_performance",
        ]

        for table in expected_tables:
            assert table in results
            assert results[table] is True

    def test_cross_join_optimization(self, bigquery_views):
        """Test that expensive CROSS JOIN operations have been optimized."""
        sql = bigquery_views._get_cost_efficiency_metrics_sql()

        # Should not contain actual CROSS JOIN clauses (check for JOIN without comments)
        sql_lines = [
            line.strip()
            for line in sql.split("\n")
            if not line.strip().startswith("--")
        ]
        sql_without_comments = " ".join(sql_lines)
        assert "CROSS JOIN" not in sql_without_comments.upper()

        # Should use window functions instead
        assert "PERCENTILE_CONT" in sql
        assert "OVER (PARTITION BY campaign_type)" in sql

    def test_get_client_caching(self, bigquery_views, mock_bigquery_exporter):
        """Test that client is cached after first call."""
        mock_client = MagicMock()
        mock_bigquery_exporter._get_client.return_value = mock_client

        # First call
        client1 = bigquery_views._get_client()
        # Second call
        client2 = bigquery_views._get_client()

        assert client1 is client2
        mock_bigquery_exporter._get_client.assert_called_once()

    def test_get_dataset_ref_caching(self, bigquery_views, mock_bigquery_exporter):
        """Test that dataset reference is cached after first call."""
        mock_dataset_ref = MagicMock()
        mock_bigquery_exporter._get_dataset_ref.return_value = mock_dataset_ref

        # First call
        ref1 = bigquery_views._get_dataset_ref()
        # Second call
        ref2 = bigquery_views._get_dataset_ref()

        assert ref1 is ref2
        mock_bigquery_exporter._get_dataset_ref.assert_called_once()

    def test_sql_formatting_consistency(self, bigquery_views):
        """Test that SQL queries follow consistent formatting."""
        sql_methods = [
            bigquery_views._get_search_terms_recommendations_sql,
            bigquery_views._get_keywords_bid_recommendations_sql,
            bigquery_views._get_campaign_performance_insights_sql,
        ]

        for method in sql_methods:
            sql = method()
            # Check basic formatting consistency
            assert sql.strip().endswith('"')  # Should end with closing quote
            assert "SELECT" in sql
            assert "FROM" in sql
            # Should have proper indentation (at least some spaces)
            lines = sql.split("\n")
            indented_lines = [line for line in lines if line.startswith("        ")]
            assert len(indented_lines) > 0

    def test_view_parameter_substitution(self, bigquery_views):
        """Test that views contain parameter placeholders."""
        sql_methods = [
            bigquery_views._get_search_terms_recommendations_sql,
            bigquery_views._get_keywords_bid_recommendations_sql,
        ]

        for method in sql_methods:
            sql = method()
            # Should contain parameter placeholders
            assert "{project_id}" in sql
            assert "{dataset_id}" in sql

    @pytest.mark.parametrize(
        "view_name,expected_keywords",
        [
            (
                "search_terms_recommendations",
                ["search_term", "local_intent_score", "recommendation_type"],
            ),
            (
                "keywords_bid_recommendations",
                ["keyword_text", "bid_recommendation", "suggested_max_cpc"],
            ),
            (
                "campaign_performance_insights",
                [
                    "campaign_name",
                    "performance_category",
                    "optimization_recommendation",
                ],
            ),
            (
                "geographic_performance",
                ["location_name", "performance_category", "bid_recommendation"],
            ),
            (
                "negative_keyword_conflicts",
                ["negative_keyword", "conflict_type", "impact_level"],
            ),
        ],
    )
    def test_sql_view_contains_expected_keywords(
        self, bigquery_views, view_name, expected_keywords
    ):
        """Test that specific SQL views contain expected keywords."""
        method_name = f"_get_{view_name}_sql"
        method = getattr(bigquery_views, method_name)
        sql = method()

        for keyword in expected_keywords:
            assert keyword in sql, f"Keyword '{keyword}' not found in {view_name} SQL"

    def test_performance_thresholds_are_reasonable(self, bigquery_views):
        """Test that performance thresholds in SQL are reasonable business values."""
        sql = bigquery_views._get_search_terms_recommendations_sql()

        # Check for reasonable cost thresholds
        assert "50" in sql  # $50 cost threshold
        assert "20" in sql  # $20 cost threshold

        # Check for reasonable CTR thresholds
        assert "0.005" in sql or "0.5" in sql  # 0.5% CTR threshold

        sql = bigquery_views._get_keywords_bid_recommendations_sql()

        # Check for reasonable quality score thresholds
        assert "5" in sql  # Quality score threshold
        assert "100" in sql  # CPA threshold

    def test_date_range_filtering(self, bigquery_views):
        """Test that SQL queries include proper date range filtering."""
        sql_methods = [
            bigquery_views._get_search_terms_recommendations_sql,
            bigquery_views._get_keywords_bid_recommendations_sql,
            bigquery_views._get_campaign_performance_insights_sql,
        ]

        for method in sql_methods:
            sql = method()
            # Should filter for last 90 days
            assert "90 DAY" in sql
            assert "DATE_SUB" in sql
            assert "CURRENT_DATE()" in sql
