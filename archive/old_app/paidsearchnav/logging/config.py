"""Logging configuration and setup."""

import logging
import logging.handlers
import os
import platform
import sys
from enum import Enum
from pathlib import Path
from typing import Any, List, Optional

from pydantic import BaseModel, Field, SecretStr

from paidsearchnav.core.config import Settings
from paidsearchnav.logging.formatters import JSONFormatter
from paidsearchnav.logging.handlers import (
    EmailAlertHandler,
    SentryHandler,
    SlackAlertHandler,
)
from paidsearchnav.logging.secrets import get_secrets_registry


class SecureRotatingFileHandler(logging.handlers.RotatingFileHandler):
    """Rotating file handler that maintains secure permissions on rotated files."""

    def __init__(
        self,
        filename,
        mode="a",
        maxBytes=0,
        backupCount=0,
        encoding=None,
        delay=False,
        permissions=0o600,
    ):
        """Initialize secure rotating file handler.

        Args:
            filename: Log file path
            mode: File open mode
            maxBytes: Maximum file size before rotation
            backupCount: Number of backup files to keep
            encoding: File encoding
            delay: Whether to delay file opening
            permissions: File permissions to apply (default: 0o600)
        """
        self.permissions = permissions
        super().__init__(filename, mode, maxBytes, backupCount, encoding, delay)

    def _open(self):
        """Open file with secure permissions."""
        stream = super()._open()
        # Apply permissions to the file
        if platform.system() != "Windows":
            try:
                os.chmod(self.baseFilename, self.permissions)
            except (OSError, PermissionError):
                pass  # Best effort
        return stream

    def doRollover(self):
        """Rollover with secure permissions on rotated files."""
        super().doRollover()
        # Apply permissions to all backup files
        if platform.system() != "Windows":
            for i in range(self.backupCount):
                backup_file = f"{self.baseFilename}.{i + 1}"
                if os.path.exists(backup_file):
                    try:
                        os.chmod(backup_file, self.permissions)
                    except (OSError, PermissionError):
                        pass  # Best effort


class LogLevel(str, Enum):
    """Supported log levels."""

    DEBUG = "DEBUG"
    INFO = "INFO"
    WARNING = "WARNING"
    ERROR = "ERROR"
    CRITICAL = "CRITICAL"


class LogConfig(BaseModel):
    """Logging configuration."""

    level: LogLevel = Field(default=LogLevel.INFO, description="Default log level")
    json_format: bool = Field(default=True, description="Use JSON format for logs")
    log_file: Optional[Path] = Field(default=None, description="Optional log file path")

    # Alert configuration
    enable_alerts: bool = Field(default=True, description="Enable alert handlers")
    alert_level: LogLevel = Field(
        default=LogLevel.ERROR, description="Minimum level for alerts"
    )

    # Slack configuration
    slack_webhook_url: Optional[SecretStr] = Field(
        default=None, description="Slack webhook for alerts"
    )
    slack_channel: Optional[str] = Field(
        default=None, description="Slack channel override"
    )

    # Email configuration
    smtp_host: Optional[str] = Field(default=None, description="SMTP server host")
    smtp_port: int = Field(default=587, description="SMTP server port")
    smtp_username: Optional[str] = Field(default=None, description="SMTP username")
    smtp_password: Optional[SecretStr] = Field(
        default=None, description="SMTP password"
    )
    email_from: Optional[str] = Field(default=None, description="From email address")
    email_to: List[str] = Field(
        default_factory=list, description="Alert recipient emails"
    )

    # Sentry configuration
    sentry_dsn: Optional[SecretStr] = Field(
        default=None, description="Sentry DSN for error tracking"
    )
    sentry_environment: str = Field(
        default="development", description="Sentry environment"
    )

    # Log retention
    retention_days: int = Field(default=30, description="Days to retain logs")
    max_log_size_mb: int = Field(default=100, description="Maximum log file size in MB")

    # File permissions (security)
    log_file_permissions: int = Field(
        default=0o600,
        description="File permissions for log files (owner read/write only). "
        "More restrictive permissions (e.g., 0o600) recommended for "
        "logs containing sensitive data.",
    )
    log_dir_permissions: int = Field(
        default=0o700,
        description="Directory permissions for log directories (owner only). "
        "Restrictive permissions prevent unauthorized access to log files.",
    )

    # Secret masking configuration
    enable_secret_masking: bool = Field(
        default=True, description="Enable automatic secret masking in logs"
    )
    secret_mask_string: str = Field(
        default="***REDACTED***", description="String to use for masking secrets"
    )
    custom_sensitive_keys: List[str] = Field(
        default_factory=list, description="Additional sensitive field names"
    )
    custom_secret_patterns: List[str] = Field(
        default_factory=list,
        description="Additional regex patterns for secret detection",
    )
    whitelist_patterns: List[str] = Field(
        default_factory=list,
        description="Regex patterns for whitelisting false positives",
    )
    disabled_masking_loggers: List[str] = Field(
        default_factory=list,
        description="Logger names to disable secret masking for (performance)",
    )
    enable_audit_logging: bool = Field(
        default=False,
        description="Enable audit logging of secret detection events",
    )

    # Performance optimization settings
    max_recursion_depth: int = Field(
        default=10,
        description="Maximum recursion depth for nested data structures",
    )
    enable_pattern_cache: bool = Field(
        default=True,
        description="Enable pattern matching cache for better performance",
    )
    pattern_cache_size: int = Field(
        default=1000,
        description="Maximum size of pattern matching cache",
    )

    model_config = {
        # Use enum values instead of names
        "use_enum_values": True,
    }


