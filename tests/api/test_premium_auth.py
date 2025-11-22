"""Tests for premium authentication and authorization middleware."""

from unittest.mock import MagicMock, patch

import pytest
from fastapi import HTTPException

from paidsearchnav_mcp.api.v1.premium_auth import (
    PremiumRateLimiter,
    PremiumTierInfo,
    UsageTracker,
    check_premium_rate_limit,
    get_customer_id_from_user,
    reset_usage_tracking,
    usage_tracker,
    validate_premium_access,
    validate_query_cost,
)
from paidsearchnav_mcp.core.config import BigQueryTier


@pytest.fixture
def mock_request():
    """Mock FastAPI request."""
    request = MagicMock()
    request.url.path = "/api/v1/premium/analytics/search-terms"
    return request


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "sub": "test_user",
        "customer_id": "test_customer_123",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_premium_settings():
    """Mock settings with premium BigQuery tier."""
    settings = MagicMock()
    settings.bigquery.enabled = True
    settings.bigquery.tier = BigQueryTier.PREMIUM
    settings.bigquery.daily_cost_limit_usd = 100.0
    settings.bigquery.query_timeout_seconds = 300
    return settings


@pytest.fixture
def mock_enterprise_settings():
    """Mock settings with enterprise BigQuery tier."""
    settings = MagicMock()
    settings.bigquery.enabled = True
    settings.bigquery.tier = BigQueryTier.ENTERPRISE
    settings.bigquery.daily_cost_limit_usd = 500.0
    settings.bigquery.query_timeout_seconds = 600
    settings.bigquery.enable_ml_models = True
    return settings


@pytest.fixture
def mock_disabled_settings():
    """Mock settings with disabled BigQuery."""
    settings = MagicMock()
    settings.bigquery.enabled = False
    settings.bigquery.tier = BigQueryTier.DISABLED
    return settings


@pytest.fixture(autouse=True)
def reset_tracking():
    """Reset usage tracking before each test."""
    reset_usage_tracking()
    yield
    reset_usage_tracking()


class TestUsageTracker:
    """Test usage tracking functionality."""

    def test_track_request(self):
        """Test tracking API requests."""
        tracker = UsageTracker()

        tracker.track_request("customer_123", "/analytics/search-terms", 0.05)
        tracker.track_request("customer_123", "/analytics/keywords", 0.03)
        tracker.track_request("customer_123", "/analytics/search-terms", 0.02)

        usage = tracker.get_daily_usage("customer_123")

        assert usage["requests"] == 3
        assert usage["cost_estimate"] == 0.10
        assert usage["endpoints"]["/analytics/search-terms"] == 2
        assert usage["endpoints"]["/analytics/keywords"] == 1

    def test_get_daily_usage_empty(self):
        """Test getting usage for customer with no requests."""
        tracker = UsageTracker()

        usage = tracker.get_daily_usage("new_customer")

        assert usage["requests"] == 0
        assert usage["cost_estimate"] == 0.0
        assert usage["endpoints"] == {}

    def test_check_limits_within_bounds(self):
        """Test checking limits when within bounds."""
        tracker = UsageTracker()

        # Track some requests but stay within limits
        for i in range(50):
            tracker.track_request("customer_123", "/analytics/search-terms", 0.01)

        limits = tracker.check_limits("customer_123", BigQueryTier.PREMIUM)

        assert limits["within_limits"] is True
        assert limits["remaining"]["requests"] == 9950  # 10000 - 50
        assert limits["remaining"]["cost_budget"] == 99.5  # 100.0 - 0.5

    def test_check_limits_exceeded_requests(self):
        """Test checking limits when request limit exceeded."""
        tracker = UsageTracker()

        # Track requests exceeding the limit
        for i in range(10001):
            tracker.track_request("customer_123", "/analytics/search-terms", 0.001)

        limits = tracker.check_limits("customer_123", BigQueryTier.PREMIUM)

        assert limits["within_limits"] is False
        assert limits["remaining"]["requests"] == 0

    def test_check_limits_exceeded_cost(self):
        """Test checking limits when cost limit exceeded."""
        tracker = UsageTracker()

        # Track requests exceeding cost limit
        tracker.track_request("customer_123", "/analytics/search-terms", 150.0)

        limits = tracker.check_limits("customer_123", BigQueryTier.PREMIUM)

        assert limits["within_limits"] is False
        assert limits["remaining"]["cost_budget"] == 0

    def test_enterprise_vs_premium_limits(self):
        """Test different limits for enterprise vs premium tiers."""
        tracker = UsageTracker()

        # Track same usage for both tiers
        for i in range(15000):
            tracker.track_request("customer_premium", "/analytics/search-terms", 0.01)
            tracker.track_request(
                "customer_enterprise", "/analytics/search-terms", 0.01
            )

        premium_limits = tracker.check_limits("customer_premium", BigQueryTier.PREMIUM)
        enterprise_limits = tracker.check_limits(
            "customer_enterprise", BigQueryTier.ENTERPRISE
        )

        # Premium should be over limit, enterprise should be within
        assert premium_limits["within_limits"] is False
        assert enterprise_limits["within_limits"] is True


