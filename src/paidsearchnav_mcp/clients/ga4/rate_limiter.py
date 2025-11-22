"""GA4 API rate limiting and circuit breaker support.

This module provides rate limiting and circuit breaker functionality
specifically for the GA4 Data API integration.
"""

import asyncio
import logging
import random
import time
from datetime import datetime
from functools import wraps
from typing import Any, Callable, Dict, Optional, TypeVar

from circuitbreaker import CircuitBreaker
from paidsearchnav.core.config import CircuitBreakerConfig, GA4Config
from paidsearchnav.platforms.ga4.models import GA4QuotaUsage

try:
    from google.api_core.exceptions import (
        DeadlineExceeded,
        GoogleAPIError,
        ServiceUnavailable,
        TooManyRequests,
    )

    GA4_EXCEPTIONS = (
        GoogleAPIError,
        ServiceUnavailable,
        TooManyRequests,
        DeadlineExceeded,
    )
except ImportError:
    GA4_EXCEPTIONS = (Exception,)

logger = logging.getLogger(__name__)

T = TypeVar("T")


class GA4RateLimiter:
    """Rate limiter for GA4 Data API requests."""

    def __init__(self, config: GA4Config):
        """Initialize GA4 rate limiter.

        Args:
            config: GA4 configuration
        """
        self.config = config
        self._request_times: Dict[str, list] = {}
        self._quota_usage: Dict[str, GA4QuotaUsage] = {}
        self._lock = asyncio.Lock()

    async def check_rate_limit(self, property_id: str) -> bool:
        """Check if request is within rate limits.

        Args:
            property_id: GA4 property ID

        Returns:
            True if request is allowed, False if rate limited
        """
        if not self.config.enable_rate_limiting:
            return True

        async with self._lock:
            current_time = time.time()

            # Initialize tracking for property if needed
            if property_id not in self._request_times:
                self._request_times[property_id] = []
                self._quota_usage[property_id] = GA4QuotaUsage(property_id=property_id)

            request_times = self._request_times[property_id]
            quota = self._quota_usage[property_id]

            # Clean old request times (older than 1 day)
            cutoff_time = current_time - 86400  # 24 hours
            request_times[:] = [t for t in request_times if t > cutoff_time]

            # Check minute limit
            minute_ago = current_time - 60
            recent_minute_requests = sum(1 for t in request_times if t > minute_ago)
            if recent_minute_requests >= self.config.requests_per_minute:
                logger.warning(
                    f"GA4 rate limit exceeded for property {property_id}: "
                    f"{recent_minute_requests} requests in last minute"
                )
                return False

            # Check hourly limit
            hour_ago = current_time - 3600
            recent_hour_requests = sum(1 for t in request_times if t > hour_ago)
            if recent_hour_requests >= self.config.requests_per_hour:
                logger.warning(
                    f"GA4 rate limit exceeded for property {property_id}: "
                    f"{recent_hour_requests} requests in last hour"
                )
                return False

            # Check daily limit
            day_ago = current_time - 86400
            recent_day_requests = sum(1 for t in request_times if t > day_ago)
            if recent_day_requests >= self.config.requests_per_day:
                logger.warning(
                    f"GA4 rate limit exceeded for property {property_id}: "
                    f"{recent_day_requests} requests in last day"
                )
                return False

            return True

    async def record_request(self, property_id: str) -> None:
        """Record a successful request.

        Args:
            property_id: GA4 property ID
        """
        async with self._lock:
            current_time = time.time()

            if property_id not in self._request_times:
                self._request_times[property_id] = []
                self._quota_usage[property_id] = GA4QuotaUsage(property_id=property_id)

            self._request_times[property_id].append(current_time)

            # Update quota usage
            quota = self._quota_usage[property_id]

            # Reset daily counters if new day
            if datetime.utcnow().date() > quota.last_reset_time.date():
                quota.requests_today = 0
                quota.last_reset_time = datetime.utcnow()

            quota.requests_today += 1
            quota.requests_this_hour = sum(
                1 for t in self._request_times[property_id] if t > current_time - 3600
            )
            quota.requests_this_minute = sum(
                1 for t in self._request_times[property_id] if t > current_time - 60
            )

    async def wait_for_rate_limit(self, property_id: str) -> float:
        """Wait until request is within rate limits.

        Args:
            property_id: GA4 property ID

        Returns:
            Time waited in seconds
        """
        wait_time = 0.0
        max_wait = 300.0  # Maximum 5 minutes

        while not await self.check_rate_limit(property_id) and wait_time < max_wait:
            # Calculate optimal wait time
            sleep_time = min(5.0, 60.0 / self.config.requests_per_minute)
            await asyncio.sleep(sleep_time)
            wait_time += sleep_time

        if wait_time >= max_wait:
            raise Exception(f"GA4 rate limit wait timeout for property {property_id}")

        return wait_time

    def get_quota_status(self, property_id: str) -> Optional[GA4QuotaUsage]:
        """Get current quota status for a property.

        Args:
            property_id: GA4 property ID

        Returns:
            Current quota usage or None
        """
        return self._quota_usage.get(property_id)

    def reset_property_limits(self, property_id: str) -> None:
        """Reset rate limits for a property (admin function).

        Args:
            property_id: GA4 property ID to reset
        """
        if property_id in self._request_times:
            del self._request_times[property_id]
        if property_id in self._quota_usage:
            del self._quota_usage[property_id]

        logger.info(f"Reset GA4 rate limits for property {property_id}")


