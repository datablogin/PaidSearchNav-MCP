"""Tests for secure JSON serialization utilities."""

import json
import tempfile
from datetime import date, datetime
from decimal import Decimal
from enum import Enum
from pathlib import Path
from uuid import UUID

import pytest
from pydantic import BaseModel, SecretStr

from paidsearchnav_mcp.core.utils.serialization import (
    SerializationError,
    safe_json_dump,
    safe_json_dumps,
    safe_json_serializer,
    sanitize_for_logging,
)


class SampleEnum(Enum):
    """Sample enum for serialization testing."""

    VALUE_A = "a"
    VALUE_B = "b"


class SampleModel(BaseModel):
    """Sample Pydantic model for serialization testing."""

    name: str
    value: int


class TestSafeJsonSerializer:
    """Test safe_json_serializer function."""

    def test_basic_types(self):
        """Test serialization of basic types."""
        assert safe_json_serializer("string") == "string"
        assert safe_json_serializer(42) == 42
        assert safe_json_serializer(3.14) == 3.14
        assert safe_json_serializer(True) is True
        assert safe_json_serializer(False) is False
        assert safe_json_serializer(None) is None

    def test_datetime_serialization(self):
        """Test datetime serialization."""
        dt = datetime(2023, 1, 1, 12, 0, 0)
        result = safe_json_serializer(dt)
        assert result == "2023-01-01T12:00:00"

    def test_date_serialization(self):
        """Test date serialization."""
        d = date(2023, 1, 1)
        result = safe_json_serializer(d)
        assert result == "2023-01-01"

    def test_decimal_serialization(self):
        """Test Decimal serialization."""
        decimal_val = Decimal("123.45")
        result = safe_json_serializer(decimal_val)
        assert result == 123.45

    def test_uuid_serialization(self):
        """Test UUID serialization."""
        uuid_val = UUID("12345678-1234-5678-9012-123456789012")
        result = safe_json_serializer(uuid_val)
        assert result == "12345678-1234-5678-9012-123456789012"

    def test_path_serialization(self):
        """Test Path serialization."""
        path = Path("/test/path")
        result = safe_json_serializer(path)
        assert result == "/test/path"

    def test_enum_serialization(self):
        """Test Enum serialization."""
        result = safe_json_serializer(SampleEnum.VALUE_A)
        assert result == "a"

    def test_secret_str_serialization(self):
        """Test SecretStr is redacted."""
        secret = SecretStr("secret_value")
        result = safe_json_serializer(secret)
        assert result == "***REDACTED***"

    def test_pydantic_model_serialization(self):
        """Test Pydantic model serialization."""
        model = SampleModel(name="test", value=42)
        result = safe_json_serializer(model)
        assert result == {"name": "test", "value": 42}

    def test_dict_serialization(self):
        """Test dictionary serialization."""
        data = {"string": "value", "number": 42, "nested": {"inner": "data"}}
        result = safe_json_serializer(data)
        assert result == {"string": "value", "number": 42, "nested": {"inner": "data"}}

    def test_list_serialization(self):
        """Test list serialization."""
        data = ["a", 1, True, None]
        result = safe_json_serializer(data)
        assert result == ["a", 1, True, None]

    def test_tuple_serialization(self):
        """Test tuple serialization."""
        data = ("a", 1, True)
        result = safe_json_serializer(data)
        assert result == ["a", 1, True]

    def test_set_serialization(self):
        """Test set serialization."""
        data = {1, 2, 3}
        result = safe_json_serializer(data)
        assert sorted(result) == [1, 2, 3]

    def test_unsupported_type_raises_error(self):
        """Test unsupported type raises SerializationError."""

        class UnsupportedType:
            pass

        with pytest.raises(SerializationError) as exc_info:
            safe_json_serializer(UnsupportedType())

        assert "Cannot serialize object of type UnsupportedType" in str(exc_info.value)

    def test_nested_complex_structure(self):
        """Test nested complex data structure."""
        data = {
            "timestamp": datetime(2023, 1, 1),
            "secret": SecretStr("hidden"),
            "enum_val": SampleEnum.VALUE_B,
            "nested": {
                "uuid": UUID("12345678-1234-5678-9012-123456789012"),
                "decimal": Decimal("99.99"),
                "list": [1, 2, 3],
            },
        }

        result = safe_json_serializer(data)

        assert result["timestamp"] == "2023-01-01T00:00:00"
        assert result["secret"] == "***REDACTED***"
        assert result["enum_val"] == "b"
        assert result["nested"]["uuid"] == "12345678-1234-5678-9012-123456789012"
        assert result["nested"]["decimal"] == 99.99
        assert result["nested"]["list"] == [1, 2, 3]


