"""Tests for alert rate limiter."""

import time

import pytest

from paidsearchnav.alerts.models import Alert, AlertPriority, AlertType
from paidsearchnav.alerts.rate_limiter import (
    AdaptiveRateLimiter,
    AlertRateLimiter,
    RateLimitBucket,
)


class TestRateLimitBucket:
    """Test RateLimitBucket functionality."""

    def test_bucket_creation(self):
        """Test bucket creation."""
        bucket = RateLimitBucket(timestamps=[], max_requests=10, window_seconds=60)

        assert bucket.max_requests == 10
        assert bucket.window_seconds == 60
        assert len(bucket.timestamps) == 0

    def test_is_allowed_empty_bucket(self):
        """Test is_allowed with empty bucket."""
        bucket = RateLimitBucket(timestamps=[], max_requests=5, window_seconds=60)

        current_time = time.time()
        assert bucket.is_allowed(current_time) is True
        assert len(bucket.timestamps) == 1

    def test_is_allowed_under_limit(self):
        """Test is_allowed under the limit."""
        bucket = RateLimitBucket(timestamps=[], max_requests=3, window_seconds=60)

        current_time = time.time()

        # First three requests should be allowed
        assert bucket.is_allowed(current_time) is True
        assert bucket.is_allowed(current_time + 1) is True
        assert bucket.is_allowed(current_time + 2) is True
        assert len(bucket.timestamps) == 3

    def test_is_allowed_over_limit(self):
        """Test is_allowed over the limit."""
        bucket = RateLimitBucket(timestamps=[], max_requests=2, window_seconds=60)

        current_time = time.time()

        # First two requests should be allowed
        assert bucket.is_allowed(current_time) is True
        assert bucket.is_allowed(current_time + 1) is True

        # Third request should be denied
        assert bucket.is_allowed(current_time + 2) is False
        assert len(bucket.timestamps) == 2

    def test_window_cleanup(self):
        """Test cleanup of old timestamps."""
        bucket = RateLimitBucket(timestamps=[], max_requests=5, window_seconds=10)

        current_time = time.time()

        # Add old timestamps
        bucket.timestamps.append(current_time - 20)  # Too old
        bucket.timestamps.append(current_time - 15)  # Too old
        bucket.timestamps.append(current_time - 5)  # Still valid

        # New request should clean old timestamps and be allowed
        assert bucket.is_allowed(current_time) is True
        assert len(bucket.timestamps) == 2  # One valid old + one new

    def test_get_retry_after(self):
        """Test retry-after calculation."""
        bucket = RateLimitBucket(timestamps=[], max_requests=2, window_seconds=60)

        current_time = time.time()

        # Fill bucket
        bucket.is_allowed(current_time)
        bucket.is_allowed(current_time + 1)

        # Check retry-after time
        retry_after = bucket.get_retry_after(current_time + 30)
        assert retry_after > 0
        assert retry_after <= 30  # Should be less than remaining window time


class TestAlertRateLimiter:
    """Test AlertRateLimiter functionality."""

    def test_rate_limiter_creation(self):
        """Test rate limiter creation."""
        limiter = AlertRateLimiter()

        assert limiter.default_limits["global_per_minute"] == 60
        assert limiter.default_limits["critical_per_minute"] == 100
        assert limiter.stats["total_requests"] == 0

    def test_custom_config(self):
        """Test custom configuration."""
        config = {
            "max_alerts_per_minute": 120,
            "error_alerts_per_minute": 30,
        }

        limiter = AlertRateLimiter(config)

        assert limiter.default_limits["global_per_minute"] == 120
        assert limiter.default_limits["error_per_minute"] == 30

    @pytest.mark.asyncio
    async def test_critical_alert_bypass(self):
        """Test that critical alerts bypass most rate limiting."""
        config = {"global_per_hour": 2}  # Very low limit
        limiter = AlertRateLimiter(config)

        # Create critical alert
        critical_alert = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.CRITICAL,
            title="Critical Alert",
            message="Critical message",
            source="TestComponent",
        )

        # Should be allowed even with low limits
        allowed, retry_after = await limiter.is_allowed(critical_alert)
        assert allowed is True
        assert retry_after is None

    @pytest.mark.asyncio
    async def test_rate_limiting_enforcement(self):
        """Test rate limiting enforcement for normal alerts."""
        config = {"global_per_minute": 2}  # Very low limit
        limiter = AlertRateLimiter(config)

        high_alert = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="High Alert",
            message="High priority message",
            source="TestComponent",
        )

        # First two should be allowed
        allowed1, _ = await limiter.is_allowed(high_alert)
        allowed2, _ = await limiter.is_allowed(high_alert)

        assert allowed1 is True
        assert allowed2 is True

        # Third should be rate limited
        allowed3, retry_after = await limiter.is_allowed(high_alert)
        assert allowed3 is False
        assert retry_after is not None
        assert retry_after > 0

    @pytest.mark.asyncio
    async def test_different_alert_types(self):
        """Test rate limiting for different alert types."""
        config = {
            "error_alerts_per_minute": 2,
            "warning_alerts_per_minute": 3,
        }
        limiter = AlertRateLimiter(config)

        error_alert = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Error Alert",
            message="Error message",
            source="TestComponent",
        )

        warning_alert = Alert(
            type=AlertType.WARNING,
            priority=AlertPriority.MEDIUM,
            title="Warning Alert",
            message="Warning message",
            source="TestComponent",
        )

        # Error alerts should hit limit at 2
        for i in range(2):
            allowed, _ = await limiter.is_allowed(error_alert)
            assert allowed is True

        allowed, _ = await limiter.is_allowed(error_alert)
        assert allowed is False

        # Warning alerts should still be allowed (separate bucket)
        allowed, _ = await limiter.is_allowed(warning_alert)
        assert allowed is True

    @pytest.mark.asyncio
    async def test_customer_specific_limits(self):
        """Test customer-specific rate limiting."""
        config = {
            "customer_alerts_per_minute": 2
        }  # Allow 2 per customer to test independence
        limiter = AlertRateLimiter(config)

        alert_customer1 = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Customer 1 Alert",
            message="Message for customer 1",
            source="TestComponent",
            customer_id="customer1",
        )

        alert_customer2 = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Customer 2 Alert",
            message="Message for customer 2",
            source="TestComponent",
            customer_id="customer2",
        )

        # Each customer should have their own limit
        allowed1, _ = await limiter.is_allowed(alert_customer1)
        allowed2, _ = await limiter.is_allowed(alert_customer2)

        assert allowed1 is True
        assert allowed2 is True

        # Second alert for customer 1 should be allowed (within their limit of 2)
        allowed1_second, _ = await limiter.is_allowed(alert_customer1)
        assert allowed1_second is True

        # Customer 2 should also be allowed their second alert (independent limit)
        allowed2_second, _ = await limiter.is_allowed(alert_customer2)
        assert allowed2_second is True

        # Third alert for customer 1 should now be rate limited
        allowed1_third, _ = await limiter.is_allowed(alert_customer1)
        assert allowed1_third is False

    @pytest.mark.asyncio
    async def test_stats_tracking(self):
        """Test statistics tracking."""
        limiter = AlertRateLimiter()

        alert = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Test Alert",
            message="Test message",
            source="TestComponent",
        )

        # Process some alerts
        await limiter.is_allowed(alert)
        await limiter.is_allowed(alert)

        stats = await limiter.get_stats()

        assert stats["total_requests"] == 2
        assert stats["allowed_requests"] == 2
        assert stats["rate_limited_requests"] == 0
        assert stats["success_rate"] == 1.0
        assert stats["uptime_seconds"] > 0

    @pytest.mark.asyncio
    async def test_cleanup_old_buckets(self):
        """Test cleanup of old buckets."""
        limiter = AlertRateLimiter()

        # Create some buckets by processing alerts
        alert = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Test Alert",
            message="Test message",
            source="TestComponent",
        )

        await limiter.is_allowed(alert)

        # Should have buckets now
        stats_before = await limiter.get_stats()
        assert stats_before["active_buckets"] > 0

        # Cleanup (with very short max age for testing)
        await limiter.cleanup_old_buckets(max_age_seconds=0)

        # Note: In real implementation, empty buckets might be cleaned up
        # This test mainly ensures the method doesn't crash