class GA4CircuitBreaker:
    """Circuit breaker specifically for GA4 Data API calls."""

    def __init__(
        self,
        config: GA4Config,
        circuit_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize GA4 circuit breaker.

        Args:
            config: GA4 configuration
            circuit_config: Optional circuit breaker configuration
        """
        self.config = config
        self.circuit_config = circuit_config or CircuitBreakerConfig()

        # Create circuit breaker instance
        self.breaker = CircuitBreaker(
            failure_threshold=self.circuit_config.failure_threshold,
            recovery_timeout=self.circuit_config.recovery_timeout,
            expected_exception=GA4_EXCEPTIONS,
        )

        # Add circuit breaker event handlers
        self.breaker.add_listener(self._on_circuit_open)
        self.breaker.add_listener(self._on_circuit_close)
        self.breaker.add_listener(self._on_circuit_half_open)

    def _on_circuit_open(self) -> None:
        """Handle circuit breaker opening."""
        logger.warning(
            f"GA4 circuit breaker opened for property {self.config.property_id} "
            f"after {self.circuit_config.failure_threshold} failures"
        )

    def _on_circuit_close(self) -> None:
        """Handle circuit breaker closing."""
        logger.info(
            f"GA4 circuit breaker closed for property {self.config.property_id}"
        )

    def _on_circuit_half_open(self) -> None:
        """Handle circuit breaker entering half-open state."""
        logger.info(
            f"GA4 circuit breaker half-open for property {self.config.property_id} - testing recovery"
        )

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to apply circuit breaker to functions.

        Args:
            func: Function to protect with circuit breaker

        Returns:
            Protected function
        """

        @wraps(func)
        def wrapper(*args, **kwargs):
            return self.breaker(func)(*args, **kwargs)

        return wrapper

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is open."""
        return self.breaker.current_state == "open"

    @property
    def is_closed(self) -> bool:
        """Check if circuit breaker is closed."""
        return self.breaker.current_state == "closed"

    @property
    def is_half_open(self) -> bool:
        """Check if circuit breaker is half-open."""
        return self.breaker.current_state == "half-open"

    def get_status(self) -> Dict[str, Any]:
        """Get circuit breaker status.

        Returns:
            Circuit breaker status information
        """
        return {
            "property_id": self.config.property_id,
            "state": self.breaker.current_state,
            "failure_count": self.breaker.failure_count,
            "failure_threshold": self.circuit_config.failure_threshold,
            "recovery_timeout": self.circuit_config.recovery_timeout,
            "last_failure_time": getattr(self.breaker, "last_failure_time", None),
            "next_retry_time": (
                getattr(self.breaker, "last_failure_time", 0)
                + self.circuit_config.recovery_timeout
                if hasattr(self.breaker, "last_failure_time")
                else None
            ),
        }

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        self.breaker.reset()
        logger.info(f"GA4 circuit breaker reset for property {self.config.property_id}")


def ga4_rate_limited(rate_limiter: GA4RateLimiter, property_id: str):
    """Decorator for rate-limited GA4 API calls.

    Args:
        rate_limiter: GA4 rate limiter instance
        property_id: GA4 property ID

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            # Check rate limits
            if not await rate_limiter.check_rate_limit(property_id):
                wait_time = await rate_limiter.wait_for_rate_limit(property_id)
                logger.info(f"GA4 rate limit wait completed: {wait_time:.2f}s")

            try:
                # Execute function
                result = await func(*args, **kwargs)

                # Record successful request
                await rate_limiter.record_request(property_id)

                return result

            except GA4_EXCEPTIONS as e:
                logger.warning(f"GA4 API error in rate-limited call: {e}")
                raise

        return wrapper

    return decorator


def ga4_circuit_breaker(circuit_breaker: GA4CircuitBreaker):
    """Decorator for circuit breaker protected GA4 API calls.

    Args:
        circuit_breaker: GA4 circuit breaker instance

    Returns:
        Decorator function
    """

    def decorator(func: Callable[..., T]) -> Callable[..., T]:
        @wraps(func)
        async def wrapper(*args, **kwargs):
            try:
                # Use circuit breaker protection
                protected_func = circuit_breaker(func)
                return await protected_func(*args, **kwargs)

            except GA4_EXCEPTIONS as e:
                logger.error(f"GA4 API call failed (circuit breaker): {e}")
                raise

        return wrapper

    return decorator


class GA4ResilientClient:
    """GA4 client wrapper with built-in rate limiting and circuit breaker."""

    def __init__(
        self,
        ga4_config: GA4Config,
        circuit_config: Optional[CircuitBreakerConfig] = None,
    ):
        """Initialize resilient GA4 client.

        Args:
            ga4_config: GA4 configuration
            circuit_config: Optional circuit breaker configuration
        """
        self.config = ga4_config
        self.rate_limiter = GA4RateLimiter(ga4_config)
        self.circuit_breaker = GA4CircuitBreaker(ga4_config, circuit_config)

        # Import and create base client
        from paidsearchnav.platforms.ga4.client import GA4DataClient

        self.base_client = GA4DataClient(ga4_config)

    @property
    def property_id(self) -> str:
        """Get property ID."""
        return self.config.property_id

    async def get_realtime_metrics_resilient(
        self,
        dimensions: list[str],
        metrics: list[str],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 1000,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Get real-time metrics with rate limiting and circuit breaker protection.

        Args:
            dimensions: List of dimension names
            metrics: List of metric names
            filters: Optional filters
            limit: Maximum rows to return
            max_retries: Maximum retry attempts

        Returns:
            Real-time metrics data

        Raises:
            Exception: If all retry attempts fail or circuit breaker is open
        """

        @ga4_rate_limited(self.rate_limiter, self.property_id)
        @ga4_circuit_breaker(self.circuit_breaker)
        async def _make_request():
            return await self.base_client.get_realtime_metrics(
                dimensions=dimensions, metrics=metrics, filters=filters, limit=limit
            )

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                return await _make_request()

            except TooManyRequests:
                if attempt < max_retries - 1:
                    # Exponential backoff: 1s, 2s, 4s, etc.
                    wait_time = min(2**attempt, 30)
                    logger.info(
                        f"GA4 rate limited, retrying in {wait_time}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    logger.error("GA4 rate limit exceeded, max retries reached")
                    raise

            except GA4_EXCEPTIONS as e:
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 10) + (random.random() * 2)  # Jitter
                    logger.info(f"GA4 API error, retrying in {wait_time:.1f}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"GA4 API call failed after {max_retries} attempts: {e}"
                    )
                    raise

        raise Exception("GA4 API call failed after all retry attempts")

    async def get_historical_metrics_resilient(
        self,
        start_date: str,
        end_date: str,
        dimensions: list[str],
        metrics: list[str],
        filters: Optional[Dict[str, Any]] = None,
        limit: int = 10000,
        max_retries: int = 3,
    ) -> Dict[str, Any]:
        """Get historical metrics with resilience features.

        Args:
            start_date: Start date
            end_date: End date
            dimensions: List of dimension names
            metrics: List of metric names
            filters: Optional filters
            limit: Maximum rows to return
            max_retries: Maximum retry attempts

        Returns:
            Historical metrics data
        """

        @ga4_rate_limited(self.rate_limiter, self.property_id)
        @ga4_circuit_breaker(self.circuit_breaker)
        async def _make_request():
            return await self.base_client.get_historical_metrics(
                start_date=start_date,
                end_date=end_date,
                dimensions=dimensions,
                metrics=metrics,
                filters=filters,
                limit=limit,
            )

        # Retry logic with exponential backoff
        for attempt in range(max_retries):
            try:
                return await _make_request()

            except TooManyRequests:
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 60)
                    logger.info(
                        f"GA4 rate limited, retrying in {wait_time}s (attempt {attempt + 1})"
                    )
                    await asyncio.sleep(wait_time)
                else:
                    raise

            except GA4_EXCEPTIONS as e:
                if attempt < max_retries - 1:
                    wait_time = min(2**attempt, 30) + (random.random() * 5)
                    logger.info(f"GA4 API error, retrying in {wait_time:.1f}s: {e}")
                    await asyncio.sleep(wait_time)
                else:
                    logger.error(
                        f"GA4 API call failed after {max_retries} attempts: {e}"
                    )
                    raise

        raise Exception("GA4 API call failed after all retry attempts")

    def get_resilience_status(self) -> Dict[str, Any]:
        """Get status of resilience features.

        Returns:
            Resilience status information
        """
        return {
            "property_id": self.property_id,
            "rate_limiting": {
                "enabled": self.config.enable_rate_limiting,
                "quota_status": self.rate_limiter.get_quota_status(self.property_id),
                "limits": {
                    "per_minute": self.config.requests_per_minute,
                    "per_hour": self.config.requests_per_hour,
                    "per_day": self.config.requests_per_day,
                },
            },
            "circuit_breaker": self.circuit_breaker.get_status(),
            "configuration": {
                "max_retries": self.config.max_retries,
                "backoff_multiplier": self.config.backoff_multiplier,
                "max_backoff_seconds": self.config.max_backoff_seconds,
                "request_timeout_seconds": self.config.request_timeout_seconds,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }

    async def test_resilience(self) -> Dict[str, Any]:
        """Test resilience features.

        Returns:
            Test results
        """
        results = {
            "rate_limiter_test": False,
            "circuit_breaker_test": False,
            "connection_test": False,
            "timestamp": datetime.utcnow().isoformat(),
        }

        try:
            # Test rate limiter
            can_make_request = await self.rate_limiter.check_rate_limit(
                self.property_id
            )
            results["rate_limiter_test"] = True
            results["rate_limiter_status"] = (
                "allowed" if can_make_request else "rate_limited"
            )

            # Test circuit breaker status
            results["circuit_breaker_test"] = True
            results["circuit_breaker_state"] = (
                self.circuit_breaker.breaker.current_state
            )

            # Test basic connection (if circuit breaker allows)
            if not self.circuit_breaker.is_open:
                try:
                    connection_result = self.base_client.test_connection()
                    results["connection_test"] = connection_result[0]
                    results["connection_message"] = connection_result[1]
                except Exception as e:
                    results["connection_test"] = False
                    results["connection_message"] = f"Connection test failed: {e}"

            results["overall_status"] = (
                "healthy"
                if all(
                    [
                        results["rate_limiter_test"],
                        results["circuit_breaker_test"],
                        results["connection_test"]
                        or self.circuit_breaker.is_open,  # Open circuit is expected state sometimes
                    ]
                )
                else "degraded"
            )

        except Exception as e:
            logger.error(f"GA4 resilience test failed: {e}")
            results["overall_status"] = "failed"
            results["error"] = str(e)

        return results

    def get_performance_metrics(self) -> Dict[str, Any]:
        """Get performance metrics for the resilient client.

        Returns:
            Performance metrics
        """
        all_quota_status = {}
        for property_id, quota in self.rate_limiter._quota_usage.items():
            all_quota_status[property_id] = quota.dict()

        return {
            "quota_usage": all_quota_status,
            "circuit_breaker_status": self.circuit_breaker.get_status(),
            "configuration": {
                "rate_limiting_enabled": self.config.enable_rate_limiting,
                "circuit_breaker_enabled": self.circuit_config.enabled,
                "failure_threshold": self.circuit_config.failure_threshold,
                "recovery_timeout": self.circuit_config.recovery_timeout,
            },
            "timestamp": datetime.utcnow().isoformat(),
        }
