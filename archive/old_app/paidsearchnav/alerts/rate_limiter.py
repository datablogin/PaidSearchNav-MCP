"""Rate limiting for alert system to prevent spam."""

import asyncio
import time
from collections import deque
from dataclasses import dataclass
from typing import Deque, Dict, Optional, Tuple

from .models import Alert, AlertPriority, AlertType


@dataclass
class RateLimitBucket:
    """Rate limiting bucket for tracking alert frequency."""

    timestamps: Deque[float]
    max_requests: int
    window_seconds: int

    def __post_init__(self):
        """Initialize deque if not provided."""
        if not isinstance(self.timestamps, deque):
            self.timestamps = deque()

    def is_allowed(self, current_time: float) -> bool:
        """Check if a request is allowed based on rate limits.

        Args:
            current_time: Current timestamp

        Returns:
            True if request is allowed
        """
        # Remove old timestamps outside the window
        cutoff_time = current_time - self.window_seconds
        while self.timestamps and self.timestamps[0] <= cutoff_time:
            self.timestamps.popleft()

        # Check if we're under the limit
        if len(self.timestamps) < self.max_requests:
            self.timestamps.append(current_time)
            return True

        return False

    def get_retry_after(self, current_time: float) -> float:
        """Get time to wait before next request is allowed.

        Args:
            current_time: Current timestamp

        Returns:
            Seconds to wait, 0 if allowed now
        """
        if not self.timestamps:
            return 0.0

        oldest_timestamp = self.timestamps[0]
        retry_after = oldest_timestamp + self.window_seconds - current_time
        return max(0.0, retry_after)


