"""Structured logging utilities for Google Ads Scripts."""

import logging
import uuid
from contextvars import ContextVar
from typing import Any, MutableMapping, Optional

# Context variable to store correlation ID
correlation_id_var: ContextVar[Optional[str]] = ContextVar(
    "correlation_id", default=None
)


def generate_correlation_id() -> str:
    """Generate a unique correlation ID."""
    return str(uuid.uuid4())


def set_correlation_id(correlation_id: Optional[str] = None) -> str:
    """Set the correlation ID for the current context.

    Args:
        correlation_id: The correlation ID to set. If None, a new one is generated.

    Returns:
        The correlation ID that was set.
    """
    if correlation_id is None:
        correlation_id = generate_correlation_id()
    correlation_id_var.set(correlation_id)
    return correlation_id


def get_correlation_id() -> Optional[str]:
    """Get the current correlation ID."""
    return correlation_id_var.get()


class StructuredLoggerAdapter(logging.LoggerAdapter):
    """Logger adapter that adds structured data to log records."""

    def process(
        self, msg: str, kwargs: MutableMapping[str, Any]
    ) -> tuple[str, MutableMapping[str, Any]]:
        """Process the logging call to add structured data."""
        # Get correlation ID from context
        correlation_id = get_correlation_id()

        # Get extra data from kwargs
        extra = kwargs.get("extra", {})

        # Add correlation ID if available
        if correlation_id:
            extra["correlation_id"] = correlation_id

        # Add any additional context from the adapter
        if self.extra:
            extra.update(self.extra)

        kwargs["extra"] = extra
        return msg, kwargs


def get_structured_logger(name: str, **context) -> StructuredLoggerAdapter:
    """Get a structured logger with context.

    Args:
        name: Logger name
        **context: Additional context to include in all log messages

    Returns:
        A structured logger adapter
    """
    base_logger = logging.getLogger(name)
    return StructuredLoggerAdapter(base_logger, context)


class CorrelationIDFilter(logging.Filter):
    """Logging filter that adds correlation ID to log records."""

    def filter(self, record: logging.LogRecord) -> bool:
        """Add correlation ID to the log record."""
        if not hasattr(record, "correlation_id"):
            record.correlation_id = get_correlation_id() or "no-correlation-id"
        return True


def configure_structured_logging():
    """Configure structured logging with correlation ID support."""
    # Add correlation ID filter to root logger
    root_logger = logging.getLogger()
    root_logger.addFilter(CorrelationIDFilter())

    # Update log format to include correlation ID
    formatter = logging.Formatter(
        "%(asctime)s - %(name)s - %(levelname)s - [%(correlation_id)s] - %(message)s"
    )

    # Update all handlers
    for handler in root_logger.handlers:
        handler.setFormatter(formatter)
