"""Tests for logging context management."""

from paidsearchnav.logging.context import (
    LogContext,
    add_context,
    clear_context,
    get_context,
    remove_context,
)


class TestLoggingContext:
    """Test logging context functions."""

    def setup_method(self):
        """Set up test method."""
        clear_context()

    def test_add_context(self):
        """Test adding context fields."""
        add_context(customer_id="123", job_id="abc")

        context = get_context()
        assert context["customer_id"] == "123"
        assert context["job_id"] == "abc"

    def test_clear_context(self):
        """Test clearing context."""
        add_context(field1="value1", field2="value2")
        assert len(get_context()) == 2

        clear_context()
        assert len(get_context()) == 0

    def test_remove_context(self):
        """Test removing specific fields."""
        add_context(field1="value1", field2="value2", field3="value3")

        remove_context("field1", "field3")

        context = get_context()
        assert "field1" not in context
        assert context["field2"] == "value2"
        assert "field3" not in context

    def test_context_isolation(self):
        """Test that context is isolated between async tasks."""
        # This is a simplified test - in real async code,
        # each task would have its own context
        add_context(task="task1")
        context1 = get_context()

        clear_context()
        add_context(task="task2")
        context2 = get_context()

        assert context1["task"] == "task1"
        assert context2["task"] == "task2"

    def test_context_update(self):
        """Test updating existing context fields."""
        add_context(field="value1")
        assert get_context()["field"] == "value1"

        add_context(field="value2")
        assert get_context()["field"] == "value2"


class TestLogContext:
    """Test LogContext context manager."""

    def setup_method(self):
        """Set up test method."""
        clear_context()

    def test_context_manager_basic(self):
        """Test basic context manager usage."""
        add_context(existing="value")

        with LogContext(customer_id="123", job_id="abc"):
            context = get_context()
            assert context["existing"] == "value"
            assert context["customer_id"] == "123"
            assert context["job_id"] == "abc"

        # Context should be restored
        context = get_context()
        assert context["existing"] == "value"
        assert "customer_id" not in context
        assert "job_id" not in context

    def test_nested_context_managers(self):
        """Test nested context managers."""
        with LogContext(level1="value1"):
            assert get_context()["level1"] == "value1"

            with LogContext(level2="value2"):
                context = get_context()
                assert context["level1"] == "value1"
                assert context["level2"] == "value2"

            # Inner context removed
            context = get_context()
            assert context["level1"] == "value1"
            assert "level2" not in context

        # All context removed
        assert len(get_context()) == 0

    def test_context_manager_with_exception(self):
        """Test context manager handles exceptions properly."""
        add_context(existing="value")

        try:
            with LogContext(temp="temporary"):
                assert get_context()["temp"] == "temporary"
                raise ValueError("Test error")
        except ValueError:
            pass

        # Context should still be restored
        context = get_context()
        assert context["existing"] == "value"
        assert "temp" not in context

    def test_context_manager_override(self):
        """Test context manager can override existing fields."""
        add_context(field="original")

        with LogContext(field="override"):
            assert get_context()["field"] == "override"

        # Original value restored
        assert get_context()["field"] == "original"
