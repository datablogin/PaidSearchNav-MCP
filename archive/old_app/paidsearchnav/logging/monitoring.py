"""Monitoring utilities for tracking application metrics."""

import time
from collections.abc import Callable
from contextlib import contextmanager
from functools import wraps
from typing import Any

from paidsearchnav.logging.config import get_logger

logger = get_logger(__name__)


class MetricsCollector:
    """Collect and report application metrics."""

    def __init__(self):
        """Initialize metrics collector."""
        self.metrics: dict[str, Any] = {}

    def increment(
        self, metric: str, value: int = 1, tags: dict[str, str] | None = None
    ) -> None:
        """Increment a counter metric.

        Args:
            metric: Metric name
            value: Value to increment by
            tags: Optional tags for the metric
        """
        key = self._build_key(metric, tags)
        self.metrics[key] = self.metrics.get(key, 0) + value

        logger.debug(
            "Metric incremented",
            extra={"metric": metric, "value": value, "tags": tags},
        )

    def gauge(
        self, metric: str, value: float, tags: dict[str, str] | None = None
    ) -> None:
        """Set a gauge metric.

        Args:
            metric: Metric name
            value: Gauge value
            tags: Optional tags for the metric
        """
        key = self._build_key(metric, tags)
        self.metrics[key] = value

        logger.debug(
            "Gauge set",
            extra={"metric": metric, "value": value, "tags": tags},
        )

    def timing(
        self, metric: str, duration_ms: float, tags: dict[str, str] | None = None
    ) -> None:
        """Record a timing metric.

        Args:
            metric: Metric name
            duration_ms: Duration in milliseconds
            tags: Optional tags for the metric
        """
        logger.info(
            f"Timing: {metric}",
            extra={"metric": metric, "duration_ms": duration_ms, "tags": tags},
        )

    def _build_key(self, metric: str, tags: dict[str, str] | None = None) -> str:
        """Build a metric key with tags.

        Args:
            metric: Base metric name
            tags: Optional tags

        Returns:
            Metric key
        """
        if not tags:
            return metric

        tag_str = ",".join(f"{k}={v}" for k, v in sorted(tags.items()))
        return f"{metric},{tag_str}"

    def get_metrics(self) -> dict[str, Any]:
        """Get all collected metrics.

        Returns:
            Dictionary of metrics
        """
        return self.metrics.copy()

    def reset(self) -> None:
        """Reset all metrics."""
        self.metrics.clear()


# Global metrics collector
_metrics = MetricsCollector()


def increment(metric: str, value: int = 1, tags: dict[str, str] | None = None) -> None:
    """Increment a counter metric.

    Args:
        metric: Metric name
        value: Value to increment by
        tags: Optional tags for the metric
    """
    _metrics.increment(metric, value, tags)


def gauge(metric: str, value: float, tags: dict[str, str] | None = None) -> None:
    """Set a gauge metric.

    Args:
        metric: Metric name
        value: Gauge value
        tags: Optional tags for the metric
    """
    _metrics.gauge(metric, value, tags)


def timing(metric: str, duration_ms: float, tags: dict[str, str] | None = None) -> None:
    """Record a timing metric.

    Args:
        metric: Metric name
        duration_ms: Duration in milliseconds
        tags: Optional tags for the metric
    """
    _metrics.timing(metric, duration_ms, tags)


@contextmanager
def timer(metric: str, tags: dict[str, str] | None = None):
    """Context manager for timing operations.

    Args:
        metric: Metric name
        tags: Optional tags

    Example:
        >>> with timer("api.request", tags={"endpoint": "/search"}):
        ...     make_api_request()
    """
    start_time = time.time()
    try:
        yield
    finally:
        duration_ms = (time.time() - start_time) * 1000
        timing(metric, duration_ms, tags)


def timed(metric: str | None = None):
    """Decorator for timing function execution.

    Args:
        metric: Optional metric name (defaults to function name)

    Example:
        >>> @timed("analyzer.keyword_match")
        ... def analyze_keywords():
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        metric_name = metric or f"function.{func.__name__}"

        @wraps(func)
        def wrapper(*args, **kwargs):
            with timer(metric_name):
                return func(*args, **kwargs)

        return wrapper

    return decorator


def track_job(job_type: str):
    """Decorator for tracking job execution.

    Args:
        job_type: Type of job being tracked

    Example:
        >>> @track_job("keyword_analysis")
        ... async def analyze_keywords(customer_id: str):
        ...     pass
    """

    def decorator(func: Callable) -> Callable:
        @wraps(func)
        async def async_wrapper(*args, **kwargs):
            job_id = kwargs.get("job_id", "unknown")
            customer_id = kwargs.get("customer_id", "unknown")

            increment("job.started", tags={"type": job_type})
            logger.info(
                f"Job started: {job_type}",
                extra={
                    "job_type": job_type,
                    "job_id": job_id,
                    "customer_id": customer_id,
                },
            )

            start_time = time.time()
            try:
                result = await func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                increment("job.completed", tags={"type": job_type})
                timing("job.duration", duration_ms, tags={"type": job_type})

                logger.info(
                    f"Job completed: {job_type}",
                    extra={
                        "job_type": job_type,
                        "job_id": job_id,
                        "customer_id": customer_id,
                        "duration_ms": duration_ms,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                increment("job.failed", tags={"type": job_type})

                logger.error(
                    f"Job failed: {job_type}",
                    extra={
                        "job_type": job_type,
                        "job_id": job_id,
                        "customer_id": customer_id,
                        "duration_ms": duration_ms,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

        @wraps(func)
        def sync_wrapper(*args, **kwargs):
            job_id = kwargs.get("job_id", "unknown")
            customer_id = kwargs.get("customer_id", "unknown")

            increment("job.started", tags={"type": job_type})
            logger.info(
                f"Job started: {job_type}",
                extra={
                    "job_type": job_type,
                    "job_id": job_id,
                    "customer_id": customer_id,
                },
            )

            start_time = time.time()
            try:
                result = func(*args, **kwargs)
                duration_ms = (time.time() - start_time) * 1000

                increment("job.completed", tags={"type": job_type})
                timing("job.duration", duration_ms, tags={"type": job_type})

                logger.info(
                    f"Job completed: {job_type}",
                    extra={
                        "job_type": job_type,
                        "job_id": job_id,
                        "customer_id": customer_id,
                        "duration_ms": duration_ms,
                    },
                )

                return result

            except Exception as e:
                duration_ms = (time.time() - start_time) * 1000
                increment("job.failed", tags={"type": job_type})

                logger.error(
                    f"Job failed: {job_type}",
                    extra={
                        "job_type": job_type,
                        "job_id": job_id,
                        "customer_id": customer_id,
                        "duration_ms": duration_ms,
                        "error": str(e),
                    },
                    exc_info=True,
                )
                raise

        # Return appropriate wrapper based on function type
        import asyncio

        if asyncio.iscoroutinefunction(func):
            return async_wrapper
        else:
            return sync_wrapper

    return decorator
