"""Google Ads API rate limiting with quota tracking and exponential backoff.

This module implements proactive rate limiting for Google Ads API operations to prevent
API quota exhaustion and improve reliability for large accounts.

Key Features:
- Configurable rate limits per operation type
- API quota tracking and monitoring
- Exponential backoff with jitter
- Bulk operation protection
- Per-customer rate limiting
- Integration with existing circuit breaker
"""

import asyncio
import logging
import time
from enum import Enum
from typing import Any, Callable, Dict, Optional

from paidsearchnav.core.config import Settings
from paidsearchnav.core.exceptions import RateLimitError
from paidsearchnav.platforms.google.storage import (
    RateLimitStorageBackend,
    create_storage_backend,
)
from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_random,
)

logger = logging.getLogger(__name__)


class OperationType(Enum):
    """Google Ads API operation types with different rate limit requirements."""

    SEARCH = "search"
    MUTATE = "mutate"
    REPORT = "report"
    BULK_MUTATE = "bulk_mutate"
    ACCOUNT_INFO = "account_info"


class GoogleAdsRateLimiter:
    """
    Rate limiter for Google Ads API operations with quota tracking.

    Implements per-customer, per-operation-type rate limiting with
    exponential backoff and API quota monitoring.
    """

    def __init__(self, settings: Optional[Settings] = None):
        """Initialize the rate limiter with configuration.

        Args:
            settings: Application settings for rate limit configuration
        """
        self.settings = settings or Settings()

        # Initialize storage backend (Redis or in-memory)
        redis_config = getattr(self.settings, "redis", None)
        self._storage: RateLimitStorageBackend = create_storage_backend(redis_config)

        # Rate limit configuration per operation type
        google_ads_config = getattr(self.settings, "google_ads", None)

        if google_ads_config:
            self._rate_limits = {
                OperationType.SEARCH: {
                    "requests_per_minute": google_ads_config.search_requests_per_minute,
                    "requests_per_hour": google_ads_config.search_requests_per_hour,
                    "requests_per_day": google_ads_config.search_requests_per_day,
                },
                OperationType.MUTATE: {
                    "requests_per_minute": google_ads_config.mutate_requests_per_minute,
                    "requests_per_hour": google_ads_config.mutate_requests_per_hour,
                    "requests_per_day": google_ads_config.mutate_requests_per_day,
                },
                OperationType.REPORT: {
                    "requests_per_minute": google_ads_config.report_requests_per_minute,
                    "requests_per_hour": google_ads_config.report_requests_per_hour,
                    "requests_per_day": google_ads_config.report_requests_per_day,
                },
                OperationType.BULK_MUTATE: {
                    "requests_per_minute": google_ads_config.bulk_requests_per_minute,
                    "requests_per_hour": google_ads_config.bulk_requests_per_hour,
                    "requests_per_day": google_ads_config.bulk_requests_per_day,
                },
                OperationType.ACCOUNT_INFO: {
                    "requests_per_minute": google_ads_config.account_requests_per_minute,
                    "requests_per_hour": google_ads_config.account_requests_per_hour,
                    "requests_per_day": google_ads_config.account_requests_per_day,
                },
            }

            # Store backoff configuration
            self._max_retries = google_ads_config.max_retries
            self._backoff_multiplier = google_ads_config.backoff_multiplier
            self._max_backoff = google_ads_config.max_backoff_seconds
        else:
            # Fallback defaults if no config (must match GoogleAdsConfig defaults)
            self._rate_limits = {
                OperationType.SEARCH: {
                    "requests_per_minute": 300,
                    "requests_per_hour": 18000,
                    "requests_per_day": 432000,
                },
                OperationType.MUTATE: {
                    "requests_per_minute": 100,
                    "requests_per_hour": 6000,
                    "requests_per_day": 144000,
                },
                OperationType.REPORT: {
                    "requests_per_minute": 133,
                    "requests_per_hour": 7980,
                    "requests_per_day": 191520,
                },
                OperationType.BULK_MUTATE: {
                    "requests_per_minute": 15,
                    "requests_per_hour": 900,
                    "requests_per_day": 21600,
                },
                OperationType.ACCOUNT_INFO: {
                    "requests_per_minute": 80,
                    "requests_per_hour": 4800,
                    "requests_per_day": 115200,
                },
            }

            # Default backoff configuration
            self._max_retries = 3
            self._backoff_multiplier = 2.0
            self._max_backoff = 60.0

        # Cleanup interval for old request history
        self._cleanup_interval = 300  # 5 minutes
        self._last_cleanup = time.monotonic()

    async def check_rate_limit(
        self, customer_id: str, operation_type: OperationType, operation_size: int = 1
    ) -> bool:
        """Check if a request can proceed without violating rate limits.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation being performed
            operation_size: Size of the operation (e.g., number of mutations)

        Returns:
            True if request can proceed, False if rate limited
        """
        await self._cleanup_old_entries()

        now = time.monotonic()
        limits = self._rate_limits[operation_type]

        # Get request history from storage backend
        requests = await self._storage.get_request_history(customer_id, operation_type)

        # Check different time windows
        windows = [
            ("minute", 60, limits["requests_per_minute"]),
            ("hour", 3600, limits["requests_per_hour"]),
            ("day", 86400, limits["requests_per_day"]),
        ]

        for window_name, window_seconds, limit in windows:
            window_start = now - window_seconds
            recent_requests = [ts for ts in requests if ts > window_start]

            # Account for operation size (e.g., bulk operations count more)
            total_operations = len(recent_requests) + operation_size

            if total_operations > limit:
                logger.warning(
                    f"Rate limit exceeded for {customer_id} {operation_type.value}: "
                    f"{total_operations}/{limit} in {window_name}"
                )
                return False

        return True

    async def _check_and_reserve_capacity(
        self, customer_id: str, operation_type: OperationType, operation_size: int = 1
    ) -> bool:
        """Atomically check rate limit and reserve capacity if allowed.

        This prevents race conditions where multiple instances check the limit
        simultaneously and exceed the actual limit when recording.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation being performed
            operation_size: Size of the operation

        Returns:
            True if capacity was successfully reserved, False if rate limited
        """
        await self._cleanup_old_entries()

        now = time.monotonic()
        limits = self._rate_limits[operation_type]

        # Get request history from storage backend
        requests = await self._storage.get_request_history(customer_id, operation_type)

        # Check different time windows
        windows = [
            ("minute", 60, limits["requests_per_minute"]),
            ("hour", 3600, limits["requests_per_hour"]),
            ("day", 86400, limits["requests_per_day"]),
        ]

        for window_name, window_seconds, limit in windows:
            window_start = now - window_seconds
            window_requests = [r for r in requests if r >= window_start]
            current_count = len(window_requests)

            if current_count + operation_size > limit:
                logger.debug(
                    f"Rate limit exceeded for {customer_id} {operation_type.value} "
                    f"in {window_name} window: {current_count + operation_size} > {limit}"
                )
                return False

        # Check daily quota limit if applicable
        if operation_type in [OperationType.MUTATE, OperationType.BULK_MUTATE]:
            quota_data = await self._storage.get_quota_usage(customer_id)
            if quota_data:
                daily_usage = quota_data.get("daily_usage", 0)
                quota_limit = self._rate_limits.get("daily_quota_limit", 10000)

                if daily_usage + operation_size > quota_limit:
                    logger.warning(
                        f"Daily quota limit would be exceeded for {customer_id}: "
                        f"{daily_usage + operation_size} > {quota_limit}"
                    )
                    return False

        # If we get here, the request is allowed - record it immediately
        await self._storage.add_request(
            customer_id, operation_type, now, operation_size
        )

        # Update quota for mutation operations
        if operation_type in [OperationType.MUTATE, OperationType.BULK_MUTATE]:
            # Calculate API cost (simplified - could be more sophisticated)
            api_cost = operation_size * 1  # 1 quota unit per operation
            await self._storage.update_quota_usage(customer_id, api_cost)

        logger.debug(
            f"Rate limit check passed and capacity reserved for {customer_id} "
            f"{operation_type.value} (size: {operation_size})"
        )
        return True

    async def record_request(
        self,
        customer_id: str,
        operation_type: OperationType,
        operation_size: int = 1,
        api_cost: Optional[int] = None,
    ) -> None:
        """Record a successful API request for rate limiting tracking.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation performed
            operation_size: Size of the operation
            api_cost: API units consumed (if available)
        """
        now = time.monotonic()

        # Record the request using storage backend
        await self._storage.add_request(
            customer_id, operation_type, now, operation_size
        )

        # Update quota tracking if cost is provided
        if api_cost is not None:
            await self._storage.update_quota_usage(customer_id, api_cost)

        logger.debug(
            f"Recorded {operation_type.value} request for {customer_id} "
            f"(size: {operation_size}, cost: {api_cost})"
        )

    async def get_rate_limit_status(
        self, customer_id: str, operation_type: OperationType
    ) -> Dict[str, Any]:
        """Get current rate limit status for a customer and operation type.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation

        Returns:
            Dictionary with current usage and remaining capacity
        """
        now = time.monotonic()
        limits = self._rate_limits[operation_type]

        # Get request history from storage backend
        requests = await self._storage.get_request_history(customer_id, operation_type)

        # Calculate usage for different windows
        status = {}
        windows = [
            ("minute", 60, limits["requests_per_minute"]),
            ("hour", 3600, limits["requests_per_hour"]),
            ("day", 86400, limits["requests_per_day"]),
        ]

        for window_name, window_seconds, limit in windows:
            window_start = now - window_seconds
            recent_requests = [ts for ts in requests if ts > window_start]
            used = len(recent_requests)
            remaining = max(0, limit - used)

            status[window_name] = {
                "limit": limit,
                "used": used,
                "remaining": remaining,
                "reset_time": now + window_seconds - (now % window_seconds),
            }

        # Add quota information if available
        quota_info = await self._storage.get_quota_usage(customer_id)
        if quota_info:
            status["quota"] = quota_info

        return status

    async def wait_until_allowed(
        self, customer_id: str, operation_type: OperationType, operation_size: int = 1
    ) -> None:
        """Wait until rate limit allows the operation, then reserve capacity.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation
            operation_size: Size of the operation
        """
        # Use configurable max wait time from Redis config if available
        max_wait_time = 300  # Default fallback
        try:
            if (
                getattr(self.settings, "redis", None)
                and hasattr(self.settings.redis, "max_wait_time")
                and isinstance(self.settings.redis.max_wait_time, (int, float))
            ):
                max_wait_time = self.settings.redis.max_wait_time
        except (AttributeError, TypeError):
            pass
        base_check_interval = 1  # Base check interval
        waited = 0
        consecutive_checks = 0

        while waited < max_wait_time:
            # Check and reserve atomically to prevent race conditions
            if await self._check_and_reserve_capacity(
                customer_id, operation_type, operation_size
            ):
                return

            consecutive_checks += 1

            # Dynamic wait strategy: shorter waits initially, longer for persistent limits
            if consecutive_checks <= 3:
                check_interval = base_check_interval
            elif consecutive_checks <= 10:
                check_interval = min(base_check_interval * 1.5, 5)
            else:
                check_interval = min(base_check_interval * 2, 10)

            logger.debug(
                f"Rate limited for {customer_id} {operation_type.value}, "
                f"waiting {check_interval}s (total waited: {waited}s, checks: {consecutive_checks})"
            )

            await asyncio.sleep(check_interval)
            waited += check_interval

        raise RateLimitError(
            f"Rate limit exceeded and maximum wait time ({max_wait_time}s) reached "
            f"for {customer_id} {operation_type.value}"
        )

    async def wait_for_rate_limit(
        self, customer_id: str, operation_type: OperationType, operation_size: int = 1
    ) -> None:
        """Wait until rate limit allows the operation to proceed.

        DEPRECATED: Use wait_until_allowed() for atomic operation.
        This method is kept for backward compatibility.

        Args:
            customer_id: Google Ads customer ID
            operation_type: Type of operation
            operation_size: Size of the operation
        """
        await self.wait_until_allowed(customer_id, operation_type, operation_size)

    async def _cleanup_old_entries(self) -> None:
        """Delegate cleanup to storage backend."""
        now = time.monotonic()

        # Only cleanup periodically to avoid overhead
        if now - self._last_cleanup >= self._cleanup_interval:
            # Use configurable history retention time from Redis config if available
            retention_time = 86400  # Default fallback
            try:
                if (
                    getattr(self.settings, "redis", None)
                    and hasattr(self.settings.redis, "cleanup_history_retention")
                    and isinstance(
                        self.settings.redis.cleanup_history_retention, (int, float)
                    )
                ):
                    retention_time = self.settings.redis.cleanup_history_retention
            except (AttributeError, TypeError):
                pass
            cutoff_time = now - retention_time
            cleaned_entries = await self._storage.cleanup_old_entries(cutoff_time)
            self._last_cleanup = now

            if cleaned_entries > 0:
                logger.debug(f"Cleaned up {cleaned_entries} old rate limit entries")

    async def health_check(self) -> bool:
        """Check if rate limiting system is healthy."""
        return await self._storage.health_check()

    async def close(self) -> None:
        """Close storage backend connections."""
        if hasattr(self._storage, "close"):
            await self._storage.close()


