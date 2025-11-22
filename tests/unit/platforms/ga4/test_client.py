"""Unit tests for GA4 Data API client."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav.core.config import GA4Config
from paidsearchnav.platforms.ga4.client import (
    GA4DataClient,
    GA4RateLimitError,
)


class TestGA4DataClient:
    """Test GA4 Data API client functionality."""

    @pytest.fixture
    def ga4_config(self):
        """Create test GA4 configuration."""
        return GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            enable_rate_limiting=True,
            requests_per_minute=60,
            requests_per_hour=3600,
            requests_per_day=86400,
            cache_ttl_seconds=300,
        )

    @pytest.fixture
    def mock_authenticator(self):
        """Create mock authenticator."""
        authenticator = Mock()
        mock_client = Mock()
        authenticator.get_client.return_value = mock_client
        return authenticator, mock_client

    def test_init_without_ga4_api_raises_import_error(self):
        """Test that missing GA4 API library raises ImportError."""
        config = GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,
        )

        with patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", False):
            with pytest.raises(
                ImportError, match="Google Analytics Data API is required"
            ):
                GA4DataClient(config)

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    def test_init_success(self, mock_cache_manager, mock_authenticator, ga4_config):
        """Test successful client initialization."""
        client = GA4DataClient(ga4_config)

        assert client.config == ga4_config
        mock_authenticator.assert_called_once_with(ga4_config)
        mock_cache_manager.assert_called_once_with(ga4_config)
        assert client._client is None
        assert client._request_count == 0

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_get_realtime_metrics_cached_response(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test real-time metrics with cached response."""
        # Mock cache returning data
        cached_data = {"rows": [{"activeUsers": "100"}], "row_count": 1}
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=cached_data)
        mock_cache_manager.return_value = mock_cache_instance

        client = GA4DataClient(ga4_config)

        result = await client.get_realtime_metrics(
            dimensions=["source"],
            metrics=["activeUsers"],
        )

        assert result == cached_data
        mock_cache_instance.get_cached_response.assert_called_once()

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_get_realtime_metrics_api_call(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test real-time metrics with actual API call."""
        # Mock no cached data
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=None)
        mock_cache_instance.store_response = AsyncMock()
        mock_cache_manager.return_value = mock_cache_instance

        # Mock authenticator and client
        mock_client = Mock()
        mock_response = Mock()
        mock_response.row_count = 1
        mock_response.dimension_headers = [Mock(name="source")]
        mock_response.metric_headers = [Mock(name="activeUsers")]
        mock_response.rows = [
            Mock(
                dimension_values=[Mock(value="google")],
                metric_values=[Mock(value="100")],
            )
        ]
        mock_response.metadata = Mock(currency_code="USD", time_zone="UTC")

        mock_client.run_realtime_report.return_value = mock_response
        mock_authenticator_instance = Mock()
        mock_authenticator_instance.get_client.return_value = mock_client
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        result = await client.get_realtime_metrics(
            dimensions=["source"],
            metrics=["activeUsers"],
        )

        # Verify API was called
        mock_client.run_realtime_report.assert_called_once()

        # Verify response was formatted and cached
        assert "rows" in result
        assert result["row_count"] == 1
        mock_cache_instance.store_response.assert_called_once()

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_get_realtime_metrics_rate_limit_error(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test rate limit error handling."""
        from paidsearchnav.platforms.ga4.client import TooManyRequests

        # Mock no cached data
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=None)
        mock_cache_manager.return_value = mock_cache_instance

        # Mock rate limit exception
        mock_client = Mock()
        mock_client.run_realtime_report.side_effect = TooManyRequests("Rate limited")
        mock_authenticator_instance = Mock()
        mock_authenticator_instance.get_client.return_value = mock_client
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        with pytest.raises(GA4RateLimitError, match="GA4 API rate limit exceeded"):
            await client.get_realtime_metrics(
                dimensions=["source"],
                metrics=["activeUsers"],
            )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_get_historical_metrics_success(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test successful historical metrics retrieval."""
        # Mock no cached data
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=None)
        mock_cache_instance.store_response = AsyncMock()
        mock_cache_manager.return_value = mock_cache_instance

        # Mock successful API response
        mock_client = Mock()
        mock_response = Mock()
        mock_response.row_count = 2
        mock_response.dimension_headers = [Mock(name="source"), Mock(name="medium")]
        mock_response.metric_headers = [Mock(name="sessions")]
        mock_response.rows = [
            Mock(
                dimension_values=[Mock(value="google"), Mock(value="cpc")],
                metric_values=[Mock(value="150")],
            ),
            Mock(
                dimension_values=[Mock(value="facebook"), Mock(value="social")],
                metric_values=[Mock(value="75")],
            ),
        ]
        mock_response.metadata = Mock(currency_code="USD", time_zone="UTC")

        mock_client.run_report.return_value = mock_response
        mock_authenticator_instance = Mock()
        mock_authenticator_instance.get_client.return_value = mock_client
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        result = await client.get_historical_metrics(
            start_date="2025-01-01",
            end_date="2025-01-07",
            dimensions=["source", "medium"],
            metrics=["sessions"],
        )

        # Verify API was called
        mock_client.run_report.assert_called_once()

        # Verify response format
        assert "rows" in result
        assert result["row_count"] == 2
        assert len(result["rows"]) == 2
        assert result["rows"][0]["source"] == "google"
        assert result["rows"][0]["sessions"] == "150"

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    def test_test_connection_success(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test successful connection test."""
        # Mock successful connection test
        mock_client = Mock()
        mock_client.run_report.return_value = Mock()

        mock_authenticator_instance = Mock()
        mock_authenticator_instance.test_authentication.return_value = True
        mock_authenticator_instance.validate_property_access.return_value = True
        mock_authenticator_instance.get_client.return_value = mock_client
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        success, message = client.test_connection()

        assert success is True
        assert "successful" in message.lower()

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    def test_test_connection_auth_failure(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test connection test with authentication failure."""
        mock_authenticator_instance = Mock()
        mock_authenticator_instance.test_authentication.return_value = False
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        success, message = client.test_connection()

        assert success is False
        assert "authentication failed" in message.lower()

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    def test_get_request_stats(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test request statistics retrieval."""
        client = GA4DataClient(ga4_config)
        client._request_count = 5
        client._last_request_time = 1234567890.0

        stats = client.get_request_stats()

        assert stats["total_requests"] == 5
        assert stats["last_request_time"] == 1234567890.0
        assert stats["property_id"] == "123456789"
        assert stats["rate_limiting_enabled"] is True


class TestGA4DataClientRateLimiting:
    """Test rate limiting functionality in GA4 client."""

    @pytest.fixture
    def rate_limited_config(self):
        """Create config with strict rate limiting."""
        return GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            enable_rate_limiting=True,
            requests_per_minute=2,  # Very low for testing
            requests_per_hour=120,  # 2 * 60 = 120
            requests_per_day=2880,  # 120 * 24 = 2880
        )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_rate_limiting_enforced(
        self, mock_cache_manager, mock_authenticator, rate_limited_config
    ):
        """Test that rate limiting is enforced."""
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=None)
        mock_cache_manager.return_value = mock_cache_instance

        client = GA4DataClient(rate_limited_config)

        # Mock time to control rate limiting
        with patch("time.time") as mock_time:
            # Simulate rapid successive calls
            mock_time.return_value = 1000.0
            client._last_request_time = 999.5  # Recent request

            # Should trigger rate limiting sleep
            with patch("asyncio.sleep") as mock_sleep:
                await client._check_rate_limits()
                mock_sleep.assert_called_once()
                # Verify sleep time is reasonable
                sleep_time = mock_sleep.call_args[0][0]
                assert 0 < sleep_time <= 30  # Should be between 0 and 30 seconds

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    def test_track_request_updates_counters(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test that request tracking updates counters."""
        client = GA4DataClient(ga4_config)

        initial_count = client._request_count
        client._track_request()

        assert client._request_count == initial_count + 1
        assert client._last_request_time > 0


class TestGA4ClientValidation:
    """Test input validation in GA4 client."""

    @pytest.fixture
    def ga4_config(self):
        """Create test GA4 configuration."""
        return GA4Config(
            enabled=True,
            property_id="123456789",
            use_application_default_credentials=True,
            requests_per_minute=10,
            requests_per_hour=600,
            requests_per_day=14400,
        )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_invalid_dimensions_raises_error(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test that invalid dimensions raise validation error."""
        client = GA4DataClient(ga4_config)

        with pytest.raises(ValueError, match="Unknown GA4 dimension"):
            await client.get_realtime_metrics(
                dimensions=["invalid_dimension"],
                metrics=["activeUsers"],
            )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_invalid_metrics_raises_error(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test that invalid metrics raise validation error."""
        client = GA4DataClient(ga4_config)

        with pytest.raises(ValueError, match="Unknown GA4 metric"):
            await client.get_realtime_metrics(
                dimensions=["source"],
                metrics=["invalid_metric"],
            )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_invalid_date_range_raises_error(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test that invalid date ranges raise validation error."""
        client = GA4DataClient(ga4_config)

        with pytest.raises(ValueError, match="Invalid date format"):
            await client.get_historical_metrics(
                start_date="invalid-date",
                end_date="2025-01-01",
                dimensions=["source"],
                metrics=["sessions"],
            )

    @patch("paidsearchnav.platforms.ga4.client.GA4_API_AVAILABLE", True)
    @patch("paidsearchnav.platforms.ga4.client.GA4Authenticator")
    @patch("paidsearchnav.platforms.ga4.client.GA4CacheManager")
    @pytest.mark.asyncio
    async def test_pagination_support(
        self, mock_cache_manager, mock_authenticator, ga4_config
    ):
        """Test pagination functionality."""
        # Mock cache returning no data
        mock_cache_instance = Mock()
        mock_cache_instance.get_cached_response = AsyncMock(return_value=None)
        mock_cache_instance.store_response = AsyncMock()
        mock_cache_manager.return_value = mock_cache_instance

        # Mock multiple API responses for pagination
        mock_client = Mock()
        responses = [
            # First batch (full)
            Mock(
                row_count=2,
                dimension_headers=[Mock(name="source")],
                metric_headers=[Mock(name="sessions")],
                rows=[
                    Mock(
                        dimension_values=[Mock(value="google")],
                        metric_values=[Mock(value="100")],
                    ),
                    Mock(
                        dimension_values=[Mock(value="facebook")],
                        metric_values=[Mock(value="50")],
                    ),
                ],
                metadata=Mock(currency_code="USD"),
            ),
            # Second batch (partial - indicates end)
            Mock(
                row_count=1,
                dimension_headers=[Mock(name="source")],
                metric_headers=[Mock(name="sessions")],
                rows=[
                    Mock(
                        dimension_values=[Mock(value="twitter")],
                        metric_values=[Mock(value="25")],
                    ),
                ],
                metadata=Mock(currency_code="USD"),
            ),
        ]

        mock_client.run_report.side_effect = responses
        mock_authenticator_instance = Mock()
        mock_authenticator_instance.get_client.return_value = mock_client
        mock_authenticator.return_value = mock_authenticator_instance

        client = GA4DataClient(ga4_config)

        result = await client.get_all_historical_metrics(
            start_date="2025-01-01",
            end_date="2025-01-07",
            dimensions=["source"],
            metrics=["sessions"],
            batch_size=2,
            max_results=10,
        )

        # Should have combined data from both batches
        assert result["row_count"] == 3
        assert len(result["rows"]) == 3
        assert result["total_batches"] == 2
        assert result["pagination_complete"] is True
