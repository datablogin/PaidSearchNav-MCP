"""Tests for BigQuery mock infrastructure."""

import asyncio

import pytest

from tests.mocks.bigquery_mock import (
    MockBigQueryClient,
    MockBigQueryExporter,
    MockBigQueryService,
    create_mock_bigquery_config,
    create_test_data_fixtures,
)


class TestBigQueryMocks:
    """Test BigQuery mock infrastructure."""

    def test_mock_bigquery_client_basic_operations(self):
        """Test basic mock BigQuery client operations."""
        client = MockBigQueryClient("test-project")

        # Test dataset operations
        dataset_ref = client.dataset("test_dataset")
        assert dataset_ref.dataset_id == "test_dataset"

        # Dataset should not exist initially
        with pytest.raises(Exception):  # NotFound
            client.get_dataset(dataset_ref)

        # Create dataset
        dataset = client.create_dataset(dataset_ref)
        assert dataset.dataset_id == "test_dataset"

        # Now dataset should exist
        retrieved_dataset = client.get_dataset(dataset_ref)
        assert retrieved_dataset.dataset_id == "test_dataset"

    def test_mock_bigquery_client_table_operations(self):
        """Test mock BigQuery client table operations."""
        client = MockBigQueryClient("test-project")

        # Create dataset first
        dataset_ref = client.dataset("test_dataset")
        client.create_dataset(dataset_ref)

        # Test table operations
        table_ref = dataset_ref.table("test_table")

        # Table should not exist initially
        with pytest.raises(Exception):  # NotFound
            client.get_table(table_ref)

        # Create table
        table = client.create_table(table_ref)
        assert table.table_id == "test_table"
        assert table.dataset_id == "test_dataset"

        # Now table should exist
        retrieved_table = client.get_table(table_ref)
        assert retrieved_table.table_id == "test_table"

    def test_mock_bigquery_client_data_insertion(self):
        """Test mock BigQuery client data insertion."""
        client = MockBigQueryClient("test-project")

        # Create dataset and table
        dataset_ref = client.dataset("test_dataset")
        client.create_dataset(dataset_ref)
        table_ref = dataset_ref.table("test_table")
        table = client.create_table(table_ref)

        # Insert some data
        test_rows = [
            {"id": 1, "name": "test1", "value": 10.5},
            {"id": 2, "name": "test2", "value": 20.5},
        ]

        errors = client.insert_rows_json(table, test_rows)
        assert errors == []  # No errors

        # Check data was stored
        assert len(table.rows) == 2
        assert table.rows[0]["id"] == 1
        assert table.rows[1]["name"] == "test2"

    def test_mock_bigquery_client_query_operations(self):
        """Test mock BigQuery client query operations."""
        client = MockBigQueryClient("test-project")

        # Test simple query
        job = client.query("SELECT 1")
        result = job.result()

        assert len(result) == 1
        assert result[0]["result"] == 1

        # Test usage stats query
        job = client.query("SELECT usage_stats FROM analytics")
        result = job.result()

        assert len(result) == 1
        assert "daily_cost_usd" in result[0]
        assert "queries_today" in result[0]

    @pytest.mark.asyncio
    async def test_mock_bigquery_service_basic_functionality(self):
        """Test mock BigQuery service basic functionality."""
        config = create_mock_bigquery_config("premium", True)
        service = MockBigQueryService(config)

        # Test properties
        assert service.is_enabled is True
        assert service.is_premium is True
        assert service.is_enterprise is False
        assert service.supports_advanced_analytics() is True
        assert service.supports_ml_models() is False

        # Test health check
        health = await service.health_check()
        assert health["status"] == "healthy"
        assert health["connectivity"] is True
        assert health["permissions"] is True

    @pytest.mark.asyncio
    async def test_mock_bigquery_service_enterprise_features(self):
        """Test mock BigQuery service enterprise features."""
        config = create_mock_bigquery_config("enterprise", True)
        service = MockBigQueryService(config)

        # Test properties
        assert service.is_enterprise is True
        assert service.supports_ml_models() is True

        # Test ML analytics
        recommendations = await service.analytics.get_keyword_bid_recommendations(
            "test_customer", 0.02
        )
        assert len(recommendations) >= 1
        assert "confidence" in recommendations[0]
        assert "recommended_bid" in recommendations[0]

    @pytest.mark.asyncio
    async def test_mock_bigquery_service_disabled_state(self):
        """Test mock BigQuery service when disabled."""
        config = create_mock_bigquery_config("standard", False)
        service = MockBigQueryService(config)

        # Test properties
        assert service.is_enabled is False
        assert service.supports_advanced_analytics() is False

        # Test operations return disabled status
        health = await service.health_check()
        assert health["status"] == "disabled"

        usage = await service.get_usage_stats("test_customer")
        assert usage["status"] == "disabled"

    @pytest.mark.asyncio
    async def test_mock_bigquery_service_error_scenarios(self):
        """Test mock BigQuery service error scenarios."""
        config = create_mock_bigquery_config("premium", True)
        config.project_id = "failing-project"  # Trigger failures
        service = MockBigQueryService(config)

        # Health check should fail
        health = await service.health_check()
        assert health["status"] == "unhealthy"
        assert health["connectivity"] is False
        assert "errors" in health

    @pytest.mark.asyncio
    async def test_mock_bigquery_service_cost_monitoring(self):
        """Test mock BigQuery service cost monitoring."""
        config = create_mock_bigquery_config("premium", True)
        service = MockBigQueryService(config)

        # Test normal customer
        alerts = await service.cost_monitor.check_cost_alerts("normal_customer")
        assert alerts["cost_percentage"] < 50
        assert len(alerts["alerts"]) == 0

        # Test high-cost customer
        alerts = await service.cost_monitor.check_cost_alerts("high_cost_customer")
        assert alerts["cost_percentage"] > 80
        assert len(alerts["alerts"]) > 0
        assert alerts["alerts"][0]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_mock_bigquery_exporter_functionality(self):
        """Test mock BigQuery exporter functionality."""
        config = create_mock_bigquery_config("premium", True)
        exporter = MockBigQueryExporter(config)

        # Test connection validation
        is_valid = await exporter.validate_connection()
        assert is_valid is True

        # Test audit results export
        test_data = [
            {"audit_id": "test1", "customer_id": "cust1", "cost": 100.0},
            {"audit_id": "test2", "customer_id": "cust1", "cost": 200.0},
        ]

        result = await exporter.export_audit_results("cust1", test_data)
        assert result.status.name == "COMPLETED"
        assert result.records_exported == 2
        assert "table" in result.metadata

    @pytest.mark.asyncio
    async def test_mock_bigquery_exporter_failure_scenarios(self):
        """Test mock BigQuery exporter failure scenarios."""
        config = create_mock_bigquery_config("premium", True)
        exporter = MockBigQueryExporter(config)

        # Test export failure
        result = await exporter.export_audit_results("failing_customer", [])
        assert result.status.name == "FAILED"
        assert "failure" in result.error_message.lower()

    def test_mock_configuration_utilities(self):
        """Test mock configuration utility functions."""
        # Test premium config
        premium_config = create_mock_bigquery_config("premium", True)
        assert premium_config.tier.value == "premium"
        assert premium_config.enabled is True
        assert premium_config.daily_cost_limit_usd == 100.0

        # Test enterprise config
        enterprise_config = create_mock_bigquery_config("enterprise", True)
        assert enterprise_config.tier.value == "enterprise"
        assert enterprise_config.daily_cost_limit_usd == 500.0
        assert enterprise_config.enable_ml_models is True

        # Test disabled config
        disabled_config = create_mock_bigquery_config("standard", False)
        assert disabled_config.enabled is False

    def test_test_data_fixtures(self):
        """Test test data fixture generation."""
        fixtures = create_test_data_fixtures()

        # Test small dataset
        small_data = fixtures["small_dataset"]
        assert "search_terms" in small_data
        assert "keywords" in small_data
        assert len(small_data["search_terms"]) == 1
        assert len(small_data["keywords"]) == 1

        # Test large dataset
        large_data = fixtures["large_dataset"]
        assert len(large_data["search_terms"]) == 1000

    @pytest.mark.asyncio
    async def test_mock_analytics_functionality(self):
        """Test mock analytics functionality."""
        config = create_mock_bigquery_config("premium", True)
        service = MockBigQueryService(config)

        # Test search terms insights
        insights = await service.analytics.get_search_terms_insights(
            "test_customer", 30
        )
        assert len(insights) >= 1
        assert "search_term" in insights[0]
        assert "total_cost" in insights[0]
        assert "conversion_rate" in insights[0]

        # Test bid recommendations (enterprise only)
        config_enterprise = create_mock_bigquery_config("enterprise", True)
        service_enterprise = MockBigQueryService(config_enterprise)

        recommendations = (
            await service_enterprise.analytics.get_keyword_bid_recommendations(
                "test_customer", 0.02
            )
        )
        assert len(recommendations) >= 1
        assert "keyword" in recommendations[0]
        assert "recommended_bid" in recommendations[0]

    def test_mock_failure_simulation(self):
        """Test mock failure simulation capabilities."""
        client = MockBigQueryClient("test-project")

        # Create table
        dataset_ref = client.dataset("test_dataset")
        client.create_dataset(dataset_ref)
        table_ref = dataset_ref.table("test_table")
        table = client.create_table(table_ref)

        # Simulate insertion failure
        table_key = f"{table.dataset_id}.{table.table_id}"
        client.simulate_failure("insert", table_key)

        # Insert should now fail
        test_rows = [{"id": 1, "name": "test"}]
        errors = client.insert_rows_json(table, test_rows)
        assert len(errors) > 0
        assert "error" in errors[0]

        # Clear failures
        client.clear_failures()

        # Insert should now succeed
        errors = client.insert_rows_json(table, test_rows)
        assert len(errors) == 0

    @pytest.mark.asyncio
    async def test_concurrent_mock_operations(self):
        """Test concurrent operations with mock services."""
        config = create_mock_bigquery_config("premium", True)
        service = MockBigQueryService(config)

        # Run multiple concurrent operations
        tasks = [
            service.health_check(),
            service.get_usage_stats("customer1"),
            service.get_usage_stats("customer2"),
            service.analytics.get_search_terms_insights("customer1", 30),
            service.cost_monitor.check_cost_alerts("customer1"),
        ]

        results = await asyncio.gather(*tasks)

        # All should succeed
        assert len(results) == 5
        assert results[0]["status"] == "healthy"  # health check
        assert "daily_cost_usd" in results[1]  # usage stats
        assert "daily_cost_usd" in results[2]  # usage stats
        assert len(results[3]) >= 1  # analytics
        assert "cost_percentage" in results[4]  # cost alerts
