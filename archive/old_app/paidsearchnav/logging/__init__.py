"""Logging and monitoring infrastructure for PaidSearchNav."""

from paidsearchnav.logging.config import (
    LogConfig,
    LogLevel,
    configure_logging,
    get_logger,
)
from paidsearchnav.logging.context import (
    add_context,
    clear_context,
    get_context,
)
from paidsearchnav.logging.formatters import JSONFormatter
from paidsearchnav.logging.handlers import (
    AlertHandler,
    EmailAlertHandler,
    SentryHandler,
    SlackAlertHandler,
)
from paidsearchnav.logging.secrets import (
    SecretsRegistry,
    get_secrets_registry,
    mask_secrets,
)

__all__ = [
    "configure_logging",
    "get_logger",
    "LogLevel",
    "LogConfig",
    "AlertHandler",
    "SlackAlertHandler",
    "EmailAlertHandler",
    "SentryHandler",
    "JSONFormatter",
    "add_context",
    "clear_context",
    "get_context",
    "SecretsRegistry",
    "get_secrets_registry",
    "mask_secrets",
]