def _apply_secure_permissions(path: Path, permissions: int) -> None:
    """Apply file permissions with platform compatibility and error handling.

    Args:
        path: Path to file or directory
        permissions: Octal permissions to apply
    """
    if platform.system() == "Windows":
        # Windows has a different permission model
        # Skip detailed permission setting on Windows
        return

    try:
        # Only set permissions if they differ from expected
        current_perms = path.stat().st_mode & 0o777
        if current_perms != permissions:
            os.chmod(path, permissions)
    except (OSError, PermissionError) as e:
        # Log warning but continue - permission setting is best effort
        logging.getLogger(__name__).warning(f"Could not set permissions on {path}: {e}")


def configure_logging(settings: Settings, config: LogConfig | None = None) -> None:
    """Configure logging for the application.

    Args:
        settings: Application settings
        config: Optional logging configuration override
    """
    if config is None:
        config = _load_config_from_settings(settings)

    # Configure secrets registry
    if config.enable_secret_masking:
        secrets_registry = get_secrets_registry()

        # Add custom sensitive keys
        for key in config.custom_sensitive_keys:
            secrets_registry.add_sensitive_key(key)

        # Add custom secret patterns
        for pattern in config.custom_secret_patterns:
            try:
                secrets_registry.add_secret_pattern(pattern)
            except ValueError as e:
                # Log warning about invalid pattern but continue
                logging.getLogger(__name__).warning(f"Invalid secret pattern: {e}")

        # Add whitelist patterns
        for pattern in config.whitelist_patterns:
            try:
                secrets_registry.add_whitelist_pattern(pattern)
            except ValueError as e:
                # Log warning about invalid pattern but continue
                logging.getLogger(__name__).warning(f"Invalid whitelist pattern: {e}")

        # Disable masking for specified loggers
        for logger_name in config.disabled_masking_loggers:
            secrets_registry.disable_masking_for_logger(logger_name)

        # Configure audit logging
        if config.enable_audit_logging:
            secrets_registry.enable_audit_logging()

        # Configure performance settings
        secrets_registry.set_max_recursion_depth(config.max_recursion_depth)

        if config.enable_pattern_cache:
            secrets_registry.enable_pattern_cache()
            secrets_registry.set_cache_size(config.pattern_cache_size)
        else:
            secrets_registry.disable_pattern_cache()

    # Clear existing handlers
    root_logger = logging.getLogger()
    root_logger.handlers.clear()

    # Set base log level
    root_logger.setLevel(config.level)

    # Console handler
    console_handler = logging.StreamHandler(sys.stdout)
    if config.json_format:
        console_handler.setFormatter(JSONFormatter())
    else:
        console_handler.setFormatter(
            logging.Formatter("%(asctime)s - %(name)s - %(levelname)s - %(message)s")
        )
    root_logger.addHandler(console_handler)

    # File handler
    if config.log_file:
        # Create directory with secure permissions
        config.log_file.parent.mkdir(parents=True, exist_ok=True)
        _apply_secure_permissions(config.log_file.parent, config.log_dir_permissions)

        file_handler = SecureRotatingFileHandler(
            config.log_file,
            maxBytes=config.max_log_size_mb * 1024 * 1024,
            backupCount=5,
            permissions=config.log_file_permissions,
        )

        # Set secure permissions on the log file
        if config.log_file.exists():
            _apply_secure_permissions(config.log_file, config.log_file_permissions)
        else:
            # Create the file with secure permissions if it doesn't exist
            # Note: Path.touch() mode parameter sets umask, not permissions directly
            config.log_file.touch(exist_ok=True)
            _apply_secure_permissions(config.log_file, config.log_file_permissions)

        if config.json_format:
            file_handler.setFormatter(JSONFormatter())
        root_logger.addHandler(file_handler)

    # Alert handlers
    if config.enable_alerts:
        # Slack alerts
        if config.slack_webhook_url:
            slack_handler = SlackAlertHandler(
                webhook_url=config.slack_webhook_url.get_secret_value(),
                channel=config.slack_channel,
            )
            slack_handler.setLevel(getattr(logging, config.alert_level))
            root_logger.addHandler(slack_handler)

        # Email alerts
        if config.smtp_host and config.email_to:
            email_handler = EmailAlertHandler(
                smtp_host=config.smtp_host,
                smtp_port=config.smtp_port,
                smtp_username=config.smtp_username,
                smtp_password=config.smtp_password.get_secret_value()
                if config.smtp_password
                else None,
                from_email=config.email_from or "alerts@paidsearchnav.com",
                to_emails=config.email_to,
            )
            email_handler.setLevel(getattr(logging, config.alert_level))
            root_logger.addHandler(email_handler)

        # Sentry integration
        if config.sentry_dsn:
            sentry_handler = SentryHandler(
                dsn=config.sentry_dsn.get_secret_value(),
                environment=config.sentry_environment,
            )
            sentry_handler.setLevel(logging.ERROR)
            root_logger.addHandler(sentry_handler)

    # Set third-party log levels to reduce noise
    logging.getLogger("urllib3").setLevel(logging.WARNING)
    logging.getLogger("google").setLevel(logging.WARNING)
    logging.getLogger("sqlalchemy.engine").setLevel(logging.WARNING)


