"""Retry logic for export operations."""

import asyncio
import logging
import random
from typing import Any, Callable, Optional, Tuple, Type

logger = logging.getLogger(__name__)


def exponential_backoff_with_jitter(
    attempt: int, base_delay: float = 1.0, max_delay: float = 60.0, jitter: float = 0.1
) -> float:
    """Calculate exponential backoff with jitter."""
    delay = min(base_delay * (2**attempt), max_delay)
    jitter_amount = delay * jitter
    return delay + random.uniform(-jitter_amount, jitter_amount)


class RetryPolicy:
    """Configurable retry policy for export operations."""

    def __init__(
        self,
        max_attempts: int = 3,
        backoff_func: Optional[Callable[[int], float]] = None,
        retriable_exceptions: Tuple[Type[Exception], ...] = (Exception,),
        on_retry: Optional[Callable[[Exception, int], None]] = None,
    ):
        """Initialize retry policy."""
        self.max_attempts = max_attempts
        self.backoff_func = backoff_func or exponential_backoff_with_jitter
        self.retriable_exceptions = retriable_exceptions
        self.on_retry = on_retry

    async def execute(self, func: Callable, *args, **kwargs) -> Any:
        """Execute function with retry logic."""
        last_exception = None

        for attempt in range(self.max_attempts):
            try:
                # Execute the function
                if asyncio.iscoroutinefunction(func):
                    return await func(*args, **kwargs)
                else:
                    return func(*args, **kwargs)

            except self.retriable_exceptions as e:
                last_exception = e

                # Check if we should retry
                if attempt >= self.max_attempts - 1:
                    logger.error(f"Max retry attempts ({self.max_attempts}) reached")
                    raise

                # Calculate backoff delay
                delay = self.backoff_func(attempt)

                # Call retry callback if provided
                if self.on_retry:
                    self.on_retry(e, attempt + 1)

                logger.warning(
                    f"Attempt {attempt + 1}/{self.max_attempts} failed: {e}. "
                    f"Retrying in {delay:.2f} seconds..."
                )

                # Wait before retrying
                await asyncio.sleep(delay)

            except Exception as e:
                # Non-retriable exception
                logger.error(f"Non-retriable exception: {e}")
                raise

        # Should never reach here, but just in case
        if last_exception:
            raise last_exception
