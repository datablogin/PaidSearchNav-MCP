"""Comprehensive tests for BigQuery service integration."""

import asyncio
from datetime import datetime
from unittest.mock import MagicMock, patch

import pytest

from paidsearchnav_mcp.core.config import BigQueryConfig, BigQueryTier
from paidsearchnav_mcp.platforms.bigquery.service import BigQueryService

# Skip if BigQuery dependencies not available
try:
    from google.cloud.exceptions import Forbidden, GoogleCloudError, NotFound

    BIGQUERY_AVAILABLE = True
except ImportError:
    BIGQUERY_AVAILABLE = False
    GoogleCloudError = Exception
    NotFound = Exception
    Forbidden = Exception

pytestmark = pytest.mark.skipif(
    not BIGQUERY_AVAILABLE, reason="Google Cloud BigQuery not installed"
)


class TestBigQueryServiceIntegration:
    """Integration tests for BigQuery service functionality."""

    @pytest.fixture
    def premium_config(self):
        """BigQuery configuration for premium tier."""
        return BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project-premium",
            dataset_id="premium_analytics",
            location="US",
            service_account_json='{"type": "service_account", "project_id": "test-project"}',
            enable_query_cache=True,
            daily_cost_limit_usd=100.0,
            query_timeout_seconds=300,
        )

    @pytest.fixture
    def enterprise_config(self):
        """BigQuery configuration for enterprise tier."""
        return BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.ENTERPRISE,
            project_id="test-project-enterprise",
            dataset_id="enterprise_analytics",
            location="US",
            service_account_json='{"type": "service_account", "project_id": "test-project"}',
            enable_ml_models=True,
            enable_real_time_streaming=True,
            enable_query_cache=True,
            daily_cost_limit_usd=500.0,
            query_timeout_seconds=600,
        )

    @pytest.fixture
    def disabled_config(self):
        """BigQuery configuration for disabled service."""
        return BigQueryConfig(
            enabled=False,
            tier=BigQueryTier.DISABLED,
            project_id="test-project-disabled",
            dataset_id="disabled_dataset",
        )

    def test_service_initialization_premium(self, premium_config):
        """Test BigQuery service initialization for premium tier."""
        service = BigQueryService(premium_config)

        assert service.is_enabled is True
        assert service.is_premium is True
        assert service.is_enterprise is False
        assert service.supports_advanced_analytics() is True
        assert service.supports_ml_models() is False
        assert service.config.daily_cost_limit_usd == 100.0

    def test_service_initialization_enterprise(self, enterprise_config):
        """Test BigQuery service initialization for enterprise tier."""
        service = BigQueryService(enterprise_config)

        assert service.is_enabled is True
        assert service.is_premium is True
        assert service.is_enterprise is True
        assert service.supports_advanced_analytics() is True
        assert service.supports_ml_models() is True
        assert service.config.daily_cost_limit_usd == 500.0

    def test_service_initialization_disabled(self, disabled_config):
        """Test BigQuery service with disabled configuration."""
        service = BigQueryService(disabled_config)

        assert service.is_enabled is False
        assert service.is_premium is False
        assert service.is_enterprise is False
        assert service.supports_advanced_analytics() is False
        assert service.supports_ml_models() is False

    @pytest.mark.asyncio
    async def test_health_check_success(self, premium_config):
        """Test successful health check."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock successful dataset access
            mock_dataset = MagicMock()
            mock_client_instance.dataset.return_value = mock_dataset
            mock_client_instance.get_dataset.return_value = mock_dataset

            # Mock successful query execution
            mock_client_instance.query.return_value.result.return_value = [
                {"test_result": "success"}
            ]

            health_status = await service.health_check()

            assert health_status["status"] == "healthy"
            assert health_status["connectivity"] is True
            assert health_status["permissions"] is True
            assert health_status["dataset_accessible"] is True
            assert "response_time_ms" in health_status
            assert health_status["response_time_ms"] >= 0

    @pytest.mark.asyncio
    async def test_health_check_connectivity_failure(self, premium_config):
        """Test health check with connectivity failure."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client.side_effect = Exception("Network timeout")

            health_status = await service.health_check()

            assert health_status["status"] == "unhealthy"
            assert health_status["connectivity"] is False
            assert "errors" in health_status
            assert "Network timeout" in str(health_status["errors"])

    @pytest.mark.asyncio
    async def test_health_check_permission_failure(self, premium_config):
        """Test health check with permission failure."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock permission denied
            mock_client_instance.get_dataset.side_effect = Forbidden("Access denied")

            health_status = await service.health_check()

            assert health_status["status"] == "unhealthy"
            assert health_status["connectivity"] is True
            assert health_status["permissions"] is False
            assert "Access denied" in str(health_status["errors"])

    @pytest.mark.asyncio
    async def test_ensure_dataset_exists_success(self, premium_config):
        """Test successful dataset creation/verification."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock dataset exists
            mock_dataset = MagicMock()
            mock_client_instance.get_dataset.return_value = mock_dataset

            result = await service.ensure_dataset_exists()

            assert result is True
            mock_client_instance.get_dataset.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_dataset_exists_create_new(self, premium_config):
        """Test creating new dataset when it doesn't exist."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock dataset doesn't exist, then create succeeds
            mock_client_instance.get_dataset.side_effect = NotFound("Dataset not found")
            mock_dataset = MagicMock()
            mock_client_instance.create_dataset.return_value = mock_dataset

            result = await service.ensure_dataset_exists()

            assert result is True
            mock_client_instance.create_dataset.assert_called_once()

    @pytest.mark.asyncio
    async def test_ensure_dataset_exists_creation_failure(self, premium_config):
        """Test dataset creation failure."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock dataset doesn't exist and creation fails
            mock_client_instance.get_dataset.side_effect = NotFound("Dataset not found")
            mock_client_instance.create_dataset.side_effect = Forbidden(
                "Insufficient permissions"
            )

            result = await service.ensure_dataset_exists()

            assert result is False

    @pytest.mark.asyncio
    async def test_get_usage_stats_success(self, premium_config):
        """Test successful usage statistics retrieval."""
        service = BigQueryService(premium_config)

        with patch.object(service, "_query_usage_stats") as mock_query:
            mock_query.return_value = {
                "daily_cost_usd": 25.50,
                "queries_today": 150,
                "bytes_processed_today": 5368709120,  # 5GB
                "last_query_time": datetime.utcnow(),
            }

            stats = await service.get_usage_stats("customer123")

            assert stats["customer_id"] == "customer123"
            assert stats["daily_cost_usd"] == 25.50
            assert stats["queries_today"] == 150
            assert stats["bytes_processed_today"] == 5368709120
            assert stats["daily_limit_usd"] == 100.0
            assert stats["cost_percentage"] == 25.5
            assert "last_query_time" in stats

    @pytest.mark.asyncio
    async def test_test_permissions_success(self, premium_config):
        """Test successful permissions testing."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock successful permission tests
            mock_client_instance.get_dataset.return_value = MagicMock()
            mock_client_instance.create_table.return_value = MagicMock()
            mock_client_instance.delete_table.return_value = None
            mock_client_instance.query.return_value.result.return_value = []

            permissions = await service.test_permissions()

            assert permissions["dataset_access"] is True
            assert permissions["table_create"] is True
            assert permissions["table_read"] is True
            assert permissions["table_write"] is True
            assert permissions["job_create"] is True
            assert "All required permissions" in permissions["permissions_summary"]

    @pytest.mark.asyncio
    async def test_test_permissions_partial_failure(self, premium_config):
        """Test permissions testing with partial failures."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock dataset access success but table create failure
            mock_client_instance.get_dataset.return_value = MagicMock()
            mock_client_instance.create_table.side_effect = Forbidden(
                "Cannot create tables"
            )

            permissions = await service.test_permissions()

            assert permissions["dataset_access"] is True
            assert permissions["table_create"] is False
            assert "Missing permissions" in permissions["permissions_summary"]

    @pytest.mark.asyncio
    async def test_cost_monitoring_integration(self, premium_config):
        """Test cost monitoring functionality."""
        service = BigQueryService(premium_config)

        # Mock cost monitor
        mock_cost_monitor = MagicMock()
        mock_cost_monitor.check_cost_alerts.return_value = {
            "customer_id": "customer123",
            "current_cost_usd": 85.0,
            "daily_limit_usd": 100.0,
            "cost_percentage": 85.0,
            "alerts": [
                {
                    "level": "warning",
                    "message": "Cost is 85% of daily limit",
                    "timestamp": datetime.utcnow().isoformat(),
                }
            ],
        }

        with patch.object(service, "cost_monitor", mock_cost_monitor):
            alerts = await service.cost_monitor.check_cost_alerts("customer123")

            assert alerts["cost_percentage"] == 85.0
            assert len(alerts["alerts"]) == 1
            assert alerts["alerts"][0]["level"] == "warning"

    @pytest.mark.asyncio
    async def test_analytics_premium_tier(self, premium_config):
        """Test analytics functionality for premium tier."""
        service = BigQueryService(premium_config)

        # Mock analytics
        mock_analytics = MagicMock()
        mock_analytics.get_search_terms_insights.return_value = [
            {
                "search_term": "running shoes",
                "total_cost": 125.50,
                "conversions": 5,
                "conversion_rate": 0.025,
                "recommendation": "increase_bid",
            }
        ]

        with patch.object(service, "analytics", mock_analytics):
            insights = await service.analytics.get_search_terms_insights(
                customer_id="customer123", date_range=30
            )

            assert len(insights) == 1
            assert insights[0]["search_term"] == "running shoes"
            assert insights[0]["conversion_rate"] == 0.025

    @pytest.mark.asyncio
    async def test_ml_models_enterprise_tier(self, enterprise_config):
        """Test ML model functionality for enterprise tier."""
        service = BigQueryService(enterprise_config)

        # Mock ML analytics
        mock_analytics = MagicMock()
        mock_analytics.get_keyword_bid_recommendations.return_value = [
            {
                "keyword": "running shoes",
                "current_bid": 1.50,
                "recommended_bid": 1.75,
                "confidence": 0.85,
                "expected_improvement": "15% increase in conversions",
            }
        ]

        with patch.object(service, "analytics", mock_analytics):
            recommendations = await service.analytics.get_keyword_bid_recommendations(
                customer_id="customer123", performance_threshold=0.02
            )

            assert len(recommendations) == 1
            assert recommendations[0]["confidence"] == 0.85
            assert recommendations[0]["recommended_bid"] == 1.75

    @pytest.mark.asyncio
    async def test_query_timeout_handling(self, premium_config):
        """Test query timeout handling."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock query timeout
            mock_job = MagicMock()
            mock_job.result.side_effect = asyncio.TimeoutError("Query timeout")
            mock_client_instance.query.return_value = mock_job

            with pytest.raises(asyncio.TimeoutError):
                await service._execute_query("SELECT 1", timeout_seconds=1)

    @pytest.mark.asyncio
    async def test_concurrent_operations(self, premium_config):
        """Test concurrent BigQuery operations."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock successful operations
            mock_client_instance.query.return_value.result.return_value = [
                {"result": "success"}
            ]

            # Run multiple operations concurrently
            tasks = [service.get_usage_stats(f"customer{i}") for i in range(5)]

            results = await asyncio.gather(*tasks, return_exceptions=True)

            # All should succeed
            assert len(results) == 5
            for result in results:
                assert not isinstance(result, Exception)

    @pytest.mark.asyncio
    async def test_memory_usage_large_dataset(self, premium_config):
        """Test memory usage with large dataset operations."""
        import os

        import psutil

        service = BigQueryService(premium_config)

        # Get initial memory usage
        process = psutil.Process(os.getpid())
        initial_memory = process.memory_info().rss

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock large dataset
            large_result = [
                {"row": i, "data": f"data_{i}" * 100}  # Large strings
                for i in range(10000)
            ]
            mock_client_instance.query.return_value.result.return_value = large_result

            # Process large dataset
            result = await service._execute_query("SELECT * FROM large_table")

            # Memory should not increase excessively
            final_memory = process.memory_info().rss
            memory_increase = final_memory - initial_memory

            # Memory increase should be reasonable (less than 100MB)
            assert memory_increase < 100 * 1024 * 1024
            assert len(result) == 10000

    @pytest.mark.asyncio
    async def test_error_recovery_mechanisms(self, premium_config):
        """Test error recovery and retry mechanisms."""
        service = BigQueryService(premium_config)

        with patch("google.cloud.bigquery.Client") as mock_client:
            mock_client_instance = MagicMock()
            mock_client.return_value = mock_client_instance

            # Mock transient failure followed by success
            mock_client_instance.query.side_effect = [
                GoogleCloudError("Transient error"),
                GoogleCloudError("Transient error"),
                MagicMock(result=MagicMock(return_value=[{"success": True}])),
            ]

            # Should retry and eventually succeed
            with patch("asyncio.sleep"):  # Speed up retries
                result = await service._execute_query_with_retry(
                    "SELECT 1", max_retries=3
                )

                assert result[0]["success"] is True
                assert mock_client_instance.query.call_count == 3

    @pytest.mark.asyncio
    async def test_service_disabled_operations(self, disabled_config):
        """Test operations when service is disabled."""
        service = BigQueryService(disabled_config)

        # All operations should indicate service is disabled
        health_status = await service.health_check()
        assert health_status["status"] == "disabled"
        assert health_status["enabled"] is False

        # Usage stats should return disabled status
        usage_stats = await service.get_usage_stats("customer123")
        assert usage_stats["status"] == "disabled"
        assert usage_stats["enabled"] is False

        # Permissions should return disabled status
        permissions = await service.test_permissions()
        assert permissions["status"] == "disabled"
        assert permissions["enabled"] is False

    def test_configuration_validation(self):
        """Test BigQuery configuration validation."""
        # Valid premium configuration
        valid_config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="valid-project",
            dataset_id="valid_dataset",
            service_account_json='{"type": "service_account"}',
        )
        service = BigQueryService(valid_config)
        assert service.is_enabled is True

        # Invalid configuration (missing required fields)
        invalid_config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="",  # Empty project ID
            dataset_id="valid_dataset",
        )
        service = BigQueryService(invalid_config)
        # Service should handle invalid config gracefully
        assert hasattr(service, "config")

    @pytest.mark.asyncio
    async def test_cost_limit_enforcement(self, premium_config):
        """Test cost limit enforcement mechanisms."""
        service = BigQueryService(premium_config)

        # Mock cost tracking that exceeds limit
        with patch.object(service, "get_usage_stats") as mock_usage:
            mock_usage.return_value = {
                "customer_id": "customer123",
                "daily_cost_usd": 95.0,  # Close to 100.0 limit
                "daily_limit_usd": 100.0,
                "cost_percentage": 95.0,
            }

            # Query should be allowed (under limit)
            allowed = await service._check_cost_limits(
                "customer123", estimated_cost=3.0
            )
            assert allowed is True

            # Query should be blocked (would exceed limit)
            blocked = await service._check_cost_limits(
                "customer123", estimated_cost=10.0
            )
            assert blocked is False