class ConfigHelper:
    """Helper class for parsing configuration values from environment variables."""

    def __init__(self, settings: Settings):
        """Initialize with settings instance.

        Args:
            settings: Application settings instance
        """
        self.settings = settings

    def get_bool(self, key: str, default: bool = False) -> bool:
        """Parse boolean from environment variable.

        Args:
            key: Environment variable key
            default: Default value if not set

        Returns:
            Boolean value
        """
        value = self.settings.get_env(key, str(default).lower())
        if value is None:
            return default
        return str(value).lower() in ("true", "1", "yes", "on")

    def get_int(self, key: str, default: int = 0) -> int:
        """Parse integer from environment variable with error handling.

        Args:
            key: Environment variable key
            default: Default value if not set or invalid

        Returns:
            Integer value
        """
        try:
            value = self.settings.get_env(key, str(default))
            return int(value) if value is not None else default
        except (ValueError, TypeError):
            return default

    def get_str(self, key: str, default: str = "") -> str:
        """Get string from environment variable.

        Args:
            key: Environment variable key
            default: Default value if not set

        Returns:
            String value
        """
        return self.settings.get_env(key, default) or default

    def get_str_optional(self, key: str) -> Optional[str]:
        """Get optional string from environment variable.

        Args:
            key: Environment variable key

        Returns:
            String value or None if not set/empty
        """
        value = self.settings.get_env(key)
        if value is None or str(value).strip() == "":
            return None
        return str(value)

    def get_list(
        self, key: str, default: Optional[List[str]] = None, separator: str = ","
    ) -> List[str]:
        """Parse list from environment variable.

        Args:
            key: Environment variable key
            default: Default list if not set
            separator: List item separator

        Returns:
            List of strings
        """
        if default is None:
            default = []

        value = self.settings.get_env(key)
        if not value or value.strip() == "":
            return default

        # Split and clean up items
        items = [item.strip() for item in value.split(separator)]
        return [item for item in items if item]  # Remove empty items

    def get_path_optional(self, key: str) -> Optional[Path]:
        """Get optional Path from environment variable.

        Args:
            key: Environment variable key

        Returns:
            Path object or None if not set
        """
        value = self.get_str_optional(key)
        return Path(value) if value else None

    def get_enum(self, key: str, enum_class: type, default: str) -> Any:
        """Parse enum from environment variable.

        Args:
            key: Environment variable key
            enum_class: Enum class to parse into
            default: Default enum value name

        Returns:
            Enum value
        """
        try:
            value = self.get_str(key, default)
            return enum_class(value)
        except (ValueError, TypeError):
            return enum_class(default)

    def get_octal_int(self, key: str, default: int) -> int:
        """Parse octal integer from environment variable.

        Args:
            key: Environment variable key
            default: Default octal value (e.g., 0o600)

        Returns:
            Integer value parsed from octal, falls back to default on error
        """
        try:
            value = self.settings.get_env(key)
            if value is None:
                return default

            str_value = str(value).strip()
            if not str_value:
                return default

            # Handle explicit octal prefix
            if str_value.startswith("0o"):
                return int(str_value, 8)

            # If all digits and likely octal range, treat as octal
            if str_value.isdigit() and 1 <= len(str_value) <= 4:
                octal_value = int(str_value, 8)
                # Validate reasonable permission range (standard file permissions only)
                if 0 <= octal_value <= 0o777:  # Standard file permissions only
                    return octal_value

            # Fallback to decimal with validation
            decimal_value = int(str_value)
            if 0 <= decimal_value <= 511:  # 0o777 in decimal
                return decimal_value

            return default
        except (ValueError, TypeError):
            return default