class TestPremiumRateLimiter:
    """Test premium rate limiting functionality."""

    def test_check_rate_limit_within_bounds(self):
        """Test rate limiting when within bounds."""
        limiter = PremiumRateLimiter()

        # Make requests within premium analytics limit (30/min)
        for i in range(25):
            result = limiter.check_rate_limit(
                "customer_123", BigQueryTier.PREMIUM, "analytics"
            )
            assert result is True

    def test_check_rate_limit_exceeded(self):
        """Test rate limiting when limit exceeded."""
        limiter = PremiumRateLimiter()

        # Exceed premium analytics limit (30/min)
        for i in range(31):
            result = limiter.check_rate_limit(
                "customer_123", BigQueryTier.PREMIUM, "analytics"
            )
            if i < 30:
                assert result is True
            else:
                assert result is False

    def test_enterprise_higher_limits(self):
        """Test that enterprise tier has higher rate limits."""
        limiter = PremiumRateLimiter()

        # Make requests that would exceed premium but not enterprise
        for i in range(50):
            premium_result = limiter.check_rate_limit(
                "customer_premium", BigQueryTier.PREMIUM, "analytics"
            )
            enterprise_result = limiter.check_rate_limit(
                "customer_enterprise", BigQueryTier.ENTERPRISE, "analytics"
            )

            if i < 30:
                assert premium_result is True
                assert enterprise_result is True
            elif i < 100:
                assert premium_result is False
                assert enterprise_result is True

    def test_different_endpoint_types(self):
        """Test rate limits for different endpoint types."""
        limiter = PremiumRateLimiter()

        # Test different endpoint types have different limits
        for i in range(70):
            analytics_result = limiter.check_rate_limit(
                "customer_123", BigQueryTier.PREMIUM, "analytics"
            )
            live_result = limiter.check_rate_limit(
                "customer_123", BigQueryTier.PREMIUM, "live"
            )

            if i < 30:
                assert analytics_result is True
            else:
                assert analytics_result is False

            if i < 60:
                assert live_result is True
            else:
                assert live_result is False

    def test_get_remaining_requests(self):
        """Test getting remaining requests count."""
        limiter = PremiumRateLimiter()

        # Make some requests
        for i in range(10):
            limiter.check_rate_limit("customer_123", BigQueryTier.PREMIUM, "analytics")

        remaining = limiter.get_remaining_requests(
            "customer_123", BigQueryTier.PREMIUM, "analytics"
        )
        assert remaining == 20  # 30 - 10


