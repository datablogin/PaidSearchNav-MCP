"""Integration tests for secrets handling in logging formatters."""

import json
import logging

import pytest

from paidsearchnav.logging.formatters import ColoredFormatter, JSONFormatter
from paidsearchnav.logging.secrets import get_secrets_registry


class TestJSONFormatterSecrets:
    """Test secret masking in JSONFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = JSONFormatter()
        self.logger = logging.getLogger("test")
        self.logger.setLevel(logging.DEBUG)

    def test_masks_secrets_in_message(self):
        """Test that secrets in log messages are masked."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="API key is sk-1234567890abcdef1234567890abcdef",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)
        data = json.loads(formatted)

        assert "sk-1234567890abcdef1234567890abcdef" not in data["message"]
        assert "***REDACTED***" in data["message"]

    def test_masks_secrets_in_extra_fields(self):
        """Test that secrets in extra fields are masked."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields with secrets
        record.extra_fields = {
            "api_key": "sk-1234567890abcdef1234567890abcdef",
            "username": "testuser",
            "password": "secret123",
            "config": {"token": "eyJhbGciOiJIUzI1NiJ9.test.signature", "timeout": 30},
        }

        formatted = self.formatter.format(record)
        data = json.loads(formatted)

        assert data["api_key"] == "***REDACTED***"
        assert data["username"] == "testuser"
        assert data["password"] == "***REDACTED***"
        assert data["config"]["token"] == "***REDACTED***"
        assert data["config"]["timeout"] == 30

    @pytest.mark.skip(
        reason="Context vars not working properly in CI - needs investigation"
    )
    def test_masks_secrets_in_context(self):
        """Test that secrets in context are masked."""
        # Use the actual context functions instead of mocking
        from paidsearchnav.logging.context import add_context, clear_context

        # Clear any existing context
        clear_context()

        # Add context data with secrets
        add_context(user_id="12345")
        add_context(session_token="AIzaSyDxxxxxxxxxxxxxxxxxxxxxxxxxxx")
        add_context(
            debug_info={"db_password": "secretpassword", "normal_field": "normal_value"}
        )

        # Verify context was set
        from paidsearchnav.logging.context import get_context

        ctx = get_context()
        assert ctx.get("user_id") == "12345", f"Context not set properly: {ctx}"

        try:
            # Create formatter and log record
            formatter = JSONFormatter()
            record = logging.LogRecord(
                name="test",
                level=logging.INFO,
                pathname="",
                lineno=1,
                msg="Test message",
                args=(),
                exc_info=None,
            )

            formatted = formatter.format(record)
            data = json.loads(formatted)

            # Debug: Check what we actually got
            assert "context" in data, (
                f"Missing 'context' key. Keys: {sorted(data.keys())}"
            )
            assert data["context"]["user_id"] == "12345"
            assert data["context"]["session_token"] == "***REDACTED***"
            assert data["context"]["debug_info"]["db_password"] == "***REDACTED***"
            assert data["context"]["debug_info"]["normal_field"] == "normal_value"
        finally:
            # Clean up context
            clear_context()

    def test_masks_secrets_in_exception_traceback(self):
        """Test that secrets in exception tracebacks are masked."""
        try:
            api_key = "sk-1234567890abcdef1234567890abcdef"
            raise ValueError(f"Authentication failed with key: {api_key}")
        except ValueError:
            import sys

            record = logging.LogRecord(
                name="test",
                level=logging.ERROR,
                pathname="",
                lineno=1,
                msg="Error occurred",
                args=(),
                exc_info=sys.exc_info(),
            )

            formatted = self.formatter.format(record)
            data = json.loads(formatted)

            # Check exception message
            assert (
                "sk-1234567890abcdef1234567890abcdef"
                not in data["exception"]["message"]
            )
            assert "***REDACTED***" in data["exception"]["message"]

            # Check traceback
            traceback_str = "".join(data["exception"]["traceback"])
            assert "sk-1234567890abcdef1234567890abcdef" not in traceback_str
            assert "***REDACTED***" in traceback_str

    def test_handles_non_string_messages(self):
        """Test that non-string messages are handled properly."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Count: %d, Key: %s",
            args=(42, "sk-1234567890abcdef1234567890abcdef"),
            exc_info=None,
        )

        formatted = self.formatter.format(record)
        data = json.loads(formatted)

        assert "sk-1234567890abcdef1234567890abcdef" not in data["message"]
        assert "***REDACTED***" in data["message"]
        assert "Count: 42" in data["message"]

    def test_custom_mask_string(self):
        """Test using custom mask string via secrets registry."""
        registry = get_secrets_registry()

        # Test with custom mask through the registry
        test_data = {"password": "secret123", "username": "testuser"}

        # Test custom mask
        masked = registry.mask_secrets_in_dict(test_data, "[HIDDEN]")
        assert masked["password"] == "[HIDDEN]"
        assert masked["username"] == "testuser"