def _load_config_from_settings(settings: Settings) -> LogConfig:
    """Load logging configuration from application settings.

    Args:
        settings: Application settings

    Returns:
        LogConfig instance
    """
    config = ConfigHelper(settings)

    return LogConfig(
        # Basic logging settings
        level=config.get_enum("LOG_LEVEL", LogLevel, "INFO"),
        json_format=config.get_bool("LOG_JSON_FORMAT", True),
        log_file=config.get_path_optional("LOG_FILE"),
        # Alert settings
        enable_alerts=config.get_bool("LOG_ENABLE_ALERTS", True),
        alert_level=config.get_enum("LOG_ALERT_LEVEL", LogLevel, "ERROR"),
        # Slack configuration
        slack_webhook_url=config.get_str_optional("SLACK_WEBHOOK_URL"),
        slack_channel=config.get_str_optional("SLACK_CHANNEL"),
        # Email configuration
        smtp_host=config.get_str_optional("SMTP_HOST"),
        smtp_port=config.get_int("SMTP_PORT", 587),
        smtp_username=config.get_str_optional("SMTP_USERNAME"),
        smtp_password=config.get_str_optional("SMTP_PASSWORD"),
        email_from=config.get_str_optional("EMAIL_FROM"),
        email_to=config.get_list("EMAIL_TO"),
        # Sentry configuration
        sentry_dsn=config.get_str_optional("SENTRY_DSN"),
        sentry_environment=settings.environment,
        # Retention settings
        retention_days=config.get_int("LOG_RETENTION_DAYS", 30),
        max_log_size_mb=config.get_int("LOG_MAX_SIZE_MB", 100),
        # File permissions (security)
        log_file_permissions=config.get_octal_int("LOG_FILE_PERMISSIONS", 0o600),
        log_dir_permissions=config.get_octal_int("LOG_DIR_PERMISSIONS", 0o700),
        # Secret masking configuration
        enable_secret_masking=config.get_bool("LOG_ENABLE_SECRET_MASKING", True),
        secret_mask_string=config.get_str("LOG_SECRET_MASK_STRING", "***REDACTED***"),
        custom_sensitive_keys=config.get_list("LOG_CUSTOM_SENSITIVE_KEYS"),
        custom_secret_patterns=config.get_list("LOG_CUSTOM_SECRET_PATTERNS"),
        whitelist_patterns=config.get_list("LOG_WHITELIST_PATTERNS"),
        disabled_masking_loggers=config.get_list("LOG_DISABLED_MASKING_LOGGERS"),
        enable_audit_logging=config.get_bool("LOG_ENABLE_AUDIT_LOGGING", False),
        # Performance optimization settings
        max_recursion_depth=config.get_int("LOG_MAX_RECURSION_DEPTH", 10),
        enable_pattern_cache=config.get_bool("LOG_ENABLE_PATTERN_CACHE", True),
        pattern_cache_size=config.get_int("LOG_PATTERN_CACHE_SIZE", 1000),
    )


