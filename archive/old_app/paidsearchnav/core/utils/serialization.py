"""Secure JSON serialization utilities."""

import json
import logging
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from typing import Any
from uuid import UUID

from pydantic import SecretStr

logger = logging.getLogger(__name__)


class SerializationError(ValueError):
    """Raised when serialization fails."""

    pass


def safe_json_serializer(obj: Any) -> Any:
    """Safely serialize objects to JSON with explicit type handling.

    This function explicitly handles known types and avoids the security
    risk of using default=str which could expose sensitive object internals.

    Args:
        obj: Object to serialize

    Returns:
        JSON string representation

    Raises:
        SerializationError: If object type is not supported for serialization
    """
    if isinstance(obj, str):
        return obj
    elif isinstance(obj, (int, float, bool)):
        return obj
    elif obj is None:
        return None
    elif isinstance(obj, datetime):
        return obj.isoformat()
    elif isinstance(obj, date):
        return obj.isoformat()
    elif isinstance(obj, Decimal):
        return float(obj)
    elif isinstance(obj, UUID):
        return str(obj)
    elif isinstance(obj, Path):
        return str(obj)
    elif isinstance(obj, Enum):
        return obj.value
    elif isinstance(obj, SecretStr):
        # Never serialize secret values - return placeholder
        return "***REDACTED***"
    elif hasattr(obj, "model_dump"):
        # Pydantic models
        return obj.model_dump()
    elif hasattr(obj, "dict"):
        # Legacy Pydantic models
        return obj.dict()
    elif isinstance(obj, dict):
        return {k: safe_json_serializer(v) for k, v in obj.items()}
    elif isinstance(obj, (list, tuple)):
        return [safe_json_serializer(item) for item in obj]
    elif isinstance(obj, set):
        return list(obj)  # Convert sets to lists
    else:
        # Log unsupported type and raise error instead of exposing internals
        logger.warning(f"Unsupported type for JSON serialization: {type(obj).__name__}")
        raise SerializationError(
            f"Cannot serialize object of type {type(obj).__name__}"
        )


def safe_json_dumps(data: Any, indent: int | None = None, **kwargs: Any) -> str:
    """Safely dump data to JSON string.

    Args:
        data: Data to serialize
        indent: JSON indentation (None for compact)
        **kwargs: Additional arguments for json.dumps

    Returns:
        JSON string

    Raises:
        SerializationError: If serialization fails
    """
    try:
        return json.dumps(data, default=safe_json_serializer, indent=indent, **kwargs)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization failed: {e}")
        raise SerializationError(f"JSON serialization failed: {e}") from e


def safe_json_dump(
    data: Any, fp: Any, indent: int | None = None, **kwargs: Any
) -> None:
    """Safely dump data to JSON file.

    Args:
        data: Data to serialize
        fp: File-like object to write to
        indent: JSON indentation (None for compact)
        **kwargs: Additional arguments for json.dump

    Raises:
        SerializationError: If serialization fails
    """
    try:
        json.dump(data, fp, default=safe_json_serializer, indent=indent, **kwargs)
    except (TypeError, ValueError) as e:
        logger.error(f"JSON serialization to file failed: {e}")
        raise SerializationError(f"JSON serialization to file failed: {e}") from e


def sanitize_for_logging(data: Any) -> Any:
    """Sanitize data for safe logging.

    This function recursively processes data structures and redacts
    potentially sensitive information before logging. It works alongside
    the existing secret masking system and only handles explicit
    sensitive values, not general content.

    Args:
        data: Data to sanitize

    Returns:
        Sanitized data safe for logging
    """
    if isinstance(data, SecretStr):
        return "***REDACTED***"
    elif isinstance(data, dict):
        sanitized = {}
        for key, value in data.items():
            # Redact keys that explicitly contain sensitive info
            if any(
                keyword in key.lower()
                for keyword in [
                    "password",
                    "token",
                    "key",
                    "secret",
                    "auth",
                    "credential",
                ]
            ):
                sanitized[key] = "***REDACTED***"
            else:
                sanitized[key] = sanitize_for_logging(value)
        return sanitized
    elif isinstance(data, (list, tuple)):
        return [sanitize_for_logging(item) for item in data]
    elif isinstance(data, set):
        return {sanitize_for_logging(item) for item in data}
    else:
        # For strings and other types, let the existing secret masking system handle them
        return data