class TestSafeJsonDumps:
    """Test safe_json_dumps function."""

    def test_basic_dumps(self):
        """Test basic JSON dumps functionality."""
        data = {"key": "value", "number": 42}
        result = safe_json_dumps(data)
        assert json.loads(result) == data

    def test_dumps_with_indent(self):
        """Test JSON dumps with indentation."""
        data = {"key": "value"}
        result = safe_json_dumps(data, indent=2)
        assert "\n" in result  # Should have newlines due to indentation

    def test_dumps_with_secret_str(self):
        """Test dumps properly handles SecretStr."""
        data = {"secret": SecretStr("hidden"), "normal": "visible"}
        result = safe_json_dumps(data)
        parsed = json.loads(result)

        assert parsed["secret"] == "***REDACTED***"
        assert parsed["normal"] == "visible"

    def test_dumps_error_handling(self):
        """Test error handling in dumps."""
        # Create a circular reference that would cause issues
        circular = {}
        circular["self"] = circular

        # Our serializer should catch this and raise SerializationError
        with pytest.raises(SerializationError):
            safe_json_dumps(circular)


class TestSafeJsonDump:
    """Test safe_json_dump function."""

    def test_dump_to_file(self):
        """Test dumping JSON to file."""
        data = {"key": "value", "secret": SecretStr("hidden")}

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            safe_json_dump(data, f)
            f.seek(0)
            content = f.read()

        parsed = json.loads(content)
        assert parsed["key"] == "value"
        assert parsed["secret"] == "***REDACTED***"

    def test_dump_with_indent(self):
        """Test dumping with indentation."""
        data = {"key": "value"}

        with tempfile.NamedTemporaryFile(mode="w+", delete=False) as f:
            safe_json_dump(data, f, indent=2)
            f.seek(0)
            content = f.read()

        assert "\n" in content  # Should have newlines


class TestSanitizeForLogging:
    """Test sanitize_for_logging function."""

    def test_secret_str_sanitization(self):
        """Test SecretStr is sanitized."""
        secret = SecretStr("secret_value")
        result = sanitize_for_logging(secret)
        assert result == "***REDACTED***"

    def test_sensitive_keys_sanitization(self):
        """Test sensitive dictionary keys are sanitized."""
        data = {
            "password": "secret123",
            "api_key": "key123",
            "auth_token": "token123",
            "client_secret": "secret456",
            "credential": "cred123",
            "normal_field": "visible_value",
        }

        result = sanitize_for_logging(data)

        assert result["password"] == "***REDACTED***"
        assert result["api_key"] == "***REDACTED***"
        assert result["auth_token"] == "***REDACTED***"
        assert result["client_secret"] == "***REDACTED***"
        assert result["credential"] == "***REDACTED***"
        assert result["normal_field"] == "visible_value"

    def test_case_insensitive_key_detection(self):
        """Test case-insensitive detection of sensitive keys."""
        data = {
            "PASSWORD": "secret123",
            "Api_Key": "key123",
            "AUTH_TOKEN": "token123",
            "normal_field": "visible",
        }

        result = sanitize_for_logging(data)

        assert result["PASSWORD"] == "***REDACTED***"
        assert result["Api_Key"] == "***REDACTED***"
        assert result["AUTH_TOKEN"] == "***REDACTED***"
        assert result["normal_field"] == "visible"

    def test_nested_structure_sanitization(self):
        """Test sanitization works on nested structures."""
        data = {
            "config": {"database_password": "secret123", "timeout": 30},
            "user_data": [
                {"username": "user", "password": "secret456"},
                {"api_key": "key789", "endpoint": "http://example.com"},
            ],
            "settings": {"secret_key": "secret789", "normal_setting": "visible"},
        }

        result = sanitize_for_logging(data)

        assert result["config"]["database_password"] == "***REDACTED***"
        assert result["config"]["timeout"] == 30
        assert result["user_data"][0]["password"] == "***REDACTED***"
        assert result["user_data"][0]["username"] == "user"
        assert result["user_data"][1]["api_key"] == "***REDACTED***"
        assert result["user_data"][1]["endpoint"] == "http://example.com"
        assert result["settings"]["secret_key"] == "***REDACTED***"
        assert result["settings"]["normal_setting"] == "visible"

    def test_list_sanitization(self):
        """Test list sanitization."""
        data = [
            "normal_value",
            {"password": "secret123", "name": "test"},
            SecretStr("hidden"),
        ]

        result = sanitize_for_logging(data)

        assert result[0] == "normal_value"
        assert result[1]["password"] == "***REDACTED***"
        assert result[1]["name"] == "test"
        assert result[2] == "***REDACTED***"

    def test_set_sanitization(self):
        """Test set sanitization."""
        data = {"item1", SecretStr("secret"), "item2"}

        result = sanitize_for_logging(data)

        # Sets are unordered, so we check if sanitized values are present
        assert "item1" in result
        assert "item2" in result
        assert "***REDACTED***" in result

    def test_non_sensitive_data_unchanged(self):
        """Test non-sensitive data is unchanged."""
        data = {
            "name": "John Doe",
            "age": 30,
            "preferences": ["music", "sports"],
            "settings": {"theme": "dark", "language": "en"},
        }

        result = sanitize_for_logging(data)
        assert result == data

    def test_basic_types_unchanged(self):
        """Test basic types are unchanged."""
        assert sanitize_for_logging("string") == "string"
        assert sanitize_for_logging(42) == 42
        assert sanitize_for_logging(3.14) == 3.14
        assert sanitize_for_logging(True) is True
        assert sanitize_for_logging(None) is None