class AlertRateLimiter:
    """Rate limiter for alerts with configurable policies."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize rate limiter.

        Args:
            config: Optional configuration dictionary
        """
        self.config = config or {}

        # Default rate limits
        self.default_limits = {
            # Global limits
            "global_per_minute": self.config.get(
                "global_per_minute", self.config.get("max_alerts_per_minute", 60)
            ),
            "global_per_hour": self.config.get("max_alerts_per_hour", 1000),
            # Per-type limits
            "error_per_minute": self.config.get("error_alerts_per_minute", 20),
            "warning_per_minute": self.config.get("warning_alerts_per_minute", 30),
            "performance_per_minute": self.config.get(
                "performance_alerts_per_minute", 10
            ),
            "security_per_minute": self.config.get("security_alerts_per_minute", 5),
            # Per-priority limits
            "critical_per_minute": 100,  # Critical alerts get higher limits
            "high_per_minute": self.config.get("high_priority_per_minute", 40),
            "medium_per_minute": self.config.get("medium_priority_per_minute", 30),
            "low_per_minute": self.config.get("low_priority_per_minute", 20),
            # Per-source limits
            "source_per_minute": self.config.get("source_alerts_per_minute", 15),
            # Per-customer limits
            "customer_per_minute": self.config.get("customer_alerts_per_minute", 25),
        }

        # Rate limiting buckets
        self._buckets: Dict[str, RateLimitBucket] = {}
        self._lock = asyncio.Lock()

        # Statistics
        self.stats = {
            "total_requests": 0,
            "allowed_requests": 0,
            "rate_limited_requests": 0,
            "start_time": time.time(),
        }

    async def is_allowed(self, alert: Alert) -> Tuple[bool, Optional[float]]:
        """Check if alert is allowed based on rate limits.

        Args:
            alert: Alert to check

        Returns:
            Tuple of (is_allowed, retry_after_seconds)
        """
        async with self._lock:
            current_time = time.time()
            self.stats["total_requests"] += 1

            # Critical alerts bypass most rate limiting
            if alert.priority == AlertPriority.CRITICAL:
                # Only check global hourly limit for critical alerts
                if not self._check_bucket(
                    "global_hour",
                    current_time,
                    self.default_limits["global_per_hour"],
                    3600,
                ):
                    self.stats["rate_limited_requests"] += 1
                    return False, self._get_retry_after("global_hour", current_time)

                self.stats["allowed_requests"] += 1
                return True, None

            # Check multiple rate limit buckets
            checks = [
                # Global limits
                ("global_minute", self.default_limits["global_per_minute"], 60),
                ("global_hour", self.default_limits["global_per_hour"], 3600),
                # Type-based limits
                (f"type_{alert.type.value}", self._get_type_limit(alert.type), 60),
                # Priority-based limits
                (
                    f"priority_{alert.priority.value}",
                    self._get_priority_limit(alert.priority),
                    60,
                ),
                # Source-based limits
                (
                    f"source_{alert.source}",
                    self.default_limits["source_per_minute"],
                    60,
                ),
            ]

            # Add customer-specific limits if customer_id is available
            if alert.customer_id:
                customer_limit = self.default_limits.get("customer_per_minute", 25)
                checks.append((f"customer_{alert.customer_id}", customer_limit, 60))

            # Check all rate limit buckets
            for bucket_key, max_requests, window_seconds in checks:
                if not self._check_bucket(
                    bucket_key, current_time, max_requests, window_seconds
                ):
                    self.stats["rate_limited_requests"] += 1
                    retry_after = self._get_retry_after(bucket_key, current_time)
                    return False, retry_after

            self.stats["allowed_requests"] += 1
            return True, None

    def _check_bucket(
        self,
        bucket_key: str,
        current_time: float,
        max_requests: int,
        window_seconds: int,
    ) -> bool:
        """Check and update a specific rate limit bucket.

        Args:
            bucket_key: Bucket identifier
            current_time: Current timestamp
            max_requests: Maximum requests in window
            window_seconds: Window size in seconds

        Returns:
            True if request is allowed
        """
        if bucket_key not in self._buckets:
            self._buckets[bucket_key] = RateLimitBucket(
                timestamps=deque(),
                max_requests=max_requests,
                window_seconds=window_seconds,
            )

        bucket = self._buckets[bucket_key]
        return bucket.is_allowed(current_time)

    def _get_retry_after(self, bucket_key: str, current_time: float) -> float:
        """Get retry-after time for a bucket.

        Args:
            bucket_key: Bucket identifier
            current_time: Current timestamp

        Returns:
            Seconds to wait before retry
        """
        if bucket_key in self._buckets:
            return self._buckets[bucket_key].get_retry_after(current_time)
        return 0.0

    def _get_type_limit(self, alert_type: AlertType) -> int:
        """Get rate limit for alert type.

        Args:
            alert_type: Type of alert

        Returns:
            Rate limit per minute
        """
        type_limits = {
            AlertType.ERROR: self.default_limits["error_per_minute"],
            AlertType.WARNING: self.default_limits["warning_per_minute"],
            AlertType.PERFORMANCE: self.default_limits["performance_per_minute"],
            AlertType.SECURITY: self.default_limits["security_per_minute"],
        }
        return type_limits.get(alert_type, 15)  # Default limit

    def _get_priority_limit(self, priority: AlertPriority) -> int:
        """Get rate limit for alert priority.

        Args:
            priority: Alert priority

        Returns:
            Rate limit per minute
        """
        priority_limits = {
            AlertPriority.CRITICAL: self.default_limits["critical_per_minute"],
            AlertPriority.HIGH: self.default_limits["high_per_minute"],
            AlertPriority.MEDIUM: self.default_limits["medium_per_minute"],
            AlertPriority.LOW: self.default_limits["low_per_minute"],
        }
        return priority_limits[priority]

    async def get_stats(self) -> Dict:
        """Get rate limiter statistics.

        Returns:
            Statistics dictionary
        """
        async with self._lock:
            uptime_seconds = time.time() - self.stats["start_time"]

            return {
                "uptime_seconds": uptime_seconds,
                "total_requests": self.stats["total_requests"],
                "allowed_requests": self.stats["allowed_requests"],
                "rate_limited_requests": self.stats["rate_limited_requests"],
                "success_rate": (
                    self.stats["allowed_requests"]
                    / max(1, self.stats["total_requests"])
                ),
                "requests_per_second": (
                    self.stats["total_requests"] / max(1, uptime_seconds)
                ),
                "active_buckets": len(self._buckets),
                "bucket_info": {
                    key: {
                        "current_count": len(bucket.timestamps),
                        "max_requests": bucket.max_requests,
                        "window_seconds": bucket.window_seconds,
                    }
                    for key, bucket in self._buckets.items()
                },
            }

    async def reset(self) -> None:
        """Reset all rate limiting buckets and statistics."""
        async with self._lock:
            self._buckets.clear()
            self.stats = {
                "total_requests": 0,
                "allowed_requests": 0,
                "rate_limited_requests": 0,
                "start_time": time.time(),
            }

    async def cleanup_old_buckets(self, max_age_seconds: int = 3600) -> None:
        """Clean up old, unused buckets to prevent memory leaks.

        Args:
            max_age_seconds: Maximum age for keeping empty buckets
        """
        async with self._lock:
            current_time = time.time()
            cutoff_time = current_time - max_age_seconds

            # Remove buckets that are empty and haven't been used recently
            buckets_to_remove = []
            for bucket_key, bucket in self._buckets.items():
                if not bucket.timestamps and (
                    not hasattr(bucket, "last_used") or bucket.last_used < cutoff_time
                ):
                    buckets_to_remove.append(bucket_key)

            for bucket_key in buckets_to_remove:
                del self._buckets[bucket_key]


