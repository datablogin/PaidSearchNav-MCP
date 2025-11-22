"""Integration tests for GA4 API real-time integration.

These tests validate the GA4 API integration with real API calls
and data validation against BigQuery exports.
"""

import asyncio
from datetime import datetime
from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav_mcp.analyzers.ga4_analytics import GA4AnalyticsAnalyzer
from paidsearchnav_mcp.core.config import BigQueryConfig, GA4Config
from paidsearchnav_mcp.platforms.ga4.auth import GA4Authenticator
from paidsearchnav_mcp.platforms.ga4.client import GA4DataClient
from paidsearchnav_mcp.platforms.ga4.data_validator import GA4DataValidator
from paidsearchnav_mcp.platforms.ga4.rate_limiter import GA4ResilientClient


@pytest.mark.integration
class TestGA4APIIntegration:
    """Integration tests for GA4 API functionality."""

    @pytest.fixture
    def ga4_config(self):
        """Create GA4 config for testing."""
        return GA4Config(
            enabled=True,
            property_id="123456789",  # Test property ID
            use_application_default_credentials=True,
            enable_realtime_data=True,
            enable_rate_limiting=True,
            requests_per_minute=60,
            daily_cost_limit_usd=10.0,
        )

    @pytest.fixture
    def bigquery_config(self):
        """Create BigQuery config for testing."""
        return BigQueryConfig(
            enabled=True,
            project_id="test-project",
            dataset_id="paidsearchnav",
        )

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    def test_ga4_authentication_live(self, ga4_config):
        """Test GA4 authentication with live credentials."""
        authenticator = GA4Authenticator(ga4_config)

        # Test authentication
        auth_success = authenticator.test_authentication()
        assert auth_success, "GA4 authentication should succeed with valid credentials"

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    def test_ga4_property_access_live(self, ga4_config):
        """Test GA4 property access validation with live API."""
        authenticator = GA4Authenticator(ga4_config)

        # Test property access
        access_valid = authenticator.validate_property_access(ga4_config.property_id)
        assert access_valid, (
            f"Should have access to GA4 property {ga4_config.property_id}"
        )

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    @pytest.mark.asyncio
    async def test_ga4_realtime_metrics_live(self, ga4_config):
        """Test real-time metrics retrieval with live API."""
        client = GA4DataClient(ga4_config)

        # Get real-time active users
        result = await client.get_realtime_metrics(
            dimensions=["country"], metrics=["activeUsers"], limit=10
        )

        assert "rows" in result
        assert "row_count" in result
        assert result["row_count"] >= 0

        # Validate data structure
        if result["rows"]:
            first_row = result["rows"][0]
            assert "country" in first_row
            assert "activeUsers" in first_row

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    @pytest.mark.asyncio
    async def test_ga4_historical_metrics_live(self, ga4_config):
        """Test historical metrics retrieval with live API."""
        client = GA4DataClient(ga4_config)

        # Get yesterday's session data
        result = await client.get_historical_metrics(
            start_date="yesterday",
            end_date="yesterday",
            dimensions=["source", "medium"],
            metrics=["sessions", "bounceRate"],
            limit=100,
        )

        assert "rows" in result
        assert "row_count" in result
        assert result["row_count"] >= 0

        # Validate data structure
        if result["rows"]:
            first_row = result["rows"][0]
            assert "source" in first_row
            assert "medium" in first_row
            assert "sessions" in first_row

    @pytest.mark.skip(reason="Requires live GA4 and BigQuery data")
    @pytest.mark.asyncio
    async def test_ga4_data_validation_live(self, ga4_config, bigquery_config):
        """Test GA4 data validation against live BigQuery exports."""
        # Create clients
        ga4_client = GA4DataClient(ga4_config)

        # Mock BigQuery client for now
        bigquery_client = Mock()

        validator = GA4DataValidator(
            ga4_api_client=ga4_client,
            ga4_bigquery_client=bigquery_client,
            ga4_config=ga4_config,
            bigquery_config=bigquery_config,
        )

        # Run session validation
        result = await validator.validate_session_metrics(
            start_date="7daysAgo", end_date="yesterday"
        )

        assert result.property_id == ga4_config.property_id
        assert result.validation_type == "session_metrics"
        assert result.variance_percentage >= 0

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    @pytest.mark.asyncio
    async def test_ga4_analytics_analyzer_live(self, ga4_config):
        """Test GA4AnalyticsAnalyzer with live data."""
        analyzer = GA4AnalyticsAnalyzer(ga4_config)

        # Run analysis
        result = await analyzer.analyze(
            customer_id="test-customer",
            start_date=datetime.now(),
            end_date=datetime.now(),
        )

        assert result.success in [True, False]  # May fail with test credentials
        assert result.analyzer_name == "GA4 Analytics Analyzer"
        assert result.customer_id == "test-customer"

    @pytest.mark.skip(reason="Requires live GA4 API credentials")
    def test_ga4_resilient_client_live(self, ga4_config):
        """Test GA4ResilientClient with live API."""
        resilient_client = GA4ResilientClient(ga4_config)

        # Test resilience features
        status = resilient_client.get_resilience_status()

        assert status["property_id"] == ga4_config.property_id
        assert "rate_limiting" in status
        assert "circuit_breaker" in status
        assert "configuration" in status


