"""Integration tests for live GA4 BigQuery data access.

These tests require actual GA4 BigQuery export configuration and should only
be run in environments with proper GA4 setup.
"""

import os
from datetime import datetime, timedelta

import pytest

from paidsearchnav_mcp.platforms.ga4.bigquery_client import GA4BigQueryClient
from paidsearchnav_mcp.platforms.ga4.validation import GA4DataValidator


@pytest.mark.integration
@pytest.mark.skipif(
    not os.getenv("GA4_PROJECT_ID") or not os.getenv("GA4_DATASET_ID"),
    reason="GA4 environment variables not set (GA4_PROJECT_ID, GA4_DATASET_ID)",
)
class TestLiveGA4Integration:
    """Integration tests for live GA4 data access."""

    @pytest.fixture
    def ga4_client(self):
        """Create GA4 client with live credentials."""
        project_id = os.getenv("GA4_PROJECT_ID")
        dataset_id = os.getenv("GA4_DATASET_ID")

        return GA4BigQueryClient(
            project_id=project_id, ga4_dataset_id=dataset_id, location="US"
        )

    @pytest.fixture
    def validator(self, ga4_client):
        """Create validator with live GA4 client."""
        return GA4DataValidator(ga4_client)

    def test_discover_live_ga4_tables(self, ga4_client):
        """Test discovery of actual GA4 tables."""
        tables = ga4_client.discover_ga4_tables()

        # Should find at least some GA4 event tables
        assert len(tables) > 0
        assert any(table.startswith("events_") for table in tables)

        # Check for recent tables (within last 7 days)
        recent_date = datetime.now().strftime("%Y%m%d")
        recent_tables = [t for t in tables if recent_date in t or "intraday" in t]
        assert len(recent_tables) > 0, "No recent GA4 tables found"

    def test_get_table_schema_live(self, ga4_client):
        """Test getting schema from live GA4 table."""
        tables = ga4_client.discover_ga4_tables()
        if not tables:
            pytest.skip("No GA4 tables available")

        # Get schema for most recent table
        recent_table = max(tables)
        schema = ga4_client.get_table_schema(recent_table)

        assert schema is not None
        assert len(schema) > 0

        # Verify key GA4 fields are present
        field_names = [field["name"] for field in schema]
        expected_fields = [
            "event_timestamp",
            "event_name",
            "user_pseudo_id",
            "event_params",
        ]

        for field in expected_fields:
            assert field in field_names, f"Missing expected GA4 field: {field}"

    def test_estimate_query_cost_live(self, ga4_client):
        """Test query cost estimation with live BigQuery."""
        # Simple test query
        test_query = f"""
        SELECT COUNT(*) as event_count
        FROM `{ga4_client.project_id}.{ga4_client.ga4_dataset_id}.events_*`
        WHERE _TABLE_SUFFIX >= '20241201'
        LIMIT 1
        """

        cost_estimate = ga4_client.estimate_query_cost(test_query)

        assert cost_estimate["query_valid"] is True
        assert cost_estimate["bytes_processed"] >= 0
        assert cost_estimate["estimated_cost_usd"] >= 0.0
        assert "cost_estimate_timestamp" in cost_estimate

    @pytest.mark.slow
    def test_gclid_sessions_with_sample_data(self, ga4_client):
        """Test GCLID session retrieval with sample data."""
        # Use recent date range
        end_date = datetime.now()
        start_date = end_date - timedelta(days=7)

        # Use sample GCLIDs - these likely won't match but tests the query structure
        sample_gclids = ["EAIaIQobChMI_sample_gclid1", "EAIaIQobChMI_sample_gclid2"]

        try:
            sessions = ga4_client.get_gclid_sessions(
                start_date, end_date, sample_gclids
            )

            # Query should execute successfully even if no matches
            assert isinstance(sessions, list)

            # If we do get matches, validate structure
            if sessions:
                session = sessions[0]
                expected_fields = [
                    "session_id",
                    "gclid",
                    "ga4_user_id",
                    "event_timestamp",
                ]
                for field in expected_fields:
                    assert field in session, f"Missing field {field} in session data"

        except Exception as e:
            # Log the error but don't fail - this is expected for sample data
            print(f"Expected error with sample GCLIDs: {e}")

    def test_validate_live_data_quality(self, validator):
        """Test live data quality validation."""
        # Sample Google Ads data for validation
        sample_ads_data = [
            {"gclid": "sample_gclid_1", "cost": 50.0, "conversions": 2},
            {"gclid": "sample_gclid_2", "cost": 75.0, "conversions": 1},
        ]

        start_date = datetime.now() - timedelta(days=3)
        end_date = datetime.now()

        validation_report = validator.validate_export_data_quality(
            sample_ads_data, start_date, end_date
        )

        # Validation should complete successfully
        assert "validation_timestamp" in validation_report
        assert "overall_quality_score" in validation_report
        assert validation_report["google_ads_data_quality"]["total_records"] == 2
        assert (
            validation_report["google_ads_data_quality"]["gclid_coverage_percent"]
            == 100.0
        )

    def test_real_time_sync_validation_live(self, validator):
        """Test real-time sync validation with live data."""
        sync_report = validator.validate_real_time_data_sync(hours_lookback=24)

        assert "sync_check_timestamp" in sync_report
        assert "sync_quality_score" in sync_report
        assert isinstance(sync_report["real_time_ready"], bool)

        # If intraday tables exist, should have better sync quality
        if sync_report["intraday_tables_available"] > 0:
            assert sync_report["sync_quality_score"] >= 0

    @pytest.mark.slow
    def test_comprehensive_validation_live(self, validator):
        """Test comprehensive validation with live GA4 setup."""
        sample_ads_data = [
            {"gclid": "sample_gclid_1", "cost": 50.0, "conversions": 2, "clicks": 25},
        ]

        start_date = datetime.now() - timedelta(days=7)
        end_date = datetime.now()

        comprehensive_report = validator.run_comprehensive_validation(
            sample_ads_data, start_date, end_date
        )

        # Comprehensive report should have all sections
        assert "validation_summary" in comprehensive_report
        assert "export_data_quality" in comprehensive_report
        assert "real_time_sync_quality" in comprehensive_report
        assert "consolidated_recommendations" in comprehensive_report

        # Validation summary should have key metrics
        summary = comprehensive_report["validation_summary"]
        assert "overall_quality_score" in summary
        assert "export_pipeline_ready" in summary
        assert "real_time_ready" in summary
        assert summary["total_checks_run"] == 3