def rate_limited(
    operation_type: OperationType,
    operation_size: int = 1,
):
    """Decorator for rate-limited Google Ads API operations with exponential backoff.

    Uses configuration from GoogleAdsConfig for backoff settings.

    Args:
        operation_type: Type of Google Ads operation
        operation_size: Size of the operation (for bulk operations)
    """

    def decorator(func: Callable) -> Callable:
        async def wrapper(self, customer_id: str, *args, **kwargs):
            # Get or create rate limiter
            if not hasattr(self, "_rate_limiter"):
                # Try to get settings from the client if available
                settings = getattr(self, "settings", None)
                self._rate_limiter = GoogleAdsRateLimiter(settings)

            rate_limiter = self._rate_limiter

            # Use configuration from rate limiter
            max_retries = rate_limiter._max_retries
            backoff_multiplier = rate_limiter._backoff_multiplier
            max_backoff = rate_limiter._max_backoff

            # Inner function with retry logic
            @retry(
                retry=retry_if_exception_type(RateLimitError),
                stop=stop_after_attempt(max_retries + 1),
                wait=wait_exponential(multiplier=backoff_multiplier, max=max_backoff)
                + wait_random(0, 1),  # Add jitter
                reraise=True,
            )
            async def execute_with_retry():
                # Atomically wait for rate limit and reserve capacity
                await rate_limiter.wait_until_allowed(
                    customer_id, operation_type, operation_size
                )

                try:
                    # Execute the operation (capacity already reserved)
                    result = await func(self, customer_id, *args, **kwargs)
                    return result

                except Exception as e:
                    # Enhanced error detection for Google Ads API rate limits
                    error_str = str(e).lower()
                    error_type = type(e).__name__.lower()

                    # Check for specific Google Ads API error patterns
                    is_rate_limit_error = (
                        "rateLimitExceeded" in str(e)
                        or "quotaExceeded" in str(e)
                        or "userRateLimitExceeded" in str(e)
                        or "too many requests" in error_str
                        or ("rate" in error_str and "limit" in error_str)
                        or (
                            "quota" in error_str
                            and any(term in error_str for term in ["exceeded", "limit"])
                        )
                        or "throttled" in error_str
                    )

                    if is_rate_limit_error:
                        logger.warning(
                            f"Google Ads API rate limit detected for {customer_id} "
                            f"({error_type}): {e}"
                        )
                        raise RateLimitError(f"Google Ads API rate limit: {e}") from e

                    # Re-raise other exceptions
                    raise

            return await execute_with_retry()

        return wrapper

    return decorator


# Pre-configured decorators for common operations
search_rate_limited = rate_limited(OperationType.SEARCH)
mutate_rate_limited = rate_limited(OperationType.MUTATE)
report_rate_limited = rate_limited(OperationType.REPORT)
bulk_mutate_rate_limited = rate_limited(OperationType.BULK_MUTATE, operation_size=10)
account_info_rate_limited = rate_limited(OperationType.ACCOUNT_INFO)
