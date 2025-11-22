"""Circuit breaker implementation for external API calls."""

import asyncio
import logging
import random
import threading
import time
from functools import lru_cache
from typing import Any, Callable, Optional, TypeVar

from circuitbreaker import CircuitBreaker

from paidsearchnav.core.config import CircuitBreakerConfig
from paidsearchnav.core.exceptions import APIError, RateLimitError

try:
    from google.cloud.exceptions import GoogleCloudError

    BIGQUERY_AVAILABLE = True
except ImportError:
    GoogleCloudError = Exception
    BIGQUERY_AVAILABLE = False

logger = logging.getLogger(__name__)

T = TypeVar("T")


class ConfigValidationError(ValueError):
    """Raised when configuration validation fails."""

    pass


def validate_circuit_breaker_config(config: CircuitBreakerConfig) -> None:
    """Validate circuit breaker configuration.

    Args:
        config: Circuit breaker configuration to validate

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    if not isinstance(config, CircuitBreakerConfig):
        raise ConfigValidationError("Config must be a CircuitBreakerConfig instance")

    if config.failure_threshold <= 0:
        raise ConfigValidationError("failure_threshold must be positive")

    if config.recovery_timeout <= 0:
        raise ConfigValidationError("recovery_timeout must be positive")


def validate_retry_config(config: "RetryConfig") -> None:
    """Validate retry configuration.

    Args:
        config: Retry configuration to validate

    Raises:
        ConfigValidationError: If configuration is invalid
    """
    if config.max_retries < 0:
        raise ConfigValidationError("max_retries cannot be negative")

    if config.base_delay <= 0:
        raise ConfigValidationError("base_delay must be positive")

    if config.max_delay <= 0:
        raise ConfigValidationError("max_delay must be positive")

    if config.base_delay >= config.max_delay:
        raise ConfigValidationError("base_delay must be less than max_delay")

    if config.backoff_multiplier <= 1:
        raise ConfigValidationError("backoff_multiplier must be greater than 1")


class BaseCircuitBreaker:
    """Base circuit breaker implementation with common functionality."""

    def __init__(
        self,
        config: CircuitBreakerConfig,
        name: str,
        expected_exceptions: tuple[type[Exception], ...] = (Exception,),
        additional_metrics: Optional[dict[str, Any]] = None,
    ):
        """Initialize circuit breaker with configuration.

        Args:
            config: Circuit breaker configuration
            name: Circuit breaker name for identification
            expected_exceptions: Exception types that trigger circuit breaker
            additional_metrics: Additional metrics to track

        Raises:
            ConfigValidationError: If configuration is invalid
        """
        validate_circuit_breaker_config(config)
        self.config = config
        self._name = name
        self._metrics_lock = threading.Lock()

        # Base metrics that all circuit breakers track
        base_metrics = {
            "total_calls": 0,
            "failed_calls": 0,
            "circuit_opened_count": 0,
            "last_failure_time": None,
        }

        # Add any additional metrics
        if additional_metrics:
            base_metrics.update(additional_metrics)

        self._metrics = base_metrics

        # Create circuit breaker instance
        self._breaker = CircuitBreaker(
            failure_threshold=config.failure_threshold,
            recovery_timeout=config.recovery_timeout,
            expected_exception=expected_exceptions,
            name=name,
        )

    def _update_metrics(self, **updates: Any) -> None:
        """Thread-safe metrics update helper.

        Args:
            **updates: Metrics to update
        """
        with self._metrics_lock:
            self._metrics.update(updates)

    def _categorize_error(self, exception: Exception) -> dict[str, Any]:
        """Categorize error for metrics tracking. Override in subclasses.

        Args:
            exception: Exception to categorize

        Returns:
            Dictionary of metric updates based on error type
        """
        return {}

    def __call__(self, func: Callable[..., T]) -> Callable[..., T]:
        """Decorator to wrap functions with circuit breaker protection.

        Args:
            func: Function to protect with circuit breaker

        Returns:
            Wrapped function
        """
        if not self.config.enabled:
            return func

        @self._breaker
        def wrapper(*args: Any, **kwargs: Any) -> T:
            # Track metrics
            self._update_metrics(total_calls=self._metrics["total_calls"] + 1)
            previous_state = self._breaker.state

            try:
                result = func(*args, **kwargs)

                # Check if circuit just closed (recovered)
                if previous_state == "open" and self._breaker.state == "closed":
                    logger.info(
                        f"{self._name} circuit breaker CLOSED - service recovered"
                    )

                return result
            except Exception as e:
                # Track failures and categorize them
                current_time = time.time()
                metrics_update = {
                    "failed_calls": self._metrics["failed_calls"] + 1,
                    "last_failure_time": current_time,
                }

                # Add error-specific metrics
                error_metrics = self._categorize_error(e)
                metrics_update.update(error_metrics)

                self._update_metrics(**metrics_update)
                # The exception will be raised by the circuit breaker decorator
                raise

        # Wrap the wrapper to detect state changes after exceptions
        def state_tracking_wrapper(*args: Any, **kwargs: Any) -> T:
            previous_state = self._breaker.state
            try:
                return wrapper(*args, **kwargs)
            except Exception as e:
                # Check if circuit just opened due to this failure
                if previous_state == "closed" and self._breaker.state == "open":
                    self._update_metrics(
                        circuit_opened_count=self._metrics["circuit_opened_count"] + 1
                    )
                    logger.error(
                        f"{self._name} circuit breaker OPENED after "
                        f"{self.config.failure_threshold} failures"
                    )
                raise

        return state_tracking_wrapper

    @property
    def state(self) -> str:
        """Get current circuit breaker state."""
        return self._breaker.state

    @property
    def is_open(self) -> bool:
        """Check if circuit breaker is in open state."""
        return self.state == "open"

    @property
    def is_healthy(self) -> bool:
        """Check if service is healthy (circuit closed)."""
        return self.state == "closed"

    @property
    def metrics(self) -> dict[str, Any]:
        """Get circuit breaker metrics."""
        with self._metrics_lock:
            return {
                **self._metrics,
                "current_state": self.state,
                "failure_count": self._breaker.failure_count,
                "last_failure": self._breaker.last_failure,
                "failure_threshold": self.config.failure_threshold,
                "recovery_timeout": self.config.recovery_timeout,
                "health_status": "healthy" if self.is_healthy else "degraded",
            }

    def reset(self) -> None:
        """Reset circuit breaker to closed state."""
        # The circuitbreaker library doesn't have a reset method,
        # so we manually call the success method to close it
        self._breaker._CircuitBreaker__call_succeeded()
        logger.info(f"{self._name} circuit breaker manually reset")


class GoogleAdsCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker specifically configured for Google Ads API calls."""

    def __init__(self, config: CircuitBreakerConfig):
        """Initialize circuit breaker with configuration.

        Args:
            config: Circuit breaker configuration
        """
        super().__init__(
            config=config,
            name="GoogleAdsAPI",
            expected_exceptions=(APIError, RateLimitError, Exception),
        )

    def _categorize_error(self, exception: Exception) -> dict[str, Any]:
        """Categorize Google Ads API errors for metrics tracking.

        Args:
            exception: Exception to categorize

        Returns:
            Dictionary of metric updates based on error type
        """
        if isinstance(exception, (APIError, RateLimitError)):
            logger.warning(
                f"Google Ads circuit breaker triggered by {type(exception).__name__}: {exception}"
            )
        else:
            logger.warning(
                f"Unexpected exception in Google Ads circuit breaker: {type(exception).__name__}: {exception}"
            )
        return {}


