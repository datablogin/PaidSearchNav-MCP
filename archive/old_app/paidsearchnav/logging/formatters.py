"""Custom log formatters for structured logging."""

import json
import logging
import traceback
from datetime import datetime, timezone
from typing import Optional

from paidsearchnav.core.utils import safe_json_dumps, sanitize_for_logging
from paidsearchnav.logging.context import get_context
from paidsearchnav.logging.secrets import mask_secrets


class JSONFormatter(logging.Formatter):
    """JSON formatter for structured logging."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as JSON.

        Args:
            record: Log record to format

        Returns:
            JSON-formatted log string
        """
        log_data = {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "level": record.levelname,
            "logger": record.name,
            "message": record.getMessage(),
            "module": record.module,
            "function": record.funcName,
            "line": record.lineno,
        }

        # Add context data
        context = get_context()
        if context:
            log_data["context"] = context

        # Add extra fields
        if hasattr(record, "extra_fields"):
            log_data.update(record.extra_fields)

        # Add exception info if present
        if record.exc_info and record.exc_info[0] is not None:
            # Get the raw traceback lines
            traceback_lines = traceback.format_exception(*record.exc_info)

            # Mask secrets in each traceback line individually to preserve structure
            masked_traceback = []
            for line in traceback_lines:
                masked_line = mask_secrets(line, logger_name=record.name)
                masked_traceback.append(masked_line)

            log_data["exception"] = {
                "type": record.exc_info[0].__name__,
                "message": mask_secrets(
                    str(record.exc_info[1]), logger_name=record.name
                ),
                "traceback": masked_traceback,
            }

        # Add common fields from record
        for field in ["customer_id", "analysis_id", "analyzer_name", "job_id"]:
            if hasattr(record, field):
                log_data[field] = getattr(record, field)

        # Mask any secrets in the log data before serializing
        from typing import Dict, cast

        masked_result = mask_secrets(log_data, logger_name=record.name)
        log_data = cast(Dict[str, object], masked_result)

        # Further sanitize for safe logging
        sanitized_data = sanitize_for_logging(log_data)

        return safe_json_dumps(sanitized_data)


class PrettyJSONFormatter(JSONFormatter):
    """Pretty-printed JSON formatter for development."""

    def format(self, record: logging.LogRecord) -> str:
        """Format log record as pretty-printed JSON.

        Args:
            record: Log record to format

        Returns:
            Pretty-printed JSON log string
        """
        # Get base JSON
        log_json = super().format(record)

        # Pretty print it
        log_dict = json.loads(log_json)
        return safe_json_dumps(log_dict, indent=2)


class ColoredFormatter(logging.Formatter):
    """Colored console formatter for development."""

    # Color codes
    COLORS = {
        "DEBUG": "\033[36m",  # Cyan
        "INFO": "\033[32m",  # Green
        "WARNING": "\033[33m",  # Yellow
        "ERROR": "\033[31m",  # Red
        "CRITICAL": "\033[35m",  # Magenta
    }
    RESET = "\033[0m"

    def __init__(self, fmt: Optional[str] = None, datefmt: Optional[str] = None):
        """Initialize colored formatter.

        Args:
            fmt: Log format string
            datefmt: Date format string
        """
        if fmt is None:
            fmt = "%(asctime)s - %(name)s - %(levelname)s - %(message)s"
        super().__init__(fmt, datefmt)

    def format(self, record: logging.LogRecord) -> str:
        """Format log record with colors.

        Args:
            record: Log record to format

        Returns:
            Colored log string
        """
        # Create a copy to avoid mutating the original record
        import copy

        record_copy = copy.copy(record)

        # Mask secrets in the message copy
        if isinstance(record_copy.msg, str):
            record_copy.msg = mask_secrets(record_copy.msg, logger_name=record.name)

        # Add color to level name in the copy
        if record_copy.levelname in self.COLORS:
            record_copy.levelname = f"{self.COLORS[record_copy.levelname]}{record_copy.levelname}{self.RESET}"

        # Format the copy
        result = super().format(record_copy)

        return result
