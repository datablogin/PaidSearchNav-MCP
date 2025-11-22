"""Tests for script scheduling and monitoring."""

from datetime import datetime, timedelta
from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptBase,
    ScriptConfig,
    ScriptExecutor,
    ScriptResult,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.scheduler import (
    ScriptExecution,
    ScriptMonitor,
    ScriptSchedule,
    ScriptScheduler,
)


class MockScript(ScriptBase):
    """Mock script for testing."""

    def generate_script(self) -> str:
        return "mock script"

    def process_results(self, results: dict) -> ScriptResult:
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=10,
            changes_made=5,
            errors=[],
            warnings=[],
            details={},
        )

    def get_required_parameters(self) -> list:
        return []


class TestScriptSchedule:
    """Test ScriptSchedule functionality."""

    def test_schedule_initialization(self):
        """Test schedule initialization."""
        schedule = ScriptSchedule(
            schedule_id="test_schedule",
            script_id="test_script",
            cron_expression="0 0 * * *",
            description="Daily at midnight",
        )

        assert schedule.schedule_id == "test_schedule"
        assert schedule.script_id == "test_script"
        assert schedule.cron_expression == "0 0 * * *"
        assert schedule.description == "Daily at midnight"
        assert schedule.enabled is True
        assert schedule.last_run is None
        assert schedule.next_run is not None

    def test_update_next_run(self):
        """Test updating next run time."""
        schedule = ScriptSchedule(
            schedule_id="test",
            script_id="test",
            cron_expression="0 0 * * *",  # Daily at midnight
            description="Test",
            enabled=False,
        )

        # Initially disabled, so no next run
        assert schedule.next_run is None

        # Enable and update
        schedule.enabled = True
        schedule.update_next_run()

        assert schedule.next_run is not None
        assert schedule.next_run > datetime.utcnow()

    def test_should_run(self):
        """Test checking if schedule should run."""
        schedule = ScriptSchedule(
            schedule_id="test",
            script_id="test",
            cron_expression="0 0 * * *",
            description="Test",
        )

        # Set next run to past
        past_time = datetime.utcnow() - timedelta(hours=1)
        schedule.next_run = past_time

        assert schedule.should_run() is True

        # Set next run to future
        future_time = datetime.utcnow() + timedelta(hours=1)
        schedule.next_run = future_time

        assert schedule.should_run() is False

        # Test disabled schedule
        schedule.enabled = False
        schedule.next_run = past_time

        assert schedule.should_run() is False

    def test_add_execution(self):
        """Test adding execution to history."""
        schedule = ScriptSchedule(
            schedule_id="test",
            script_id="test",
            cron_expression="0 0 * * *",
            description="Test",
            max_history=5,
        )

        # Add executions
        for i in range(7):
            execution = ScriptExecution(
                execution_id=f"exec_{i}",
                script_id="test",
                schedule_id="test",
                start_time=datetime.utcnow(),
                end_time=datetime.utcnow() + timedelta(seconds=10),
                status=ScriptStatus.COMPLETED,
                result=None,
                error=None,
            )
            schedule.add_execution(execution)

        # Should maintain max history
        assert len(schedule.execution_history) == 5
        assert schedule.execution_history[0].execution_id == "exec_2"
        assert schedule.execution_history[-1].execution_id == "exec_6"

        # Should update last run
        assert schedule.last_run is not None


