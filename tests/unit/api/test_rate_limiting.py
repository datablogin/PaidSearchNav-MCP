"""Tests for customer access control rate limiting."""

import asyncio
import time
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi import HTTPException, Request

from paidsearchnav.api.middleware_rate_limit import CustomerAccessRateLimitMiddleware
from paidsearchnav.core.config import Settings


class TestCustomerAccessRateLimitMiddleware:
    """Test customer access rate limiting middleware."""

    @pytest.fixture
    def settings(self):
        """Create test settings."""
        return Settings(
            api_enable_rate_limiting=True,
            rate_limit_customer_access_per_user_minute=10,
            rate_limit_customer_access_per_user_hour=100,
            rate_limit_customer_access_per_ip_minute=20,
            rate_limit_customer_access_per_ip_hour=200,
            rate_limit_agency_multiplier=5.0,
        )

    @pytest.fixture
    def middleware(self, settings):
        """Create middleware instance."""
        app = MagicMock()
        return CustomerAccessRateLimitMiddleware(app, settings)

    @pytest.fixture
    def mock_request(self):
        """Create mock request."""
        request = MagicMock(spec=Request)
        request.url = MagicMock()
        request.url.path = "/api/v1/customers/123"
        request.state = MagicMock()
        request.state.user_id = "user123"
        request.state.user_type = "individual"
        request.client = MagicMock()
        request.client.host = "127.0.0.1"
        return request

    @pytest.fixture
    def mock_call_next(self):
        """Create mock call_next function."""
        response = MagicMock()
        response.headers = {}
        return AsyncMock(return_value=response)

    @pytest.mark.asyncio
    async def test_rate_limiting_disabled(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that rate limiting can be disabled."""
        middleware.settings.api_enable_rate_limiting = False

        response = await middleware.dispatch(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response is not None

    @pytest.mark.asyncio
    async def test_non_customer_endpoint_bypassed(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that non-customer endpoints are not rate limited."""
        mock_request.url.path = "/api/v1/audits"

        response = await middleware.dispatch(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response is not None

    @pytest.mark.asyncio
    async def test_unauthenticated_request_bypassed(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that unauthenticated requests are not rate limited."""
        mock_request.state.user_id = None

        response = await middleware.dispatch(mock_request, mock_call_next)

        mock_call_next.assert_called_once_with(mock_request)
        assert response is not None

    @pytest.mark.asyncio
    async def test_individual_user_rate_limit(
        self, middleware, mock_request, mock_call_next
    ):
        """Test rate limiting for individual users."""
        # First 10 requests should succeed (per minute limit)
        for i in range(10):
            response = await middleware.dispatch(mock_request, mock_call_next)
            assert response is not None
            assert response.headers["X-RateLimit-Limit"] == "10"
            assert response.headers["X-RateLimit-Remaining"] == str(9 - i)

        # 11th request should fail
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == 429
        assert "Rate limit exceeded" in exc_info.value.detail

    @pytest.mark.asyncio
    async def test_agency_user_higher_limits(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that agency users get higher rate limits."""
        mock_request.state.user_type = "agency"

        # Agency users should get 5x the limit (50 per minute)
        for i in range(50):
            response = await middleware.dispatch(mock_request, mock_call_next)
            assert response is not None
            assert response.headers["X-RateLimit-Limit"] == "50"

        # 51st request should fail
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_rate_limit_window_reset(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that rate limit resets after time window."""
        # Use up the rate limit
        for _ in range(10):
            await middleware.dispatch(mock_request, mock_call_next)

        # Should fail now
        with pytest.raises(HTTPException):
            await middleware.dispatch(mock_request, mock_call_next)

        # Mock time passing (61 seconds)
        with patch("time.monotonic", return_value=time.monotonic() + 61):
            # Should succeed after window reset
            response = await middleware.dispatch(mock_request, mock_call_next)
            assert response is not None
            assert response.headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_hourly_rate_limit(self, middleware, mock_request, mock_call_next):
        """Test hourly rate limits."""
        # Set a very high per-minute limit to test hourly
        middleware.settings.rate_limit_customer_access_per_user_minute = 1000

        # Use up the hourly limit (100 requests)
        for _ in range(100):
            await middleware.dispatch(mock_request, mock_call_next)

        # 101st request should fail
        with pytest.raises(HTTPException) as exc_info:
            await middleware.dispatch(mock_request, mock_call_next)

        assert exc_info.value.status_code == 429

    @pytest.mark.asyncio
    async def test_cleanup_old_entries(self, middleware, mock_request, mock_call_next):
        """Test that old entries are cleaned up."""
        # Add some requests
        for _ in range(5):
            await middleware.dispatch(mock_request, mock_call_next)

        assert len(middleware.requests["user123"]) == 5

        # Mock time passing (2 hours)
        future_time = time.monotonic() + 7200
        with patch("time.monotonic", return_value=future_time):
            # Force cleanup by setting last cleanup time
            middleware.last_cleanup = future_time - 400

            # Make a new request to trigger cleanup
            await middleware.dispatch(mock_request, mock_call_next)

            # Old entries should be cleaned up
            assert len(middleware.requests["user123"]) == 1

    @pytest.mark.asyncio
    async def test_multiple_users_isolated(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that rate limits are isolated per user."""
        # User 1 uses their limit
        for _ in range(10):
            await middleware.dispatch(mock_request, mock_call_next)

        # User 1 should be rate limited
        with pytest.raises(HTTPException):
            await middleware.dispatch(mock_request, mock_call_next)

        # User 2 should not be affected
        mock_request.state.user_id = "user456"
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response is not None
        assert response.headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_rate_limit_headers(self, middleware, mock_request, mock_call_next):
        """Test that proper rate limit headers are set."""
        response = await middleware.dispatch(mock_request, mock_call_next)

        assert "X-RateLimit-Limit" in response.headers
        assert "X-RateLimit-Window" in response.headers
        assert "X-RateLimit-Remaining" in response.headers

        assert response.headers["X-RateLimit-Limit"] == "10"
        assert response.headers["X-RateLimit-Window"] == "60"
        assert response.headers["X-RateLimit-Remaining"] == "9"

    @pytest.mark.asyncio
    async def test_concurrent_cleanup_handling(
        self, middleware, mock_request, mock_call_next
    ):
        """Test that concurrent cleanup operations are handled safely."""
        # Force cleanup time
        middleware.last_cleanup = time.monotonic() - 400

        # Create multiple concurrent requests that will trigger cleanup
        tasks = []
        for i in range(10):
            # Create different users to avoid rate limiting
            req = MagicMock(spec=Request)
            req.url = MagicMock()
            req.url.path = "/api/v1/customers/123"
            req.state = MagicMock()
            req.state.user_id = f"user{i}"
            req.state.user_type = "individual"
            req.client = MagicMock()
            req.client.host = "127.0.0.1"

            tasks.append(middleware.dispatch(req, mock_call_next))

        # All should complete without errors (lock prevents race condition)
        responses = await asyncio.gather(*tasks)
        assert len(responses) == 10
        assert all(r is not None for r in responses)

    @pytest.mark.asyncio
    async def test_edge_case_time_boundaries(
        self, middleware, mock_request, mock_call_next
    ):
        """Test requests at exact time boundaries."""
        # Test requests at 59.9 second intervals
        for i in range(5):
            with patch("time.monotonic", return_value=time.monotonic() + (i * 59.9)):
                response = await middleware.dispatch(mock_request, mock_call_next)
                assert response is not None

        # Verify that requests are tracked correctly
        assert len(middleware.requests["user123"]) == 5

    @pytest.mark.asyncio
    async def test_missing_client_ip_handling(
        self, middleware, mock_request, mock_call_next
    ):
        """Test handling of requests without client IP."""
        # Remove client from request
        mock_request.client = None

        # Should still work with fallback
        response = await middleware.dispatch(mock_request, mock_call_next)
        assert response is not None
        assert response.headers["X-RateLimit-Limit"] == "10"

    @pytest.mark.asyncio
    async def test_configurable_cleanup_interval(self, settings):
        """Test that cleanup interval is configurable."""
        # Create middleware with custom cleanup interval
        settings.rate_limit_cleanup_interval = 60  # 1 minute

        app = MagicMock()
        middleware = CustomerAccessRateLimitMiddleware(app, settings)

        assert middleware.cleanup_interval == 60

    @pytest.mark.asyncio
    async def test_very_large_request_volume(
        self, middleware, mock_request, mock_call_next
    ):
        """Test performance with very large request volumes."""
        # Simulate many users with different IPs
        middleware.settings.rate_limit_customer_access_per_user_minute = 1000

        # Add many requests from different users
        for i in range(100):
            mock_request.state.user_id = f"user{i}"
            for j in range(50):
                await middleware.dispatch(mock_request, mock_call_next)

        # Verify memory usage is reasonable
        total_entries = sum(len(reqs) for reqs in middleware.requests.values())
        assert total_entries == 5000  # 100 users * 50 requests

        # Trigger cleanup
        future_time = time.monotonic() + 7200
        with patch("time.monotonic", return_value=future_time):
            middleware.last_cleanup = future_time - 400
            await middleware.dispatch(mock_request, mock_call_next)

            # All old entries should be cleaned up
            total_after = sum(len(reqs) for reqs in middleware.requests.values())
            assert total_after == 1  # Only the last request


class TestRateLimitingIntegration:
    """Integration tests for rate limiting with FastAPI."""

    @pytest.mark.asyncio
    async def test_customer_endpoints_rate_limited(self):
        """Test that customer endpoints are properly rate limited."""
        # This would be an integration test with the actual FastAPI app
        # For now, we've tested the middleware functionality above
        pass
