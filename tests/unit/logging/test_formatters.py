"""Tests for log formatters."""

import json
import logging

from paidsearchnav_mcp.logging.context import add_context, clear_context
from paidsearchnav_mcp.logging.formatters import (
    ColoredFormatter,
    JSONFormatter,
    PrettyJSONFormatter,
)


class TestJSONFormatter:
    """Test JSON formatter."""

    def setup_method(self):
        """Set up test method."""
        clear_context()

    def test_basic_formatting(self):
        """Test basic JSON formatting."""
        formatter = JSONFormatter()

        # Create a log record
        record = logging.LogRecord(
            name="test.logger",
            level=logging.INFO,
            pathname="test.py",
            lineno=42,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        # Format it
        output = formatter.format(record)

        # Parse JSON
        data = json.loads(output)

        # Check fields
        assert data["level"] == "INFO"
        assert data["logger"] == "test.logger"
        assert data["message"] == "Test message"
        assert data["module"] == "test"
        # Function name might be None in test environment
        assert data["function"] in [None, "test_basic_formatting"]
        assert data["line"] == 42
        assert "timestamp" in data

    def test_formatting_with_context(self):
        """Test formatting with context data."""
        formatter = JSONFormatter()

        # Add context
        add_context(customer_id="123", job_id="abc")

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Check context
        assert data["context"]["customer_id"] == "123"
        assert data["context"]["job_id"] == "abc"

    def test_formatting_with_exception(self):
        """Test formatting with exception info."""
        formatter = JSONFormatter()

        # Create exception
        try:
            raise ValueError("Test error")
        except ValueError:
            import sys

            exc_info = sys.exc_info()

        record = logging.LogRecord(
            name="test",
            level=logging.ERROR,
            pathname="test.py",
            lineno=1,
            msg="Error occurred",
            args=(),
            exc_info=exc_info,
        )

        output = formatter.format(record)
        data = json.loads(output)

        # Check exception fields
        assert "exception" in data
        assert data["exception"]["type"] == "ValueError"
        assert data["exception"]["message"] == "Test error"
        assert isinstance(data["exception"]["traceback"], list)

    def test_formatting_with_extra_fields(self):
        """Test formatting with extra fields."""
        formatter = JSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        # Add extra fields
        record.customer_id = "123"
        record.analysis_id = "abc"
        record.extra_fields = {"custom": "value"}

        output = formatter.format(record)
        data = json.loads(output)

        # Check fields
        assert data["customer_id"] == "123"
        assert data["analysis_id"] == "abc"
        assert data["custom"] == "value"


class TestPrettyJSONFormatter:
    """Test pretty JSON formatter."""

    def test_pretty_formatting(self):
        """Test pretty JSON formatting."""
        formatter = PrettyJSONFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Check it's multi-line
        assert "\n" in output

        # Check it's valid JSON
        data = json.loads(output)
        assert data["message"] == "Test"


class TestColoredFormatter:
    """Test colored formatter."""

    def test_basic_formatting(self):
        """Test basic colored formatting."""
        formatter = ColoredFormatter()

        record = logging.LogRecord(
            name="test",
            level=logging.INFO,
            pathname="test.py",
            lineno=1,
            msg="Test message",
            args=(),
            exc_info=None,
        )

        output = formatter.format(record)

        # Check message is in output
        assert "Test message" in output

        # Check color codes are added
        assert "\033[" in output  # ANSI escape code

    def test_level_colors(self):
        """Test different colors for different levels."""
        formatter = ColoredFormatter()

        levels = [
            (logging.DEBUG, "36m"),  # Cyan
            (logging.INFO, "32m"),  # Green
            (logging.WARNING, "33m"),  # Yellow
            (logging.ERROR, "31m"),  # Red
            (logging.CRITICAL, "35m"),  # Magenta
        ]

        for level, color in levels:
            record = logging.LogRecord(
                name="test",
                level=level,
                pathname="test.py",
                lineno=1,
                msg="Test",
                args=(),
                exc_info=None,
            )

            output = formatter.format(record)
            assert color in output