class AdaptiveRateLimiter(AlertRateLimiter):
    """Adaptive rate limiter that adjusts limits based on system load."""

    def __init__(self, config: Optional[Dict] = None):
        """Initialize adaptive rate limiter.

        Args:
            config: Optional configuration dictionary
        """
        super().__init__(config)

        # Adaptive configuration
        adaptive_config = config if config is not None else {}
        self.adaptive_config = {
            "enable_adaptation": adaptive_config.get("enable_adaptive_limiting", True),
            "load_threshold_low": adaptive_config.get("load_threshold_low", 0.3),
            "load_threshold_high": adaptive_config.get("load_threshold_high", 0.8),
            "adaptation_factor": adaptive_config.get("adaptation_factor", 0.5),
            "min_limit_factor": adaptive_config.get("min_limit_factor", 0.1),
            "max_limit_factor": adaptive_config.get("max_limit_factor", 2.0),
        }

        # System load tracking (simplified)
        self.system_load = 0.0
        self.load_samples = deque(maxlen=60)  # Track last 60 samples

    def update_system_load(self, load: float) -> None:
        """Update system load metric.

        Args:
            load: System load value (0.0 to 1.0)
        """
        self.system_load = max(0.0, min(1.0, load))
        self.load_samples.append(self.system_load)

    def clear_load_samples(self) -> None:
        """Clear load samples for testing purposes."""
        self.load_samples.clear()

    def get_adaptive_limit(self, base_limit: int) -> int:
        """Get adapted rate limit based on system load.

        Args:
            base_limit: Base rate limit

        Returns:
            Adapted rate limit
        """
        if not self.adaptive_config["enable_adaptation"]:
            return base_limit

        # Calculate average load over recent samples
        if not self.load_samples:
            return base_limit

        avg_load = sum(self.load_samples) / len(self.load_samples)

        # Adjust limit based on load
        if avg_load < self.adaptive_config["load_threshold_low"]:
            # Low load: increase limits
            factor = (
                1.0
                + (self.adaptive_config["load_threshold_low"] - avg_load)
                * self.adaptive_config["adaptation_factor"]
            )
        elif avg_load > self.adaptive_config["load_threshold_high"]:
            # High load: decrease limits
            factor = (
                1.0
                - (avg_load - self.adaptive_config["load_threshold_high"])
                * self.adaptive_config["adaptation_factor"]
            )
        else:
            # Normal load: keep base limits
            factor = 1.0

        # Apply min/max bounds
        factor = max(
            self.adaptive_config["min_limit_factor"],
            min(self.adaptive_config["max_limit_factor"], factor),
        )

        return int(base_limit * factor)

    def _get_type_limit(self, alert_type: AlertType) -> int:
        """Get adapted rate limit for alert type."""
        base_limit = super()._get_type_limit(alert_type)
        return self.get_adaptive_limit(base_limit)

    def _get_priority_limit(self, priority: AlertPriority) -> int:
        """Get adapted rate limit for alert priority."""
        base_limit = super()._get_priority_limit(priority)

        # Don't adapt critical alert limits
        if priority == AlertPriority.CRITICAL:
            return base_limit

        return self.get_adaptive_limit(base_limit)
