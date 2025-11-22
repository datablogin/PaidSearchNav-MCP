"""Logging context management for structured logging."""

import contextvars
from typing import Any

# Context variable for storing log context
_log_context: contextvars.ContextVar[dict[str, Any] | None] = contextvars.ContextVar(
    "log_context", default=None
)


def add_context(**kwargs: Any) -> None:
    """Add fields to the logging context.

    These fields will be included in all log messages within the current
    async context.

    Args:
        **kwargs: Key-value pairs to add to context

    Example:
        >>> add_context(customer_id="123", job_id="abc")
        >>> logger.info("Processing started")  # Will include customer_id and job_id
    """
    current = _log_context.get()
    if current is None:
        current = {}
    else:
        current = current.copy()
    current.update(kwargs)
    _log_context.set(current)


def clear_context() -> None:
    """Clear all fields from the logging context."""
    _log_context.set({})


def get_context() -> dict[str, Any]:
    """Get the current logging context.

    Returns:
        Dictionary of context fields
    """
    current = _log_context.get()
    if current is None:
        return {}
    return current.copy()


def remove_context(*keys: str) -> None:
    """Remove specific fields from the logging context.

    Args:
        *keys: Field names to remove
    """
    current = _log_context.get()
    if current is None:
        return
    current = current.copy()
    for key in keys:
        current.pop(key, None)
    _log_context.set(current)


class LogContext:
    """Context manager for temporarily adding log context."""

    def __init__(self, **kwargs: Any):
        """Initialize context manager.

        Args:
            **kwargs: Fields to add to context
        """
        self.fields = kwargs
        self.token: contextvars.Token | None = None
        self.previous: dict[str, Any] = {}

    def __enter__(self) -> "LogContext":
        """Enter context and add fields."""
        current = _log_context.get()
        if current is None:
            self.previous = {}
            new_context = self.fields.copy()
        else:
            self.previous = current.copy()
            new_context = self.previous.copy()
            new_context.update(self.fields)
        self.token = _log_context.set(new_context)
        return self

    def __exit__(self, exc_type, exc_val, exc_tb) -> None:
        """Exit context and restore previous state."""
        if self.token:
            _log_context.reset(self.token)
