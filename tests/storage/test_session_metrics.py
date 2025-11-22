"""Tests for session metrics optimization."""

import time
from unittest.mock import patch

import pytest

from paidsearchnav.storage.session_metrics import (
    SessionMetrics,
    configure_session_metrics,
    get_session_metrics,
)


class TestSessionMetrics:
    """Test session metrics functionality."""

    def test_session_metrics_initialization(self):
        """Test session metrics initialization."""
        metrics = SessionMetrics(log_interval=30.0, enabled=True)
        assert metrics.enabled is True
        assert metrics.log_interval == 30.0
        assert metrics.get_active_sessions() == 0
        assert metrics.get_total_sessions() == 0

    def test_session_opened_closed(self):
        """Test session open/close tracking."""
        metrics = SessionMetrics(enabled=True)

        # Open a session
        metrics.session_opened("test_op", "customer123")
        assert metrics.get_active_sessions("test_op") == 1
        assert metrics.get_total_sessions("test_op") == 1

        # Close the session successfully
        metrics.session_closed("test_op", success=True)
        assert metrics.get_active_sessions("test_op") == 0
        assert metrics.get_total_sessions("test_op") == 1
        assert metrics._counters["test_op_success"] == 1
        assert metrics._counters.get("test_op_failed", 0) == 0

    def test_session_failed(self):
        """Test failed session tracking."""
        metrics = SessionMetrics(enabled=True)

        # Open and fail a session
        metrics.session_opened("test_op")
        metrics.session_closed("test_op", success=False)

        assert metrics.get_active_sessions("test_op") == 0
        assert metrics._counters["test_op_failed"] == 1
        assert metrics._counters.get("test_op_success", 0) == 0

    def test_multiple_operations(self):
        """Test tracking multiple operations."""
        metrics = SessionMetrics(enabled=True)

        # Open sessions for different operations
        metrics.session_opened("save_analysis", "customer1")
        metrics.session_opened("get_analysis")
        metrics.session_opened("save_analysis", "customer2")

        assert metrics.get_active_sessions("save_analysis") == 2
        assert metrics.get_active_sessions("get_analysis") == 1
        assert metrics.get_active_sessions() == 3  # Total active

        # Close some sessions
        metrics.session_closed("save_analysis", success=True)
        metrics.session_closed("get_analysis", success=True)

        assert metrics.get_active_sessions("save_analysis") == 1
        assert metrics.get_active_sessions("get_analysis") == 0
        assert metrics.get_active_sessions() == 1

    def test_customer_tracking(self):
        """Test customer-specific session tracking."""
        metrics = SessionMetrics(enabled=True)

        # Track sessions for different customers
        metrics.session_opened("test_op", "customer1")
        metrics.session_opened("test_op", "customer1")
        metrics.session_opened("test_op", "customer2")

        assert metrics._counters["customer_customer1_sessions"] == 2
        assert metrics._counters["customer_customer2_sessions"] == 1

    def test_disabled_metrics(self):
        """Test that disabled metrics don't track anything."""
        metrics = SessionMetrics(enabled=False)

        # Try to track sessions
        metrics.session_opened("test_op", "customer1")
        metrics.session_closed("test_op", success=True)

        # Nothing should be tracked
        assert metrics.get_active_sessions() == 0
        assert metrics.get_total_sessions() == 0
        assert len(metrics._counters) == 0

    @patch("paidsearchnav.storage.session_metrics.logger")
    def test_metrics_logging(self, mock_logger):
        """Test metrics logging."""
        metrics = SessionMetrics(log_interval=0.1, enabled=True)

        # Track some sessions
        metrics.session_opened("save_analysis", "customer1")
        metrics.session_closed("save_analysis", success=True)
        metrics.session_opened("get_analysis")

        # Force logging
        metrics.force_log_metrics()

        # Check that info and debug logs were called
        assert mock_logger.info.called
        assert mock_logger.debug.called

        # Check log content
        info_call = mock_logger.info.call_args[0][0]
        assert "Total sessions: 2" in info_call
        assert "Active sessions: 1" in info_call

    @patch("paidsearchnav.storage.session_metrics.logger")
    def test_auto_logging_interval(self, mock_logger):
        """Test automatic logging based on interval."""
        metrics = SessionMetrics(log_interval=0.1, enabled=True)

        # Track a session
        metrics.session_opened("test_op")

        # Initial log shouldn't happen yet
        assert not mock_logger.info.called

        # Wait for interval and track another session
        time.sleep(0.15)
        metrics.session_opened("test_op")

        # Now logging should have occurred
        assert mock_logger.info.called

    def test_reset_metrics(self):
        """Test resetting metrics."""
        metrics = SessionMetrics(enabled=True)

        # Track some sessions
        metrics.session_opened("test_op", "customer1")
        metrics.session_closed("test_op", success=True)

        assert metrics.get_total_sessions() > 0
        assert len(metrics._counters) > 0

        # Reset
        metrics.reset_metrics()

        assert metrics.get_total_sessions() == 0
        assert len(metrics._counters) == 0
        assert len(metrics._active_sessions) == 0

    def test_thread_safety(self):
        """Test thread-safe operations."""
        metrics = SessionMetrics(enabled=True)

        def open_close_sessions(op_name, count):
            for i in range(count):
                metrics.session_opened(op_name, f"customer{i}")
                time.sleep(0.001)  # Small delay
                metrics.session_closed(op_name, success=True)

        # Run concurrent operations
        import threading

        threads = []
        for i in range(5):
            t = threading.Thread(target=open_close_sessions, args=(f"op{i}", 10))
            threads.append(t)
            t.start()

        for t in threads:
            t.join()

        # Check totals
        total_sessions = metrics.get_total_sessions()
        assert total_sessions == 50  # 5 operations * 10 sessions each
        assert metrics.get_active_sessions() == 0  # All closed

    def test_memory_management_customer_limit(self):
        """Test that customer entries are limited to prevent unbounded growth."""
        metrics = SessionMetrics(enabled=True, max_customer_entries=5)

        # Track sessions for more customers than the limit
        for i in range(10):
            metrics.session_opened("test_op", f"customer{i}")
            metrics.session_closed("test_op", success=True)

        # Check that only the most recent customers are tracked
        assert len(metrics._customer_counters) <= 5

        # Most recent customers should still be present
        assert "customer9" in metrics._customer_counters
        assert "customer8" in metrics._customer_counters

        # Oldest customers should have been evicted
        assert "customer0" not in metrics._customer_counters
        assert "customer1" not in metrics._customer_counters

    def test_cleanup_inactive_operations(self):
        """Test cleanup of inactive operation metrics."""
        metrics = SessionMetrics(enabled=True)

        # Create some operations
        metrics.session_opened("op1")
        metrics.session_closed("op1", success=True)
        metrics.session_opened("op2")
        metrics.session_closed("op2", success=False)

        # Verify counters exist
        assert "op1_opened" in metrics._counters
        assert "op1_success" in metrics._counters
        assert "op2_opened" in metrics._counters
        assert "op2_failed" in metrics._counters

        # Manually trigger cleanup
        metrics.cleanup_old_metrics()

        # Inactive operations should be removed
        assert "op1_opened" not in metrics._counters
        assert "op1_success" not in metrics._counters
        assert "op2_opened" not in metrics._counters
        assert "op2_failed" not in metrics._counters

    def test_cleanup_preserves_active_operations(self):
        """Test that cleanup preserves active operations."""
        metrics = SessionMetrics(enabled=True)

        # Create active and inactive operations
        metrics.session_opened("active_op")
        metrics.session_opened("inactive_op")
        metrics.session_closed("inactive_op", success=True)

        # Manually trigger cleanup
        metrics.cleanup_old_metrics()

        # Active operation should be preserved
        assert "active_op_opened" in metrics._counters
        assert metrics.get_active_sessions("active_op") == 1

        # Inactive operation should be removed
        assert "inactive_op_opened" not in metrics._counters

    @patch("paidsearchnav.storage.session_metrics.logger")
    def test_automatic_cleanup(self, mock_logger):
        """Test automatic cleanup based on interval."""
        metrics = SessionMetrics(enabled=True, cleanup_interval=0.1)

        # Create some operations
        metrics.session_opened("test_op")
        metrics.session_closed("test_op", success=True)

        # First operation shouldn't trigger cleanup
        assert not any(
            "Cleaned up" in str(call) for call in mock_logger.debug.call_args_list
        )

        # Wait for cleanup interval
        time.sleep(0.15)

        # Next operation should trigger cleanup
        metrics.session_opened("test_op2")

        # Check that cleanup was logged
        assert any(
            "Cleaned up" in str(call) for call in mock_logger.debug.call_args_list
        )

    def test_global_session_metrics(self):
        """Test global session metrics instance."""
        # Get global instance
        metrics1 = get_session_metrics()
        metrics2 = get_session_metrics()

        # Should be the same instance
        assert metrics1 is metrics2

        # Configure new instance
        configure_session_metrics(
            log_interval=123.0,
            enabled=False,
            max_customer_entries=5000,
            cleanup_interval=1800.0,
        )
        metrics3 = get_session_metrics()

        # Should be different instance with new config
        assert metrics3 is not metrics1
        assert metrics3.log_interval == 123.0
        assert metrics3.enabled is False
        assert metrics3.max_customer_entries == 5000
        assert metrics3.cleanup_interval == 1800.0


@pytest.mark.asyncio
class TestSessionMetricsIntegration:
    """Integration tests for session metrics with repository."""

    async def test_repository_integration(self):
        """Test session metrics integration with repository operations."""
        from paidsearchnav.core.config import Settings
        from paidsearchnav.storage.repository import AnalysisRepository

        # Create settings with session logging config
        settings = Settings.from_env()
        settings.logging.session_logging.enabled = True
        settings.logging.session_logging.detailed_logging = False
        settings.logging.session_logging.metrics_interval = 30.0

        # Create repository (would use session metrics)
        repo = AnalysisRepository(settings)

        # Verify session metrics are configured
        assert repo.session_metrics.enabled is True
        assert repo.detailed_logging is False
        assert repo.session_metrics.log_interval == 30.0