def get_logger(name: str) -> logging.Logger:
    """Get a logger instance with the given name.

    Args:
        name: Logger name (usually __name__)

    Returns:
        Configured logger instance
    """
    return logging.getLogger(name)


def check_log_permissions(
    settings: Settings, config: LogConfig | None = None
) -> dict[str, Any]:
    """Check and report on log file and directory permissions.

    This function verifies that log files and directories have appropriate
    security permissions and reports any issues found.

    Args:
        settings: Application settings
        config: Optional logging configuration override

    Returns:
        Dictionary with permission check results
    """
    if config is None:
        config = _load_config_from_settings(settings)

    results = {
        "checked": True,
        "platform": platform.system(),
        "issues": [],
        "warnings": [],
        "directories": {},
        "files": {},
    }

    # Skip detailed checks on Windows
    if platform.system() == "Windows":
        results["warnings"].append("Permission checks are limited on Windows platform")
        return results

    # Check log directory permissions
    if config.log_file:
        log_dir = config.log_file.parent
        if log_dir.exists():
            try:
                current_perms = log_dir.stat().st_mode & 0o777
                results["directories"][str(log_dir)] = {
                    "exists": True,
                    "current_permissions": oct(current_perms),
                    "expected_permissions": oct(config.log_dir_permissions),
                    "secure": current_perms <= config.log_dir_permissions,
                }

                if current_perms > config.log_dir_permissions:
                    results["issues"].append(
                        f"Log directory {log_dir} has overly permissive permissions: "
                        f"{oct(current_perms)} (expected: {oct(config.log_dir_permissions)})"
                    )
            except (OSError, PermissionError) as e:
                results["warnings"].append(
                    f"Could not check permissions on {log_dir}: {e}"
                )

        # Check log file permissions
        try:
            if config.log_file.exists():
                current_perms = config.log_file.stat().st_mode & 0o777
                results["files"][str(config.log_file)] = {
                    "exists": True,
                    "current_permissions": oct(current_perms),
                    "expected_permissions": oct(config.log_file_permissions),
                    "secure": current_perms <= config.log_file_permissions,
                }

                if current_perms > config.log_file_permissions:
                    results["issues"].append(
                        f"Log file {config.log_file} has overly permissive permissions: "
                        f"{oct(current_perms)} (expected: {oct(config.log_file_permissions)})"
                    )
        except (OSError, PermissionError) as e:
            results["warnings"].append(
                f"Could not check permissions on {config.log_file}: {e}"
            )

        # Check rotated log files
        for i in range(5):  # Default backupCount
            backup_file = Path(f"{config.log_file}.{i + 1}")
            try:
                if backup_file.exists():
                    current_perms = backup_file.stat().st_mode & 0o777
                    results["files"][str(backup_file)] = {
                        "exists": True,
                        "current_permissions": oct(current_perms),
                        "expected_permissions": oct(config.log_file_permissions),
                        "secure": current_perms <= config.log_file_permissions,
                    }

                    if current_perms > config.log_file_permissions:
                        results["issues"].append(
                            f"Backup log file {backup_file} has overly permissive permissions: "
                            f"{oct(current_perms)} (expected: {oct(config.log_file_permissions)})"
                        )
            except (OSError, PermissionError) as e:
                results["warnings"].append(
                    f"Could not check permissions on {backup_file}: {e}"
                )

    # Check audit log directory
    audit_dir = Path("/var/log/paidsearchnav/audits")
    if audit_dir.exists():
        try:
            current_perms = audit_dir.stat().st_mode & 0o777
            results["directories"][str(audit_dir)] = {
                "exists": True,
                "current_permissions": oct(current_perms),
                "expected_permissions": oct(config.log_dir_permissions),
                "secure": current_perms <= config.log_dir_permissions,
            }

            if current_perms > config.log_dir_permissions:
                results["issues"].append(
                    f"Audit directory {audit_dir} has overly permissive permissions: "
                    f"{oct(current_perms)} (expected: {oct(config.log_dir_permissions)})"
                )
        except (OSError, PermissionError) as e:
            results["warnings"].append(
                f"Could not check permissions on {audit_dir}: {e}"
            )

    results["secure"] = len(results["issues"]) == 0
    results["total_issues"] = len(results["issues"])
    results["total_warnings"] = len(results["warnings"])

    return results