class TestScriptScheduler:
    """Test ScriptScheduler functionality."""

    @pytest.fixture
    def executor(self):
        """Create a mock script executor."""
        client = Mock(spec=GoogleAdsClient)
        return ScriptExecutor(client)

    @pytest.fixture
    def scheduler(self, executor):
        """Create a script scheduler."""
        return ScriptScheduler(executor, max_workers=2)

    @pytest.fixture
    def mock_script(self):
        """Create a mock script."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
        )
        return MockScript(client, config)

    def test_initialization(self, scheduler):
        """Test scheduler initialization."""
        assert scheduler.schedules == {}
        assert scheduler.running_executions == {}
        assert scheduler._running is False
        assert scheduler.max_workers == 2

    def test_add_schedule(self, scheduler, mock_script):
        """Test adding a schedule."""
        schedule_id = scheduler.add_schedule(
            mock_script, "0 0 * * *", "Daily midnight run"
        )

        assert schedule_id.startswith("schedule_")
        assert schedule_id in scheduler.schedules

        schedule = scheduler.schedules[schedule_id]
        assert schedule.cron_expression == "0 0 * * *"
        assert schedule.description == "Daily midnight run"

    def test_remove_schedule(self, scheduler, mock_script):
        """Test removing a schedule."""
        schedule_id = scheduler.add_schedule(mock_script, "0 0 * * *", "Test")

        # Remove existing
        assert scheduler.remove_schedule(schedule_id) is True
        assert schedule_id not in scheduler.schedules

        # Remove non-existent
        assert scheduler.remove_schedule("non_existent") is False

    def test_pause_schedule(self, scheduler, mock_script):
        """Test pausing a schedule."""
        schedule_id = scheduler.add_schedule(mock_script, "0 0 * * *", "Test")

        # Pause existing
        assert scheduler.pause_schedule(schedule_id) is True
        schedule = scheduler.schedules[schedule_id]
        assert schedule.enabled is False
        assert schedule.next_run is None

        # Pause non-existent
        assert scheduler.pause_schedule("non_existent") is False

    def test_resume_schedule(self, scheduler, mock_script):
        """Test resuming a schedule."""
        schedule_id = scheduler.add_schedule(mock_script, "0 0 * * *", "Test")
        scheduler.pause_schedule(schedule_id)

        # Resume paused
        assert scheduler.resume_schedule(schedule_id) is True
        schedule = scheduler.schedules[schedule_id]
        assert schedule.enabled is True
        assert schedule.next_run is not None

        # Resume non-existent
        assert scheduler.resume_schedule("non_existent") is False

    @pytest.mark.asyncio
    async def test_start_stop(self, scheduler):
        """Test starting and stopping scheduler."""
        await scheduler.start()
        assert scheduler._running is True
        assert scheduler._scheduler_task is not None

        await scheduler.stop()
        assert scheduler._running is False

    def test_get_schedule_status(self, scheduler, mock_script):
        """Test getting schedule status."""
        schedule_id = scheduler.add_schedule(mock_script, "0 0 * * *", "Test")

        # Add some execution history
        schedule = scheduler.schedules[schedule_id]
        for i in range(3):
            execution = ScriptExecution(
                execution_id=f"exec_{i}",
                script_id="test",
                schedule_id=schedule_id,
                start_time=datetime.utcnow() - timedelta(minutes=10),
                end_time=datetime.utcnow() - timedelta(minutes=5),
                status=ScriptStatus.COMPLETED,
                result=None,
                error=None,
            )
            schedule.add_execution(execution)

        status = scheduler.get_schedule_status(schedule_id)

        assert status is not None
        assert status["schedule_id"] == schedule_id
        assert status["enabled"] is True
        assert status["total_executions"] == 3
        assert len(status["recent_executions"]) == 3

        # Non-existent schedule
        assert scheduler.get_schedule_status("non_existent") is None

    def test_get_all_schedules(self, scheduler, mock_script):
        """Test getting all schedules."""
        # Add multiple schedules
        ids = []
        for i in range(3):
            schedule_id = scheduler.add_schedule(
                mock_script, f"0 {i} * * *", f"Test {i}"
            )
            ids.append(schedule_id)

        all_schedules = scheduler.get_all_schedules()

        assert len(all_schedules) == 3
        assert all(s["schedule_id"] in ids for s in all_schedules)

    def test_get_running_executions(self, scheduler):
        """Test getting running executions."""
        # Add mock running executions
        for i in range(2):
            execution = ScriptExecution(
                execution_id=f"exec_{i}",
                script_id=f"script_{i}",
                schedule_id=f"schedule_{i}",
                start_time=datetime.utcnow() - timedelta(seconds=30),
                end_time=None,
                status=ScriptStatus.RUNNING,
                result=None,
                error=None,
            )
            scheduler.running_executions[f"exec_{i}"] = execution

        running = scheduler.get_running_executions()

        assert len(running) == 2
        assert all("duration" in e for e in running)
        assert all(e["duration"] > 0 for e in running)


class TestScriptMonitor:
    """Test ScriptMonitor functionality."""

    @pytest.fixture
    def monitor(self):
        """Create a script monitor."""
        return ScriptMonitor()

    def test_initialization(self, monitor):
        """Test monitor initialization."""
        assert monitor.metrics == {}
        assert monitor.alerts == []

    def test_record_execution_success(self, monitor):
        """Test recording successful execution."""
        execution = ScriptExecution(
            execution_id="exec_1",
            script_id="script_1",
            schedule_id="schedule_1",
            start_time=datetime.utcnow() - timedelta(seconds=30),
            end_time=datetime.utcnow(),
            status=ScriptStatus.COMPLETED,
            result=ScriptResult(
                status=ScriptStatus.COMPLETED.value,
                execution_time=30.0,
                rows_processed=100,
                changes_made=10,
                errors=[],
                warnings=[],
                details={},
            ),
            error=None,
        )

        monitor.record_execution("script_1", execution)

        metrics = monitor.metrics["script_1"]
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["failed_executions"] == 0
        assert metrics["total_rows_processed"] == 100
        assert metrics["total_changes_made"] == 10
        assert metrics["error_rate"] == 0.0
        assert (
            abs(metrics["avg_duration"] - 30.0) < 0.01
        )  # Allow small floating point difference

    def test_record_execution_failure(self, monitor):
        """Test recording failed execution."""
        execution = ScriptExecution(
            execution_id="exec_1",
            script_id="script_1",
            schedule_id="schedule_1",
            start_time=datetime.utcnow() - timedelta(seconds=10),
            end_time=datetime.utcnow(),
            status=ScriptStatus.FAILED,
            result=None,
            error="Test error",
        )

        monitor.record_execution("script_1", execution)

        metrics = monitor.metrics["script_1"]
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 0
        assert metrics["failed_executions"] == 1
        assert metrics["error_rate"] == 1.0

    def test_high_error_rate_alert(self, monitor):
        """Test high error rate alert generation."""
        # Record multiple executions with failures
        for i in range(10):
            execution = ScriptExecution(
                execution_id=f"exec_{i}",
                script_id="script_1",
                schedule_id="schedule_1",
                start_time=datetime.utcnow() - timedelta(seconds=10),
                end_time=datetime.utcnow(),
                status=ScriptStatus.FAILED if i < 6 else ScriptStatus.COMPLETED,
                result=None,
                error="Error" if i < 6 else None,
            )
            monitor.record_execution("script_1", execution)

        # Should have high error rate alert
        assert len(monitor.alerts) > 0
        high_error_alerts = [
            a for a in monitor.alerts if a["type"] == "high_error_rate"
        ]
        assert len(high_error_alerts) > 0
        assert high_error_alerts[0]["severity"] == "high"

    def test_long_execution_alert(self, monitor):
        """Test long execution time alert."""
        execution = ScriptExecution(
            execution_id="exec_1",
            script_id="script_1",
            schedule_id="schedule_1",
            start_time=datetime.utcnow() - timedelta(seconds=400),  # 6+ minutes
            end_time=datetime.utcnow(),
            status=ScriptStatus.COMPLETED,
            result=None,
            error=None,
        )

        monitor.record_execution("script_1", execution)

        long_exec_alerts = [a for a in monitor.alerts if a["type"] == "long_execution"]
        assert len(long_exec_alerts) == 1
        assert long_exec_alerts[0]["severity"] == "medium"

    def test_no_changes_alert(self, monitor):
        """Test no changes made alert for negative keyword scripts."""
        execution = ScriptExecution(
            execution_id="exec_1",
            script_id="negative_keyword_script_1",
            schedule_id="schedule_1",
            start_time=datetime.utcnow() - timedelta(seconds=30),
            end_time=datetime.utcnow(),
            status=ScriptStatus.COMPLETED,
            result=ScriptResult(
                status=ScriptStatus.COMPLETED.value,
                execution_time=30.0,
                rows_processed=100,
                changes_made=0,  # No changes
                errors=[],
                warnings=[],
                details={},
            ),
            error=None,
        )

        monitor.record_execution("negative_keyword_script_1", execution)

        no_changes_alerts = [a for a in monitor.alerts if a["type"] == "no_changes"]
        assert len(no_changes_alerts) == 1
        assert no_changes_alerts[0]["severity"] == "low"

    def test_get_metrics(self, monitor):
        """Test getting metrics."""
        # Record some executions
        execution = ScriptExecution(
            execution_id="exec_1",
            script_id="script_1",
            schedule_id="schedule_1",
            start_time=datetime.utcnow() - timedelta(seconds=30),
            end_time=datetime.utcnow(),
            status=ScriptStatus.COMPLETED,
            result=None,
            error=None,
        )
        monitor.record_execution("script_1", execution)

        # Get specific script metrics
        metrics = monitor.get_metrics("script_1")
        assert metrics["total_executions"] == 1

        # Get all metrics
        all_metrics = monitor.get_metrics()
        assert "script_1" in all_metrics

        # Non-existent script
        assert monitor.get_metrics("non_existent") == {}

    def test_get_alerts(self, monitor):
        """Test getting alerts."""
        # Add test alerts
        monitor.alerts = [
            {
                "type": "test1",
                "severity": "high",
                "timestamp": datetime.utcnow(),
            },
            {
                "type": "test2",
                "severity": "low",
                "timestamp": datetime.utcnow(),
            },
        ]

        # Get all alerts
        assert len(monitor.get_alerts()) == 2

        # Filter by severity
        assert len(monitor.get_alerts(severity="high")) == 1
        assert len(monitor.get_alerts(severity="low")) == 1
        assert len(monitor.get_alerts(severity="medium")) == 0

    def test_clear_alerts(self, monitor):
        """Test clearing alerts."""
        # Add test alerts
        old_alert = {
            "type": "old",
            "severity": "high",
            "timestamp": datetime.utcnow() - timedelta(hours=2),
        }
        new_alert = {
            "type": "new",
            "severity": "high",
            "timestamp": datetime.utcnow() - timedelta(minutes=30),
        }
        monitor.alerts = [old_alert, new_alert]

        # Clear old alerts
        monitor.clear_alerts(older_than=timedelta(hours=1))
        assert len(monitor.alerts) == 1
        assert monitor.alerts[0]["type"] == "new"

        # Clear all alerts
        monitor.alerts = [old_alert, new_alert]
        monitor.clear_alerts()
        assert len(monitor.alerts) == 0