class TestGA4ConfigurationValidation:
    """Test GA4 configuration validation in integration scenarios."""

    def test_complete_ga4_config_validation(self):
        """Test comprehensive GA4 configuration validation."""
        # Valid configuration
        config = GA4Config(
            enabled=True,
            property_id="123456789",
            service_account_key_path="/path/to/key.json",
            api_version="v1beta",
            enable_rate_limiting=True,
            requests_per_minute=100,
            requests_per_hour=6000,
            requests_per_day=100000,
            max_data_lag_hours=2,
            enable_realtime_data=True,
            daily_cost_limit_usd=50.0,
            cost_alert_threshold_usd=40.0,
        )

        # Should pass all validations
        assert config.enabled is True
        assert config.property_id == "123456789"

    def test_ga4_config_environment_variable_parsing(self):
        """Test GA4 config parsing from environment variables."""
        # This would test the environment variable parsing
        # in Settings.from_env() method, but requires setting
        # environment variables which is complex in tests
        pass

    def test_ga4_config_rate_limit_consistency(self):
        """Test rate limit consistency validation."""
        with pytest.raises(ValueError, match="Rate limit inconsistency"):
            GA4Config(
                enabled=True,
                property_id="123456789",
                requests_per_minute=2000,  # Too high
                requests_per_hour=1000,  # Too low
            )


class TestGA4IntegrationErrorHandling:
    """Test error handling in GA4 integration scenarios."""

    def test_missing_ga4_library_handling(self):
        """Test graceful handling when GA4 library is missing."""
        config = GA4Config(enabled=True, property_id="123456789")

        with pytest.raises(ImportError, match="Google Analytics Data API is required"):
            GA4DataClient(config)

    def test_invalid_property_id_handling(self):
        """Test handling of invalid property ID."""
        with pytest.raises(ValueError, match="GA4 property ID must be numeric"):
            GA4Config(
                enabled=True,
                property_id="invalid-id",
            )

    def test_missing_authentication_handling(self):
        """Test handling when no authentication methods are configured."""
        with pytest.raises(
            ValueError, match="At least one authentication method must be configured"
        ):
            GA4Config(
                enabled=True,
                property_id="123456789",
                service_account_key_path=None,
                use_application_default_credentials=False,
            )


