"""Unit tests for workflow monitoring."""

from datetime import datetime, timezone
from unittest.mock import patch

from paidsearchnav_mcp.orchestration.monitoring import (
    ExecutionInfo,
    WorkflowMetrics,
    WorkflowMonitor,
)


class TestWorkflowMetrics:
    """Test workflow metrics."""

    def test_metrics_initialization(self):
        """Test metrics are initialized correctly."""
        metrics = WorkflowMetrics()

        assert metrics.total_executions == 0
        assert metrics.successful_executions == 0
        assert metrics.failed_executions == 0
        assert metrics.cancelled_executions == 0
        assert metrics.total_execution_time == 0.0
        assert metrics.min_execution_time == float("inf")
        assert metrics.max_execution_time == 0.0
        assert metrics.average_execution_time == 0.0
        assert len(metrics.recent_execution_times) == 0
        assert len(metrics.error_counts) == 0

    def test_update_execution_time(self):
        """Test updating execution time metrics."""
        metrics = WorkflowMetrics()
        metrics.total_executions = 1

        metrics.update_execution_time(100.0)

        assert metrics.total_execution_time == 100.0
        assert metrics.min_execution_time == 100.0
        assert metrics.max_execution_time == 100.0
        assert metrics.average_execution_time == 100.0
        assert len(metrics.recent_execution_times) == 1
        assert metrics.recent_execution_times[0] == 100.0

    def test_update_execution_time_multiple(self):
        """Test updating execution time with multiple values."""
        metrics = WorkflowMetrics()
        metrics.total_executions = 3

        metrics.update_execution_time(50.0)
        metrics.update_execution_time(150.0)
        metrics.update_execution_time(100.0)

        assert metrics.total_execution_time == 300.0
        assert metrics.min_execution_time == 50.0
        assert metrics.max_execution_time == 150.0
        assert metrics.average_execution_time == 100.0
        assert len(metrics.recent_execution_times) == 3

    def test_get_recent_average_execution_time(self):
        """Test getting recent average execution time."""
        metrics = WorkflowMetrics()

        # Empty metrics
        assert metrics.get_recent_average_execution_time() == 0.0

        # With recent times
        metrics.update_execution_time(100.0)
        metrics.update_execution_time(200.0)

        assert metrics.get_recent_average_execution_time() == 150.0

    def test_get_success_rate(self):
        """Test getting success rate."""
        metrics = WorkflowMetrics()

        # No executions
        assert metrics.get_success_rate() == 0.0

        # With executions
        metrics.total_executions = 10
        metrics.successful_executions = 8

        assert metrics.get_success_rate() == 80.0

    def test_to_dict(self):
        """Test converting metrics to dictionary."""
        metrics = WorkflowMetrics()
        metrics.total_executions = 5
        metrics.successful_executions = 4
        metrics.failed_executions = 1
        metrics.update_execution_time(100.0)
        metrics.error_counts["timeout"] = 1

        result = metrics.to_dict()

        assert result["total_executions"] == 5
        assert result["successful_executions"] == 4
        assert result["failed_executions"] == 1
        assert result["success_rate_percent"] == 80.0
        assert result["total_execution_time"] == 100.0
        assert result["error_counts"]["timeout"] == 1


class TestExecutionInfo:
    """Test execution info."""

    def test_execution_info_initialization(self):
        """Test execution info initialization."""
        started_at = datetime.now(timezone.utc)

        info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="running",
            started_at=started_at,
        )

        assert info.execution_id == "exec_123"
        assert info.workflow_name == "test_workflow"
        assert info.customer_id == "customer_123"
        assert info.status == "running"
        assert info.started_at == started_at
        assert info.completed_at is None
        assert info.steps_completed == 0
        assert info.total_steps == 0

    def test_get_execution_time_running(self):
        """Test getting execution time for running workflow."""
        started_at = datetime.now(timezone.utc)

        info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="running",
            started_at=started_at,
        )

        execution_time = info.get_execution_time()
        assert execution_time >= 0
        assert execution_time < 1  # Should be very small since just created

    def test_get_execution_time_completed(self):
        """Test getting execution time for completed workflow."""
        started_at = datetime.now(timezone.utc)
        completed_at = started_at.replace(second=started_at.second + 10)

        info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
        )

        execution_time = info.get_execution_time()
        assert execution_time == 10.0

    def test_is_completed(self):
        """Test checking if execution is completed."""
        info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="running",
            started_at=datetime.now(timezone.utc),
        )

        assert not info.is_completed()

        info.status = "completed"
        assert info.is_completed()

        info.status = "failed"
        assert info.is_completed()

        info.status = "cancelled"
        assert info.is_completed()

    def test_to_dict(self):
        """Test converting execution info to dictionary."""
        started_at = datetime.now(timezone.utc)
        completed_at = started_at.replace(second=started_at.second + 10)

        info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
            error_message="Test error",
            steps_completed=3,
            total_steps=5,
        )

        result = info.to_dict()

        assert result["execution_id"] == "exec_123"
        assert result["workflow_name"] == "test_workflow"
        assert result["customer_id"] == "customer_123"
        assert result["status"] == "completed"
        assert result["execution_time_seconds"] == 10.0
        assert result["error_message"] == "Test error"
        assert result["steps_completed"] == 3
        assert result["total_steps"] == 5
        assert result["progress_percent"] == 60.0