class TestPremiumAccessValidation:
    """Test premium access validation."""

    @pytest.mark.asyncio
    async def test_validate_premium_access_success(
        self, mock_request, mock_user, mock_premium_settings
    ):
        """Test successful premium access validation."""
        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings",
                return_value=mock_premium_settings,
            ),
        ):
            tier_info = await validate_premium_access(
                mock_request, mock_user, mock_premium_settings
            )

            assert isinstance(tier_info, PremiumTierInfo)
            assert tier_info.tier == BigQueryTier.PREMIUM
            assert tier_info.features["real_time_analytics"] is True
            assert (
                tier_info.features["ml_recommendations"] is False
            )  # Premium, not Enterprise
            assert tier_info.limits["daily_requests"] == 10000

    @pytest.mark.asyncio
    async def test_validate_premium_access_enterprise(
        self, mock_request, mock_user, mock_enterprise_settings
    ):
        """Test premium access validation for enterprise tier."""
        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings",
                return_value=mock_enterprise_settings,
            ),
        ):
            tier_info = await validate_premium_access(
                mock_request, mock_user, mock_enterprise_settings
            )

            assert tier_info.tier == BigQueryTier.ENTERPRISE
            assert tier_info.features["ml_recommendations"] is True
            assert tier_info.features["unlimited_exports"] is True
            assert tier_info.limits["daily_requests"] == 50000

    @pytest.mark.asyncio
    async def test_validate_premium_access_disabled(
        self, mock_request, mock_user, mock_disabled_settings
    ):
        """Test premium access validation when BigQuery is disabled."""
        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings",
                return_value=mock_disabled_settings,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_premium_access(
                    mock_request, mock_user, mock_disabled_settings
                )

            assert exc_info.value.status_code == 402
            assert "BigQuery integration not enabled" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_premium_access_standard_tier(self, mock_request, mock_user):
        """Test premium access validation with standard tier."""
        settings = MagicMock()
        settings.bigquery.enabled = True
        settings.bigquery.tier = BigQueryTier.STANDARD  # Not premium

        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings", return_value=settings
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_premium_access(mock_request, mock_user, settings)

            assert exc_info.value.status_code == 402
            assert "Premium tier required" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_premium_access_no_customer_id(
        self, mock_request, mock_premium_settings
    ):
        """Test premium access validation when user has no customer ID."""
        user_no_customer = {
            "sub": "test_user",
            "email": "test@example.com",
        }  # No customer_id

        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=user_no_customer,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings",
                return_value=mock_premium_settings,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_premium_access(
                    mock_request, user_no_customer, mock_premium_settings
                )

            assert exc_info.value.status_code == 400
            assert "Customer ID not found" in str(exc_info.value.detail)

    @pytest.mark.asyncio
    async def test_validate_premium_access_usage_limit_exceeded(
        self, mock_request, mock_user, mock_premium_settings
    ):
        """Test premium access validation when usage limit exceeded."""
        # Pre-populate usage to exceed limits
        for i in range(10001):
            usage_tracker.track_request("test_customer_123", "/test", 0.001)

        with (
            patch(
                "paidsearchnav.api.v1.premium_auth.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.api.v1.premium_auth.get_settings",
                return_value=mock_premium_settings,
            ),
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_premium_access(
                    mock_request, mock_user, mock_premium_settings
                )

            assert exc_info.value.status_code == 429
            assert "Usage limit exceeded" in str(exc_info.value.detail)


class TestCustomerIdExtraction:
    """Test customer ID extraction from user context."""

    @pytest.mark.asyncio
    async def test_get_customer_id_success(self, mock_user):
        """Test successful customer ID extraction."""
        with patch(
            "paidsearchnav.api.v1.premium_auth.get_current_user", return_value=mock_user
        ):
            customer_id = await get_customer_id_from_user(mock_user)
            assert customer_id == "test_customer_123"

    @pytest.mark.asyncio
    async def test_get_customer_id_missing(self):
        """Test customer ID extraction when missing."""
        user_no_customer = {"sub": "test_user", "email": "test@example.com"}

        with patch(
            "paidsearchnav.api.v1.premium_auth.get_current_user",
            return_value=user_no_customer,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await get_customer_id_from_user(user_no_customer)

            assert exc_info.value.status_code == 400
            assert "Customer ID not found" in str(exc_info.value.detail)


class TestQueryCostValidation:
    """Test query cost validation."""

    @pytest.mark.asyncio
    async def test_validate_query_cost_within_limits(self, mock_premium_settings):
        """Test query cost validation when within limits."""
        premium_info = PremiumTierInfo(
            tier=BigQueryTier.PREMIUM,
            features={},
            limits={"daily_cost_limit": 100.0},
            usage={"cost_estimate": 50.0},
        )

        # 1GB query should cost ~$0.005
        estimated_bytes = 1024 * 1024 * 1024

        with patch(
            "paidsearchnav.api.v1.premium_auth.get_settings",
            return_value=mock_premium_settings,
        ):
            cost = await validate_query_cost(
                estimated_bytes, mock_premium_settings, premium_info
            )
            assert cost < 0.01  # Should be very small cost

    @pytest.mark.asyncio
    async def test_validate_query_cost_exceeds_limit(self, mock_premium_settings):
        """Test query cost validation when exceeding limits."""
        premium_info = PremiumTierInfo(
            tier=BigQueryTier.PREMIUM,
            features={},
            limits={"daily_cost_limit": 100.0},
            usage={"cost_estimate": 99.0},  # Already used most of budget
        )

        # Very large query
        estimated_bytes = 1024 * 1024 * 1024 * 1024  # 1TB

        with patch(
            "paidsearchnav.api.v1.premium_auth.get_settings",
            return_value=mock_premium_settings,
        ):
            with pytest.raises(HTTPException) as exc_info:
                await validate_query_cost(
                    estimated_bytes, mock_premium_settings, premium_info
                )

            assert exc_info.value.status_code == 429
            assert "Cost limit exceeded" in str(exc_info.value.detail)


class TestPremiumRateLimitCheck:
    """Test premium rate limit checking."""

    @pytest.mark.asyncio
    async def test_check_premium_rate_limit_success(self, mock_request):
        """Test successful rate limit check."""
        premium_info = PremiumTierInfo(
            tier=BigQueryTier.PREMIUM, features={}, limits={}, usage={}
        )

        # Should not raise exception for first request
        await check_premium_rate_limit(
            mock_request, "analytics", premium_info, "test_customer_123"
        )

    @pytest.mark.asyncio
    async def test_check_premium_rate_limit_exceeded(self, mock_request):
        """Test rate limit check when limit exceeded."""
        premium_info = PremiumTierInfo(
            tier=BigQueryTier.PREMIUM, features={}, limits={}, usage={}
        )

        # Exceed rate limit
        for i in range(31):
            if i < 30:
                await check_premium_rate_limit(
                    mock_request, "analytics", premium_info, "test_customer_123"
                )
            else:
                with pytest.raises(HTTPException) as exc_info:
                    await check_premium_rate_limit(
                        mock_request, "analytics", premium_info, "test_customer_123"
                    )

                assert exc_info.value.status_code == 429
                assert "Rate limit exceeded" in str(exc_info.value.detail)


class TestUtilityFunctions:
    """Test utility functions."""

    def test_get_usage_summary(self):
        """Test getting usage summary."""
        # Track some usage
        usage_tracker.track_request("customer_123", "/analytics", 0.05)
        usage_tracker.track_request("customer_123", "/exports", 0.02)

        from paidsearchnav.api.v1.premium_auth import get_usage_summary

        summary = get_usage_summary("customer_123")

        assert summary["requests"] == 2
        assert summary["cost_estimate"] == 0.07
        assert len(summary["endpoints"]) == 2

    def test_reset_usage_tracking(self):
        """Test resetting usage tracking."""
        # Track some usage
        usage_tracker.track_request("customer_123", "/analytics", 0.05)

        # Verify usage exists
        summary = usage_tracker.get_daily_usage("customer_123")
        assert summary["requests"] == 1

        # Reset and verify cleared
        from paidsearchnav.api.v1.premium_auth import reset_usage_tracking

        reset_usage_tracking()

        # Check that global tracker was reset
        from paidsearchnav.api.v1.premium_auth import usage_tracker as new_tracker

        new_summary = new_tracker.get_daily_usage("customer_123")
        assert new_summary["requests"] == 0