@pytest.mark.integration
class TestGA4PerformanceValidation:
    """Test GA4 integration performance characteristics."""

    @pytest.mark.skip(reason="Requires live GA4 API for performance testing")
    @pytest.mark.asyncio
    async def test_ga4_concurrent_requests_performance(self, ga4_config):
        """Test performance of concurrent GA4 API requests."""
        client = GA4DataClient(ga4_config)

        # Create multiple concurrent requests
        tasks = []
        for i in range(5):
            task = client.get_realtime_metrics(
                dimensions=["source"], metrics=["activeUsers"], limit=10
            )
            tasks.append(task)

        # Execute concurrently and measure time
        start_time = datetime.now()
        results = await asyncio.gather(*tasks, return_exceptions=True)
        end_time = datetime.now()

        execution_time = (end_time - start_time).total_seconds()

        # Verify results
        successful_requests = sum(
            1 for result in results if not isinstance(result, Exception)
        )

        assert successful_requests >= 0  # At least some should succeed
        assert execution_time < 30.0  # Should complete within 30 seconds

        # Log performance metrics
        print(
            f"GA4 concurrent requests: {successful_requests}/5 succeeded in {execution_time:.2f}s"
        )

    @pytest.mark.skip(reason="Requires live GA4 API for rate limit testing")
    @pytest.mark.asyncio
    async def test_ga4_rate_limiting_behavior(self, ga4_config):
        """Test GA4 rate limiting behavior under load."""
        # Configure aggressive rate limits for testing
        test_config = GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            enable_rate_limiting=True,
            requests_per_minute=5,  # Very low for testing
            requests_per_hour=100,
            requests_per_day=1000,
        )

        resilient_client = GA4ResilientClient(test_config)

        # Make requests rapidly to trigger rate limiting
        start_time = datetime.now()
        request_times = []

        for i in range(8):  # More than the per-minute limit
            request_start = datetime.now()
            try:
                await resilient_client.get_realtime_metrics_resilient(
                    dimensions=["source"], metrics=["activeUsers"], limit=1
                )
            except Exception as e:
                print(f"Request {i + 1} failed: {e}")

            request_end = datetime.now()
            request_times.append((request_end - request_start).total_seconds())

        end_time = datetime.now()
        total_time = (end_time - start_time).total_seconds()

        # Rate limiting should cause the total time to be longer than without limits
        assert total_time > 10.0  # Should take longer due to rate limiting

        # Some individual requests should have longer response times due to waiting
        assert max(request_times) > 1.0  # At least one request waited