class TestWorkflowMonitor:
    """Test workflow monitor."""

    def setup_method(self):
        """Set up test fixtures."""
        self.monitor = WorkflowMonitor()

    def test_monitor_initialization(self):
        """Test monitor initialization."""
        assert isinstance(self.monitor.metrics, WorkflowMetrics)
        assert len(self.monitor.active_executions) == 0
        assert len(self.monitor.recent_executions) == 0
        assert self.monitor.alerts_enabled is True

    def test_start_execution(self):
        """Test starting execution monitoring."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")

        assert "exec_123" in self.monitor.active_executions
        assert self.monitor.metrics.total_executions == 1
        assert self.monitor.metrics.customer_execution_counts["customer_123"] == 1
        assert self.monitor.metrics.workflow_type_counts["test_workflow"] == 1

        execution_info = self.monitor.active_executions["exec_123"]
        assert execution_info.execution_id == "exec_123"
        assert execution_info.workflow_name == "test_workflow"
        assert execution_info.customer_id == "customer_123"
        assert execution_info.status == "running"

    def test_update_execution_progress(self):
        """Test updating execution progress."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")

        self.monitor.update_execution_progress("exec_123", 2, 5)

        execution_info = self.monitor.active_executions["exec_123"]
        assert execution_info.steps_completed == 2
        assert execution_info.total_steps == 5

    def test_record_step_execution(self):
        """Test recording step execution."""
        self.monitor.record_step_execution("exec_123", "test_step", True)

        assert self.monitor.metrics.step_execution_counts["test_step"] == 1
        assert self.monitor.metrics.step_failure_counts["test_step"] == 0

        self.monitor.record_step_execution("exec_123", "test_step", False)

        assert self.monitor.metrics.step_execution_counts["test_step"] == 2
        assert self.monitor.metrics.step_failure_counts["test_step"] == 1

    def test_end_execution_success(self):
        """Test ending execution with success."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")

        self.monitor.end_execution("exec_123", "completed")

        assert "exec_123" not in self.monitor.active_executions
        assert self.monitor.metrics.successful_executions == 1
        assert self.monitor.metrics.failed_executions == 0
        assert len(self.monitor.recent_executions) == 1

        recent_execution = self.monitor.recent_executions[0]
        assert recent_execution.status == "completed"
        assert recent_execution.completed_at is not None

    def test_end_execution_failure(self):
        """Test ending execution with failure."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")

        self.monitor.end_execution("exec_123", "failed", "Test error")

        assert self.monitor.metrics.successful_executions == 0
        assert self.monitor.metrics.failed_executions == 1
        assert self.monitor.metrics.error_counts["other"] == 1  # Categorized error

        recent_execution = self.monitor.recent_executions[0]
        assert recent_execution.status == "failed"
        assert recent_execution.error_message == "Test error"

    def test_end_execution_unknown(self):
        """Test ending monitoring for unknown execution."""
        # Should not raise error, just log warning
        self.monitor.end_execution("unknown_exec", "completed")

        # Metrics should not be affected
        assert self.monitor.metrics.total_executions == 0

    def test_categorize_error(self):
        """Test error categorization."""
        # Test timeout error
        error_type = self.monitor._categorize_error("Request timeout occurred")
        assert error_type == "timeout"

        # Test network error
        error_type = self.monitor._categorize_error("Connection failed")
        assert error_type == "network"

        # Test authentication error
        error_type = self.monitor._categorize_error("Permission denied")
        assert error_type == "authentication"

        # Test validation error
        error_type = self.monitor._categorize_error("Invalid input data")
        assert error_type == "validation"

        # Test missing resource error
        error_type = self.monitor._categorize_error("File not found")
        assert error_type == "missing_resource"

        # Test quota error
        error_type = self.monitor._categorize_error("Quota limit exceeded")
        assert error_type == "quota_limit"

        # Test other error
        error_type = self.monitor._categorize_error("Some random error")
        assert error_type == "other"

    def test_get_active_executions(self):
        """Test getting active executions."""
        self.monitor.start_execution("exec_1", "workflow_1", "customer_1")
        self.monitor.start_execution("exec_2", "workflow_2", "customer_2")

        active = self.monitor.get_active_executions()

        assert len(active) == 2
        execution_ids = [exec_info["execution_id"] for exec_info in active]
        assert "exec_1" in execution_ids
        assert "exec_2" in execution_ids

    def test_get_recent_executions(self):
        """Test getting recent executions."""
        # Start and end some executions
        for i in range(5):
            exec_id = f"exec_{i}"
            self.monitor.start_execution(exec_id, "test_workflow", "customer_123")
            self.monitor.end_execution(exec_id, "completed")

        # Get all recent
        recent = self.monitor.get_recent_executions()
        assert len(recent) == 5

        # Get limited count
        recent = self.monitor.get_recent_executions(count=3)
        assert len(recent) == 3

    def test_get_metrics(self):
        """Test getting metrics."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")
        self.monitor.end_execution("exec_123", "completed")

        metrics = self.monitor.get_metrics()

        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["success_rate_percent"] == 100.0

    def test_get_dashboard_data(self):
        """Test getting dashboard data."""
        self.monitor.start_execution("exec_1", "test_workflow", "customer_123")
        self.monitor.start_execution("exec_2", "test_workflow", "customer_456")
        self.monitor.end_execution("exec_1", "completed")

        dashboard = self.monitor.get_dashboard_data()

        assert "metrics" in dashboard
        assert "active_executions" in dashboard
        assert "recent_executions" in dashboard
        assert "alerts" in dashboard

        assert len(dashboard["active_executions"]) == 1
        assert len(dashboard["recent_executions"]) == 1

    def test_reset_metrics(self):
        """Test resetting metrics."""
        self.monitor.start_execution("exec_123", "test_workflow", "customer_123")
        self.monitor.end_execution("exec_123", "completed")

        assert self.monitor.metrics.total_executions == 1

        self.monitor.reset_metrics()

        assert self.monitor.metrics.total_executions == 0
        assert self.monitor.metrics.successful_executions == 0

    @patch("paidsearchnav.orchestration.monitoring.logger")
    def test_check_alerts_long_execution(self, mock_logger):
        """Test alerts for long execution time."""
        self.monitor.execution_time_threshold = 100.0  # 100 seconds

        # Create execution info with long execution time
        started_at = datetime.now(timezone.utc)
        completed_at = started_at.replace(second=started_at.second + 150)

        execution_info = ExecutionInfo(
            execution_id="exec_123",
            workflow_name="test_workflow",
            customer_id="customer_123",
            status="completed",
            started_at=started_at,
            completed_at=completed_at,
        )

        self.monitor._check_alerts(execution_info)

        # Check that warning was logged
        mock_logger.warning.assert_called_once()
        assert "Long execution time alert" in mock_logger.warning.call_args[0][0]

    def test_get_current_alerts(self):
        """Test getting current alerts."""
        # Set low failure rate threshold
        self.monitor.failure_rate_threshold = 50.0

        # Create some failed executions
        for i in range(15):  # Need at least 10 executions
            exec_id = f"exec_{i}"
            self.monitor.start_execution(exec_id, "test_workflow", "customer_123")
            status = "failed" if i < 10 else "completed"  # 10 failed, 5 successful
            self.monitor.end_execution(
                exec_id, status, "Test error" if status == "failed" else None
            )

        alerts = self.monitor._get_current_alerts()

        # Should have high failure rate alert
        failure_alerts = [
            alert for alert in alerts if alert["type"] == "high_failure_rate"
        ]
        assert len(failure_alerts) == 1
        assert failure_alerts[0]["severity"] == "warning"

    def test_max_recent_executions(self):
        """Test maximum recent executions limit."""
        monitor = WorkflowMonitor(max_recent_executions=3)

        # Add more executions than the limit
        for i in range(5):
            exec_id = f"exec_{i}"
            monitor.start_execution(exec_id, "test_workflow", "customer_123")
            monitor.end_execution(exec_id, "completed")

        # Should only keep the last 3
        assert len(monitor.recent_executions) == 3

        # Should be the most recent ones
        execution_ids = [exec.execution_id for exec in monitor.recent_executions]
        assert "exec_2" in execution_ids
        assert "exec_3" in execution_ids
        assert "exec_4" in execution_ids