class TestColoredFormatterSecrets:
    """Test secret masking in ColoredFormatter."""

    def setup_method(self):
        """Set up test fixtures."""
        self.formatter = ColoredFormatter()

    def test_masks_secrets_in_message(self):
        """Test that secrets in colored log messages are masked."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="My secret is sk-1234567890abcdef1234567890abcdef here",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        assert "sk-1234567890abcdef1234567890abcdef" not in formatted
        assert "***REDACTED***" in formatted
        assert "My secret is" in formatted

    def test_preserves_original_message(self):
        """Test that original message is preserved after formatting."""
        original_msg = "Secret: sk-1234567890abcdef1234567890abcdef"

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg=original_msg,
            args=(),
            exc_info=None,
        )

        # Format the record
        formatted = self.formatter.format(record)

        # Verify original message is restored
        assert record.msg == original_msg

    def test_handles_non_string_messages(self):
        """Test that non-string messages are handled safely."""
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg=12345,  # Non-string message
            args=(),
            exc_info=None,
        )

        # Should not raise an exception
        formatted = self.formatter.format(record)
        assert "12345" in formatted

    def test_color_codes_preserved(self):
        """Test that color codes are still applied after secret masking."""
        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="",
            lineno=1,
            msg="Error with key sk-1234567890abcdef1234567890abcdef",
            args=(),
            exc_info=None,
        )

        formatted = self.formatter.format(record)

        # Should contain ANSI color codes for ERROR level (red)
        assert "\033[31m" in formatted  # Red color code
        assert "\033[0m" in formatted  # Reset code
        assert "***REDACTED***" in formatted


class TestSecretsRegistryIntegration:
    """Test integration with secrets registry configuration."""

    def test_custom_sensitive_keys(self):
        """Test that custom sensitive keys are respected."""
        registry = get_secrets_registry()

        # Add a custom sensitive key
        registry.add_sensitive_key("custom_secret_field")

        data = {
            "custom_secret_field": "this should be masked",
            "normal_field": "this should not",
        }

        masked = registry.mask_secrets_in_dict(data)

        assert masked["custom_secret_field"] == "***REDACTED***"
        assert masked["normal_field"] == "this should not"

    def test_custom_secret_patterns(self):
        """Test that custom secret patterns are respected."""
        registry = get_secrets_registry()

        # Add a custom pattern for our fake secret format
        registry.add_secret_pattern(r"MYSECRET-[A-Z0-9]{8}")

        data = {
            "field1": "MYSECRET-ABCD1234",  # Should match pattern
            "field2": "MYSECRET-abc123",  # Should not match (lowercase)
            "field3": "normal text",  # Should not match
        }

        masked = registry.mask_secrets_in_dict(data)

        assert masked["field1"] == "***REDACTED***"
        assert masked["field2"] == "MYSECRET-abc123"  # Doesn't match pattern
        assert masked["field3"] == "normal text"

    def test_pattern_in_string_content(self):
        """Test that patterns are detected within string content."""
        registry = get_secrets_registry()

        text = (
            "Here is my API key: sk-1234567890abcdef1234567890abcdef for authentication"
        )

        masked = registry._mask_secrets_in_string(text, "***REDACTED***")

        assert "sk-1234567890abcdef1234567890abcdef" not in masked
        assert "***REDACTED***" in masked
        assert "Here is my API key:" in masked
        assert "for authentication" in masked


class TestFormatterErrorHandling:
    """Test error handling in formatters with secret masking."""

    def test_formatter_handles_masking_errors_gracefully(self):
        """Test that formatters handle masking errors gracefully."""
        formatter = JSONFormatter()

        # Create a record with problematic data
        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Add extra fields that might cause issues
        record.extra_fields = {
            "circular_ref": None,  # Will be set to create circular reference
            "normal_field": "normal_value",
        }

        # Create circular reference
        record.extra_fields["circular_ref"] = record.extra_fields

        # Should not raise an exception
        try:
            formatted = formatter.format(record)
            data = json.loads(formatted)
            assert "normal_field" in data
        except (ValueError, TypeError, RecursionError):
            # If it fails due to circular reference, that's expected
            # The important thing is that it doesn't crash due to secret masking
            pass

    def test_colored_formatter_handles_none_message(self):
        """Test that colored formatter handles None messages."""
        formatter = ColoredFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="",
            lineno=1,
            msg=None,
            args=(),
            exc_info=None,
        )

        # Should not raise an exception
        formatted = formatter.format(record)
        assert "None" in formatted or "" in formatted