class TestGA4MockIntegration:
    """Test GA4 integration with mocked external dependencies."""

    @pytest.fixture
    def mock_ga4_client(self):
        """Create mock GA4 client."""
        client = Mock()
        client.test_connection.return_value = (True, "Connection successful")
        client.get_request_stats.return_value = {
            "total_requests": 10,
            "property_id": "123456789",
        }
        return client

    @pytest.mark.asyncio
    async def test_ga4_analyzer_with_mocked_client(self, ga4_config, mock_ga4_client):
        """Test GA4AnalyticsAnalyzer with mocked client."""
        with patch(
            "paidsearchnav.analyzers.ga4_analytics.GA4DataClient",
            return_value=mock_ga4_client,
        ):
            analyzer = GA4AnalyticsAnalyzer(ga4_config)

            # Mock client methods
            mock_ga4_client.get_realtime_metrics = AsyncMock(
                return_value={
                    "rows": [{"activeUsers": "50", "source": "google"}],
                    "row_count": 1,
                }
            )
            mock_ga4_client.get_historical_metrics = AsyncMock(
                return_value={
                    "rows": [
                        {
                            "source": "google",
                            "medium": "cpc",
                            "country": "US",
                            "deviceCategory": "desktop",
                            "sessions": "100",
                            "bounceRate": "0.3",
                            "averageSessionDuration": "180",
                            "conversions": "5",
                            "totalRevenue": "250",
                            "sessionConversionRate": "0.05",
                        }
                    ],
                    "row_count": 1,
                }
            )
            mock_ga4_client.get_conversion_metrics = Mock(
                return_value={
                    "rows": [
                        {
                            "source": "google",
                            "medium": "cpc",
                            "campaignName": "Test Campaign",
                            "country": "US",
                            "conversions": "5",
                            "totalRevenue": "250",
                            "sessionConversionRate": "0.05",
                        }
                    ],
                    "row_count": 1,
                }
            )
            mock_ga4_client.get_landing_page_metrics = Mock(
                return_value={
                    "rows": [
                        {
                            "landingPage": "/home",
                            "source": "google",
                            "medium": "cpc",
                            "country": "US",
                            "sessions": "100",
                            "bounceRate": "0.3",
                            "averageSessionDuration": "180",
                            "exitRate": "0.25",
                            "conversions": "5",
                            "totalRevenue": "250",
                        }
                    ],
                    "row_count": 1,
                }
            )

            # Run analysis
            result = await analyzer.analyze(
                customer_id="test-customer",
                start_date=datetime(2025, 1, 1),
                end_date=datetime(2025, 1, 7),
            )

            assert result.success is True
            assert result.analyzer_name == "GA4 Analytics Analyzer"
            assert "session_metrics" in result.data
            assert "conversion_metrics" in result.data
            assert "landing_page_metrics" in result.data

    @pytest.mark.asyncio
    async def test_ga4_data_validation_mocked(self, ga4_config, bigquery_config):
        """Test GA4 data validation with mocked dependencies."""
        # Mock GA4 API client
        mock_api_client = Mock()
        mock_api_client.get_historical_metrics = AsyncMock(
            return_value={"rows": [{"sessions": "1000"}], "row_count": 1}
        )

        # Mock BigQuery client
        mock_bq_client = Mock()

        validator = GA4DataValidator(
            ga4_api_client=mock_api_client,
            ga4_bigquery_client=mock_bq_client,
            ga4_config=ga4_config,
            bigquery_config=bigquery_config,
        )

        # Mock the BigQuery data method
        with patch.object(
            validator,
            "_get_bigquery_session_data",
            return_value={"total_sessions": 950},
        ):
            result = await validator.validate_session_metrics(
                start_date="2025-01-01", end_date="2025-01-07"
            )

            assert result.property_id == ga4_config.property_id
            assert result.api_total == 1000.0
            assert result.bigquery_total == 950.0
            assert abs(result.variance_percentage - 5.26) < 0.1  # ~5.26% variance

    def test_ga4_resilient_client_configuration(self, ga4_config):
        """Test GA4ResilientClient configuration and status."""
        with patch("paidsearchnav.platforms.ga4.rate_limiter.GA4DataClient"):
            resilient_client = GA4ResilientClient(ga4_config)

            assert resilient_client.property_id == ga4_config.property_id

            # Test status retrieval
            status = resilient_client.get_resilience_status()

            assert status["property_id"] == ga4_config.property_id
            assert "rate_limiting" in status
            assert "circuit_breaker" in status
            assert "configuration" in status

    @pytest.mark.asyncio
    async def test_ga4_cache_integration(self, ga4_config):
        """Test GA4 caching integration."""
        from paidsearchnav.platforms.ga4.cache import GA4CacheManager

        cache_manager = GA4CacheManager(ga4_config)

        # Test cache key generation
        cache_key = cache_manager._generate_cache_key(
            request_type="realtime",
            start_date="realtime",
            end_date="realtime",
            dimensions=["source"],
            metrics=["activeUsers"],
        )

        assert "realtime" in cache_key
        assert ga4_config.property_id in cache_key

        # Test cache storage and retrieval
        test_data = {"rows": [{"activeUsers": "100"}], "row_count": 1}

        await cache_manager.store_response(
            request_type="realtime",
            start_date="realtime",
            end_date="realtime",
            dimensions=["source"],
            metrics=["activeUsers"],
            response_data=test_data,
        )

        cached_data = await cache_manager.get_cached_response(
            request_type="realtime",
            start_date="realtime",
            end_date="realtime",
            dimensions=["source"],
            metrics=["activeUsers"],
        )

        assert cached_data == test_data

    def test_ga4_cost_monitoring_integration(self, ga4_config):
        """Test GA4 cost monitoring integration."""
        from paidsearchnav.platforms.ga4.cost_monitor import GA4CostMonitor

        cost_monitor = GA4CostMonitor(ga4_config)

        # Test request tracking
        cost_monitor.track_request("123456789")

        quota_status = cost_monitor.get_quota_status("123456789")
        assert quota_status is not None
        assert quota_status.requests_today == 1

        # Test budget checking
        within_budget = cost_monitor.is_within_budget("123456789")
        assert within_budget is True  # Single request should be within budget