class TestAdaptiveRateLimiter:
    """Test AdaptiveRateLimiter functionality."""

    def test_adaptive_rate_limiter_creation(self):
        """Test adaptive rate limiter creation."""
        limiter = AdaptiveRateLimiter()

        assert limiter.adaptive_config["enable_adaptation"] is True
        assert limiter.system_load == 0.0
        assert len(limiter.load_samples) == 0

    def test_system_load_update(self):
        """Test system load tracking."""
        limiter = AdaptiveRateLimiter()

        # Update system load
        limiter.update_system_load(0.5)
        assert limiter.system_load == 0.5
        assert len(limiter.load_samples) == 1

        # Test bounds checking
        limiter.update_system_load(-0.1)  # Should be clamped to 0.0
        assert limiter.system_load == 0.0

        limiter.update_system_load(1.5)  # Should be clamped to 1.0
        assert limiter.system_load == 1.0

    def test_adaptive_limit_calculation(self):
        """Test adaptive limit calculation."""
        config = {
            "enable_adaptive_limiting": True,
            "load_threshold_low": 0.3,
            "load_threshold_high": 0.8,
            "adaptation_factor": 0.5,
        }

        limiter = AdaptiveRateLimiter(config)
        base_limit = 100

        # Low load should increase limits
        limiter.clear_load_samples()  # Clear any previous samples
        limiter.update_system_load(0.1)
        adapted_limit = limiter.get_adaptive_limit(base_limit)
        assert adapted_limit > base_limit

        # High load should decrease limits
        limiter.clear_load_samples()  # Clear samples to test independently
        limiter.update_system_load(0.9)
        adapted_limit = limiter.get_adaptive_limit(base_limit)
        assert adapted_limit < base_limit

        # Normal load should keep limits unchanged
        limiter.clear_load_samples()  # Clear samples to test independently
        limiter.update_system_load(0.5)
        adapted_limit = limiter.get_adaptive_limit(base_limit)
        assert adapted_limit == base_limit

    def test_critical_alerts_no_adaptation(self):
        """Test that critical alerts are not adapted."""
        config = {"enable_adaptive_limiting": True}
        limiter = AdaptiveRateLimiter(config)

        # Set high load to reduce limits
        limiter.update_system_load(0.95)

        # Critical priority should not be adapted
        critical_limit = limiter._get_priority_limit(AlertPriority.CRITICAL)
        base_critical_limit = limiter.default_limits["critical_per_minute"]

        assert critical_limit == base_critical_limit

        # But high priority should be adapted
        high_limit = limiter._get_priority_limit(AlertPriority.HIGH)
        base_high_limit = limiter.default_limits["high_per_minute"]

        assert high_limit < base_high_limit

    def test_disabled_adaptation(self):
        """Test disabled adaptation."""
        config = {"enable_adaptive_limiting": False}
        limiter = AdaptiveRateLimiter(config)

        base_limit = 100

        # Even with high load, limits should not be adapted
        limiter.update_system_load(0.95)
        adapted_limit = limiter.get_adaptive_limit(base_limit)

        assert adapted_limit == base_limit