class TestSecurityScenarios:
    """Test security-focused scenarios."""

    def test_prevents_secret_exposure_in_complex_object(self):
        """Test that secrets are not exposed in complex nested objects."""
        data = {
            "user": {
                "id": 123,
                "profile": {
                    "name": "John",
                    "auth": {
                        "password": "secret123",
                        "api_key": "sk-abcd1234",
                        "refresh_token": "rt-xyz789",
                    },
                },
            },
            "config": {
                "database": {
                    "host": "localhost",
                    "password": "db_secret",
                    "port": 5432,
                },
                "external_apis": [
                    {
                        "name": "service1",
                        "secret": SecretStr("service_secret"),
                        "endpoint": "https://api.service1.com",
                    }
                ],
            },
        }

        # Test both serialization and sanitization
        serialized = safe_json_serializer(data)
        sanitized = sanitize_for_logging(serialized)

        # Verify no secrets leak through
        json_str = safe_json_dumps(sanitized)

        assert "secret123" not in json_str
        assert "sk-abcd1234" not in json_str
        assert "rt-xyz789" not in json_str
        assert "db_secret" not in json_str
        assert "service_secret" not in json_str

        # Verify non-sensitive data is preserved
        assert "John" in json_str
        assert "localhost" in json_str
        assert "5432" in json_str
        assert "service1" in json_str
        assert "https://api.service1.com" in json_str

    def test_malicious_object_protection(self):
        """Test protection against malicious objects."""

        class MaliciousObject:
            def __str__(self):
                return "SECRET_DATA_EXPOSED"

            def __repr__(self):
                return "SECRET_DATA_EXPOSED"

        # Our serializer should not call str() on unknown objects
        with pytest.raises(SerializationError):
            safe_json_serializer(MaliciousObject())

    def test_large_data_structure_performance(self):
        """Test performance with large data structures."""
        # Create a large nested structure
        large_data = {
            "users": [
                {
                    "id": i,
                    "name": f"user_{i}",
                    "password": f"secret_{i}",
                    "settings": {"theme": "dark", "api_key": f"key_{i}"},
                }
                for i in range(100)
            ]
        }

        # This should complete without timeout/memory issues
        result = sanitize_for_logging(large_data)

        # Verify sanitization worked
        for user in result["users"]:
            assert user["password"] == "***REDACTED***"
            assert user["settings"]["api_key"] == "***REDACTED***"
            assert "user_" in user["name"]  # Non-sensitive data preserved