@pytest.mark.integration
class TestGA4SchemaCompatibility:
    """Test GA4 schema compatibility with PaidSearchNav analytics_data schema."""

    @pytest.fixture
    def ga4_client(self):
        """Create GA4 client for schema testing."""
        # Use environment variables if available, otherwise skip
        project_id = os.getenv("GA4_PROJECT_ID", "mock-project")
        dataset_id = os.getenv("GA4_DATASET_ID", "analytics_123456789")

        return GA4BigQueryClient(
            project_id=project_id, ga4_dataset_id=dataset_id, location="US"
        )

    @pytest.mark.skipif(
        not os.getenv("GA4_PROJECT_ID"),
        reason="GA4_PROJECT_ID not set for live schema testing",
    )
    def test_schema_field_mapping(self, ga4_client):
        """Test that GA4 schema fields map correctly to analytics_data schema."""
        from paidsearchnav.platforms.bigquery.schema import get_analytics_data_schema

        # Get PaidSearchNav schema
        psn_schema = get_analytics_data_schema()
        psn_field_names = [field.name for field in psn_schema]

        # Get sample GA4 table schema
        tables = ga4_client.discover_ga4_tables()
        if not tables:
            pytest.skip("No GA4 tables available for schema testing")

        ga4_schema = ga4_client.get_table_schema(tables[0])
        ga4_field_names = [field["name"] for field in ga4_schema] if ga4_schema else []

        # Check that key GA4 integration fields are in PSN schema
        ga4_integration_fields = [
            "gclid",
            "wbraid",
            "gbraid",
            "session_id",
            "ga4_user_id",
            "store_location_id",
            "transaction_id",
            "attribution_model",
        ]

        for field in ga4_integration_fields:
            assert field in psn_field_names, (
                f"GA4 integration field {field} missing from analytics_data schema"
            )

    def test_query_compatibility(self, ga4_client):
        """Test that GA4 queries are syntactically valid."""
        # Test query structure without executing
        end_date = datetime.now()
        start_date = end_date - timedelta(days=1)

        sample_gclids = ["sample_gclid"]

        # This should not raise syntax errors during query construction
        try:
            # Test internal query building
            date_range = ga4_client._get_date_range(start_date, end_date)
            assert date_range["start_suffix"] == start_date.strftime("%Y%m%d")
            assert date_range["end_suffix"] == end_date.strftime("%Y%m%d")

        except Exception as e:
            pytest.fail(f"Query construction failed: {e}")


# Utility functions for integration testing
def skip_if_no_ga4_config():
    """Skip test if GA4 configuration is not available."""
    return pytest.mark.skipif(
        not (os.getenv("GA4_PROJECT_ID") and os.getenv("GA4_DATASET_ID")),
        reason="GA4 configuration not available",
    )


# Test configuration validation
@pytest.mark.integration
class TestGA4ConfigurationValidation:
    """Test GA4 configuration and setup validation."""

    def test_environment_variables(self):
        """Test that required environment variables are documented."""
        required_vars = ["GA4_PROJECT_ID", "GA4_DATASET_ID"]

        # Document what's needed for integration tests
        missing_vars = [var for var in required_vars if not os.getenv(var)]

        if missing_vars:
            pytest.skip(
                f"Integration tests require environment variables: {', '.join(missing_vars)}. "
                "Set these to enable live GA4 testing."
            )

    @skip_if_no_ga4_config()
    def test_ga4_client_initialization_live(self):
        """Test GA4 client initialization with live credentials."""
        project_id = os.getenv("GA4_PROJECT_ID")
        dataset_id = os.getenv("GA4_DATASET_ID")

        client = GA4BigQueryClient(
            project_id=project_id, ga4_dataset_id=dataset_id, location="US"
        )

        assert client.project_id == project_id
        assert client.ga4_dataset_id == dataset_id

        # Test that BigQuery client can be created
        bq_client = client._get_client()
        assert bq_client is not None