def create_google_ads_circuit_breaker(
    config: CircuitBreakerConfig,
) -> GoogleAdsCircuitBreaker:
    """Create a circuit breaker instance for Google Ads API.

    Args:
        config: Circuit breaker configuration

    Returns:
        Configured circuit breaker instance
    """
    return GoogleAdsCircuitBreaker(config)


class BigQueryCircuitBreaker(BaseCircuitBreaker):
    """Circuit breaker specifically configured for BigQuery operations."""

    def __init__(self, config: CircuitBreakerConfig):
        """Initialize circuit breaker with configuration.

        Args:
            config: Circuit breaker configuration
        """
        # BigQuery-specific exceptions to handle
        expected_exceptions = (
            (GoogleCloudError, Exception) if BIGQUERY_AVAILABLE else (Exception,)
        )

        # Additional metrics specific to BigQuery
        additional_metrics = {
            "quota_exceeded_count": 0,
            "timeout_count": 0,
            "connection_error_count": 0,
        }

        super().__init__(
            config=config,
            name="BigQueryAPI",
            expected_exceptions=expected_exceptions,
            additional_metrics=additional_metrics,
        )

    @staticmethod
    @lru_cache(maxsize=128)
    def _classify_error_message(error_msg: str) -> str:
        """Classify error message for caching efficiency.

        Args:
            error_msg: Lowercased error message string

        Returns:
            Error classification: 'quota', 'timeout', 'connection', or 'other'
        """
        if any(keyword in error_msg for keyword in ["quota exceeded", "rate limit"]):
            return "quota"
        elif "timeout" in error_msg:
            return "timeout"
        elif any(keyword in error_msg for keyword in ["connection", "network"]):
            return "connection"
        else:
            return "other"

    def _categorize_error(self, exception: Exception) -> dict[str, Any]:
        """Categorize BigQuery-specific errors for metrics tracking.

        Args:
            exception: Exception to categorize

        Returns:
            Dictionary of metric updates based on error type
        """
        metrics_update = {}

        if BIGQUERY_AVAILABLE and isinstance(exception, GoogleCloudError):
            error_msg = str(exception).lower()
            error_type = self._classify_error_message(error_msg)

            if error_type == "quota":
                metrics_update["quota_exceeded_count"] = (
                    self._metrics["quota_exceeded_count"] + 1
                )
                logger.warning(f"BigQuery quota/rate limit exceeded: {exception}")
            elif error_type == "timeout":
                metrics_update["timeout_count"] = self._metrics["timeout_count"] + 1
                logger.warning(f"BigQuery timeout error: {exception}")
            elif error_type == "connection":
                metrics_update["connection_error_count"] = (
                    self._metrics["connection_error_count"] + 1
                )
                logger.warning(f"BigQuery connection error: {exception}")
            else:
                logger.debug(
                    f"BigQuery circuit breaker triggered by {type(exception).__name__}: {exception}"
                )
        else:
            logger.warning(
                f"Unexpected exception in BigQuery circuit breaker: {type(exception).__name__}: {exception}"
            )

        return metrics_update

    def get_health_check_info(self) -> dict[str, Any]:
        """Get health check information for monitoring."""
        with self._metrics_lock:
            return {
                "service": "BigQuery",
                "state": self.state,
                "is_healthy": self.is_healthy,
                "failure_rate": (
                    self._metrics["failed_calls"] / max(self._metrics["total_calls"], 1)
                )
                * 100,
                "error_breakdown": {
                    "quota_exceeded": self._metrics["quota_exceeded_count"],
                    "timeouts": self._metrics["timeout_count"],
                    "connection_errors": self._metrics["connection_error_count"],
                },
                "last_failure_time": self._metrics["last_failure_time"],
                "times_circuit_opened": self._metrics["circuit_opened_count"],
            }


