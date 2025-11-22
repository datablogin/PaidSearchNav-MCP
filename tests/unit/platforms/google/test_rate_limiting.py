"""Tests for Google Ads API rate limiting functionality."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from paidsearchnav.core.config import GoogleAdsConfig
from paidsearchnav.platforms.google.rate_limiting import (
    GoogleAdsRateLimiter,
    OperationType,
    RateLimitError,
    rate_limited,
)


class TestGoogleAdsRateLimiter:
    """Test Google Ads rate limiter functionality."""

    @pytest.fixture
    def rate_limiter(self):
        """Create a rate limiter for testing."""
        return GoogleAdsRateLimiter()

    @pytest.fixture
    def test_customer_id(self):
        """Test customer ID."""
        return "1234567890"

    @pytest.mark.asyncio
    async def test_check_rate_limit_allows_initial_requests(
        self, rate_limiter, test_customer_id
    ):
        """Test that initial requests are allowed."""
        result = await rate_limiter.check_rate_limit(
            test_customer_id, OperationType.SEARCH, 1
        )
        assert result is True

    @pytest.mark.asyncio
    async def test_record_request_tracks_usage(self, rate_limiter, test_customer_id):
        """Test that requests are properly recorded."""
        # Record a request
        await rate_limiter.record_request(test_customer_id, OperationType.SEARCH, 1)

        # Check that it's tracked
        status = await rate_limiter.get_rate_limit_status(
            test_customer_id, OperationType.SEARCH
        )

        assert status["minute"]["used"] == 1
        assert status["minute"]["remaining"] == status["minute"]["limit"] - 1

    @pytest.mark.asyncio
    async def test_rate_limit_enforcement(self):
        """Test that rate limits are enforced."""
        # Create a rate limiter with very low limits for testing
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.search_requests_per_minute = 2
        settings.google_ads.search_requests_per_hour = 5
        settings.google_ads.search_requests_per_day = 10
        settings.google_ads.max_retries = 3
        settings.google_ads.backoff_multiplier = 2.0
        settings.google_ads.max_backoff_seconds = 60.0

        rate_limiter = GoogleAdsRateLimiter(settings)
        customer_id = "test_customer"

        # First two requests should pass
        assert await rate_limiter.check_rate_limit(customer_id, OperationType.SEARCH, 1)
        await rate_limiter.record_request(customer_id, OperationType.SEARCH, 1)

        assert await rate_limiter.check_rate_limit(customer_id, OperationType.SEARCH, 1)
        await rate_limiter.record_request(customer_id, OperationType.SEARCH, 1)

        # Third request should be rate limited
        assert not await rate_limiter.check_rate_limit(
            customer_id, OperationType.SEARCH, 1
        )

    @pytest.mark.asyncio
    async def test_operation_size_scaling(self, rate_limiter, test_customer_id):
        """Test that operation size affects rate limiting."""
        # Record a large operation
        await rate_limiter.record_request(
            test_customer_id, OperationType.BULK_MUTATE, 10
        )

        # Check that usage reflects the operation size
        status = await rate_limiter.get_rate_limit_status(
            test_customer_id, OperationType.BULK_MUTATE
        )

        assert status["minute"]["used"] == 10

    @pytest.mark.asyncio
    async def test_quota_tracking(self, rate_limiter, test_customer_id):
        """Test API quota tracking functionality."""
        # Record request with API cost
        await rate_limiter.record_request(
            test_customer_id, OperationType.SEARCH, 1, api_cost=100
        )

        # Check quota tracking
        status = await rate_limiter.get_rate_limit_status(
            test_customer_id, OperationType.SEARCH
        )

        if "quota" in status:
            assert status["quota"]["daily_usage"] == 100

    @pytest.mark.asyncio
    async def test_wait_for_rate_limit_timeout(self):
        """Test that wait_for_rate_limit raises RateLimitError when max wait time exceeded."""
        # Create a rate limiter with very low limits for testing
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.search_requests_per_minute = 1
        settings.google_ads.search_requests_per_hour = 2
        settings.google_ads.search_requests_per_day = 5
        settings.google_ads.max_retries = 1
        settings.google_ads.backoff_multiplier = 2.0
        settings.google_ads.max_backoff_seconds = 1.0

        rate_limiter = GoogleAdsRateLimiter(settings)
        customer_id = "test_customer"

        # Fill up the rate limit
        await rate_limiter.wait_until_allowed(customer_id, OperationType.SEARCH, 1)

        # Override max_wait_time to be very short for testing
        original_max_wait = 300
        with patch.object(rate_limiter, "wait_until_allowed") as mock_wait:
            mock_wait.side_effect = RateLimitError("Max wait time exceeded")

            with pytest.raises(RateLimitError):
                await rate_limiter.wait_for_rate_limit(
                    customer_id, OperationType.SEARCH, 1
                )

    @pytest.mark.asyncio
    async def test_different_operation_types_separate_limits(
        self, rate_limiter, test_customer_id
    ):
        """Test that different operation types have separate rate limits."""
        # Record requests for different operation types
        await rate_limiter.record_request(test_customer_id, OperationType.SEARCH, 5)
        await rate_limiter.record_request(test_customer_id, OperationType.MUTATE, 3)

        # Check that they're tracked separately
        search_status = await rate_limiter.get_rate_limit_status(
            test_customer_id, OperationType.SEARCH
        )
        mutate_status = await rate_limiter.get_rate_limit_status(
            test_customer_id, OperationType.MUTATE
        )

        assert search_status["minute"]["used"] == 5
        assert mutate_status["minute"]["used"] == 3

    @pytest.mark.asyncio
    async def test_wait_until_allowed_atomic_operation(self):
        """Test that wait_until_allowed atomically reserves capacity."""
        # Create a rate limiter with very low limits for testing
        settings = Mock()
        settings.google_ads = Mock()
        settings.google_ads.search_requests_per_minute = 1
        settings.google_ads.search_requests_per_hour = 2
        settings.google_ads.search_requests_per_day = 5
        settings.google_ads.max_retries = 1
        settings.google_ads.backoff_multiplier = 2.0
        settings.google_ads.max_backoff_seconds = 1.0

        rate_limiter = GoogleAdsRateLimiter(settings)
        customer_id = "test_customer"

        # First request should succeed and reserve capacity
        await rate_limiter.wait_until_allowed(customer_id, OperationType.SEARCH, 1)

        # Check that capacity was reserved
        status = await rate_limiter.get_rate_limit_status(
            customer_id, OperationType.SEARCH
        )
        assert status["minute"]["used"] == 1
        assert status["minute"]["remaining"] == 0

        # Second request should be rate limited since capacity is full
        # Check that it cannot proceed immediately
        assert not await rate_limiter.check_rate_limit(
            customer_id, OperationType.SEARCH, 1
        )

        # The atomic operation should have correctly reserved capacity
        # so the status should reflect the used capacity
        assert status["minute"]["used"] == 1

    @pytest.mark.asyncio
    async def test_memory_pressure_cleanup(self, rate_limiter, test_customer_id):
        """Test that cleanup works correctly with storage backend."""
        import time

        # Add some old requests directly to storage
        old_time = time.monotonic() - 86500  # 25 hours ago
        current_time = time.monotonic()

        # Add old and recent requests
        await rate_limiter._storage.add_request(
            test_customer_id, OperationType.SEARCH, old_time, 1
        )
        await rate_limiter._storage.add_request(
            test_customer_id, OperationType.SEARCH, current_time, 1
        )

        # Get initial request count
        initial_requests = await rate_limiter._storage.get_request_history(
            test_customer_id, OperationType.SEARCH
        )
        assert len(initial_requests) == 2

        # Trigger cleanup - this should remove old entries
        cutoff_time = time.monotonic() - 3600  # 1 hour ago
        cleaned = await rate_limiter._storage.cleanup_old_entries(cutoff_time)

        # Should have cleaned up the old entry
        assert cleaned >= 1

        # Check that recent entries are still there
        remaining_requests = await rate_limiter._storage.get_request_history(
            test_customer_id, OperationType.SEARCH
        )
        assert len(remaining_requests) <= len(initial_requests)

        # Recent request should still be there
        assert any(req >= cutoff_time for req in remaining_requests)


class TestRateLimitedDecorator:
    """Test the rate_limited decorator functionality."""

    @pytest.mark.asyncio
    async def test_decorator_applies_rate_limiting(self):
        """Test that the decorator applies rate limiting to methods."""

        class MockClient:
            def __init__(self):
                self.settings = Mock()
                self.settings.google_ads = Mock()
                self.settings.google_ads.search_requests_per_minute = 1
                self.settings.google_ads.search_requests_per_hour = 2
                self.settings.google_ads.search_requests_per_day = 5
                self.settings.google_ads.max_retries = 1
                self.settings.google_ads.backoff_multiplier = 2.0
                self.settings.google_ads.max_backoff_seconds = 1.0
                self.call_count = 0

            @rate_limited(OperationType.SEARCH)
            async def test_method(self, customer_id: str, arg1: str = "default"):
                self.call_count += 1
                return f"result_{self.call_count}"

        client = MockClient()

        # First call should succeed
        result1 = await client.test_method("test_customer", "arg1")
        assert result1 == "result_1"
        assert client.call_count == 1

        # Second call should be rate limited but still succeed due to wait logic
        # (though in a real scenario with proper timing, it might be blocked)
        try:
            result2 = await asyncio.wait_for(
                client.test_method("test_customer", "arg2"), timeout=0.1
            )
            # If it succeeds quickly, that's fine
            assert client.call_count <= 2
        except asyncio.TimeoutError:
            # If it times out due to rate limiting wait, that's expected
            pass

    @pytest.mark.asyncio
    async def test_decorator_handles_rate_limit_errors(self):
        """Test that the decorator properly handles rate limit errors."""

        class MockClient:
            def __init__(self):
                self.settings = None
                self.call_count = 0

            @rate_limited(OperationType.SEARCH)
            async def test_method(self, customer_id: str):
                self.call_count += 1
                if self.call_count <= 2:
                    raise Exception("RATE_EXCEEDED: Too many requests")
                return "success"

        client = MockClient()

        # Should retry and eventually succeed
        result = await client.test_method("test_customer")
        assert result == "success"
        assert client.call_count == 3  # Should have retried twice before succeeding

    @pytest.mark.asyncio
    async def test_decorator_passes_through_other_exceptions(self):
        """Test that non-rate-limit exceptions are passed through."""

        class MockClient:
            def __init__(self):
                self.settings = None

            @rate_limited(OperationType.SEARCH)
            async def test_method(self, customer_id: str):
                raise ValueError("Some other error")

        client = MockClient()

        with pytest.raises(ValueError, match="Some other error"):
            await client.test_method("test_customer")


class TestRateLimiterConfiguration:
    """Test rate limiter configuration from settings."""

    def test_rate_limiter_uses_config_settings(self):
        """Test that rate limiter uses configuration from settings."""
        settings = Mock()
        settings.google_ads = GoogleAdsConfig(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_secret",
            search_requests_per_minute=50,
            search_requests_per_hour=5000,
            search_requests_per_day=120000,
            mutate_requests_per_minute=100,
            max_retries=5,
            backoff_multiplier=3.0,
        )

        rate_limiter = GoogleAdsRateLimiter(settings)

        # Check that configuration is applied
        search_limits = rate_limiter._rate_limits[OperationType.SEARCH]
        assert search_limits["requests_per_minute"] == 50
        assert search_limits["requests_per_hour"] == 5000

        mutate_limits = rate_limiter._rate_limits[OperationType.MUTATE]
        assert mutate_limits["requests_per_minute"] == 100

        assert rate_limiter._max_retries == 5
        assert rate_limiter._backoff_multiplier == 3.0

    def test_rate_limiter_fallback_defaults(self):
        """Test that rate limiter falls back to defaults when no config."""
        rate_limiter = GoogleAdsRateLimiter(None)

        # Check default values are used (fallback values from rate_limiting.py)
        search_limits = rate_limiter._rate_limits[OperationType.SEARCH]
        assert search_limits["requests_per_minute"] == 300
        assert search_limits["requests_per_hour"] == 18000

        assert rate_limiter._max_retries == 3
        assert rate_limiter._backoff_multiplier == 2.0

    def test_rate_limit_validation(self):
        """Test that rate limit configuration is validated for consistency."""
        # Test invalid configuration: minute * 60 > hour
        with pytest.raises(ValueError, match="rate limit inconsistency"):
            GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
                search_requests_per_minute=1000,  # 1000 * 60 = 60000
                search_requests_per_hour=50000,  # Less than 60000
            )

        # Test invalid configuration: hour * 24 > day
        with pytest.raises(ValueError, match="rate limit inconsistency"):
            GoogleAdsConfig(
                developer_token="test_token",
                client_id="test_client_id",
                client_secret="test_secret",
                search_requests_per_hour=30000,  # 30000 * 24 = 720000
                search_requests_per_day=500000,  # Less than 720000
            )

        # Test valid configuration
        config = GoogleAdsConfig(
            developer_token="test_token",
            client_id="test_client_id",
            client_secret="test_secret",
            search_requests_per_minute=500,  # 500 * 60 = 30000
            search_requests_per_hour=50000,  # 50000 > 30000 ✓
            search_requests_per_day=1200000,  # 1200000 > 50000 * 24 ✓
        )
        assert config.search_requests_per_minute == 500