def create_bigquery_circuit_breaker(
    config: CircuitBreakerConfig,
) -> BigQueryCircuitBreaker:
    """Create a circuit breaker instance for BigQuery API.

    Args:
        config: Circuit breaker configuration

    Returns:
        Configured circuit breaker instance
    """
    return BigQueryCircuitBreaker(config)


class RetryConfig:
    """Configuration for retry and backoff mechanisms."""

    def __init__(
        self,
        max_retries: int = 3,
        base_delay: float = 1.0,
        max_delay: float = 60.0,
        backoff_multiplier: float = 2.0,
        jitter: bool = True,
    ):
        self.max_retries = max_retries
        self.base_delay = base_delay
        self.max_delay = max_delay
        self.backoff_multiplier = backoff_multiplier
        self.jitter = jitter

        # Validate configuration
        validate_retry_config(self)

    def get_delay(self, attempt: int) -> float:
        """Calculate delay for given attempt with exponential backoff."""
        delay = self.base_delay * (self.backoff_multiplier ** (attempt - 1))
        delay = min(delay, self.max_delay)

        if self.jitter:
            # Add jitter to prevent thundering herd
            delay = delay * (0.5 + random.random() * 0.5)

        return delay


class BigQueryRetryHandler:
    """Retry handler with exponential backoff for BigQuery operations."""

    def __init__(self, retry_config: Optional[RetryConfig] = None):
        self.config = retry_config or RetryConfig()
        self._metrics_lock = threading.Lock()
        self._metrics = {
            "total_retries": 0,
            "successful_retries": 0,
            "failed_retries": 0,
            "quota_retry_count": 0,
            "timeout_retry_count": 0,
            "connection_retry_count": 0,
        }

    def _update_metrics(self, **updates: Any) -> None:
        """Thread-safe metrics update helper.

        Args:
            **updates: Metrics to update
        """
        with self._metrics_lock:
            self._metrics.update(updates)

    def should_retry(self, exception: Exception, attempt: int) -> bool:
        """Determine if an exception should trigger a retry."""
        if attempt >= self.config.max_retries:
            return False

        if not BIGQUERY_AVAILABLE:
            return False

        if isinstance(exception, GoogleCloudError):
            error_msg = str(exception).lower()
            # Retry on transient errors
            if any(
                keyword in error_msg
                for keyword in [
                    "timeout",
                    "connection",
                    "network",
                    "temporary",
                    "rate limit",
                    "quota",
                    "service unavailable",
                ]
            ):
                return True

        return False

    def _categorize_retry_error(self, exception: Exception) -> dict[str, Any]:
        """Categorize error for retry metrics tracking."""
        metrics_update = {}

        if BIGQUERY_AVAILABLE and isinstance(exception, GoogleCloudError):
            error_msg = str(exception).lower()
            error_type = BigQueryCircuitBreaker._classify_error_message(error_msg)

            if error_type == "quota":
                metrics_update["quota_retry_count"] = (
                    self._metrics["quota_retry_count"] + 1
                )
            elif error_type == "timeout":
                metrics_update["timeout_retry_count"] = (
                    self._metrics["timeout_retry_count"] + 1
                )
            elif error_type == "connection":
                metrics_update["connection_retry_count"] = (
                    self._metrics["connection_retry_count"] + 1
                )

        return metrics_update

    async def execute_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a function with retry logic (handles both sync and async functions)."""
        if asyncio.iscoroutinefunction(func):
            return await self._execute_async_with_retry(func, *args, **kwargs)
        else:
            return await self._execute_sync_with_retry(func, *args, **kwargs)

    async def _execute_async_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute an async function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                result = await func(*args, **kwargs)

                if attempt > 1:
                    self._update_metrics(
                        successful_retries=self._metrics["successful_retries"] + 1
                    )
                    logger.info(
                        f"BigQuery async operation succeeded on attempt {attempt}"
                    )

                return result

            except Exception as e:
                last_exception = e

                # Track retry and categorize error
                metrics_update = {
                    "total_retries": self._metrics["total_retries"] + 1,
                    **self._categorize_retry_error(e),
                }
                self._update_metrics(**metrics_update)

                if not self.should_retry(e, attempt):
                    self._update_metrics(
                        failed_retries=self._metrics["failed_retries"] + 1
                    )
                    logger.error(
                        f"BigQuery async operation failed permanently after {attempt} attempts: {e}"
                    )
                    raise e

                if attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        f"BigQuery async operation failed on attempt {attempt}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        self._update_metrics(failed_retries=self._metrics["failed_retries"] + 1)
        logger.error(
            f"BigQuery async operation failed after {self.config.max_retries} retries"
        )
        raise last_exception

    async def _execute_sync_with_retry(self, func: Callable, *args, **kwargs) -> Any:
        """Execute a sync function with retry logic."""
        last_exception = None

        for attempt in range(1, self.config.max_retries + 1):
            try:
                result = func(*args, **kwargs)

                if attempt > 1:
                    self._update_metrics(
                        successful_retries=self._metrics["successful_retries"] + 1
                    )
                    logger.info(
                        f"BigQuery sync operation succeeded on attempt {attempt}"
                    )

                return result

            except Exception as e:
                last_exception = e

                # Track retry and categorize error
                metrics_update = {
                    "total_retries": self._metrics["total_retries"] + 1,
                    **self._categorize_retry_error(e),
                }
                self._update_metrics(**metrics_update)

                if not self.should_retry(e, attempt):
                    self._update_metrics(
                        failed_retries=self._metrics["failed_retries"] + 1
                    )
                    logger.error(
                        f"BigQuery sync operation failed permanently after {attempt} attempts: {e}"
                    )
                    raise e

                if attempt < self.config.max_retries:
                    delay = self.config.get_delay(attempt)
                    logger.warning(
                        f"BigQuery sync operation failed on attempt {attempt}, "
                        f"retrying in {delay:.2f}s: {e}"
                    )
                    await asyncio.sleep(delay)

        # All retries exhausted
        self._update_metrics(failed_retries=self._metrics["failed_retries"] + 1)
        logger.error(
            f"BigQuery sync operation failed after {self.config.max_retries} retries"
        )
        raise last_exception

    @property
    def metrics(self) -> dict[str, Any]:
        """Get retry handler metrics."""
        with self._metrics_lock:
            return {
                **self._metrics,
                "retry_config": {
                    "max_retries": self.config.max_retries,
                    "base_delay": self.config.base_delay,
                    "max_delay": self.config.max_delay,
                    "backoff_multiplier": self.config.backoff_multiplier,
                    "jitter_enabled": self.config.jitter,
                },
                "success_rate": (
                    self._metrics["successful_retries"]
                    / max(self._metrics["total_retries"], 1)
                )
                * 100
                if self._metrics["total_retries"] > 0
                else 100,
            }


def create_bigquery_retry_handler(
    max_retries: int = 3,
    base_delay: float = 1.0,
    max_delay: float = 60.0,
) -> BigQueryRetryHandler:
    """Create a retry handler for BigQuery operations.

    Args:
        max_retries: Maximum number of retry attempts
        base_delay: Base delay between retries in seconds
        max_delay: Maximum delay between retries in seconds

    Returns:
        Configured retry handler instance
    """
    retry_config = RetryConfig(
        max_retries=max_retries,
        base_delay=base_delay,
        max_delay=max_delay,
    )
    return BigQueryRetryHandler(retry_config)
