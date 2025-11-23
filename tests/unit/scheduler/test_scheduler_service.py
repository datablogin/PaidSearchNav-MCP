"""Unit tests for the scheduler service."""

from __future__ import annotations

import asyncio
from datetime import datetime, timezone
from unittest.mock import ANY, AsyncMock, Mock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.scheduler.interfaces import JobStatus, JobType
from paidsearchnav_mcp.scheduler.models import JobExecution, ScheduledJob
from paidsearchnav_mcp.scheduler.service import SchedulerMetrics, SchedulerService


@pytest.fixture
def mock_audit_job():
    """Create a mock AuditJob."""
    mock_job = Mock()
    mock_job.execute = AsyncMock(return_value={"status": "completed", "results": []})
    mock_job.get_job_id = Mock(return_value="job_123")
    mock_job.get_job_type = Mock(return_value=JobType.ON_DEMAND_AUDIT)
    mock_job.config = Mock(customer_id="customer_123")
    return mock_job


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    provider = Mock()
    provider.get_customer = AsyncMock(
        return_value={
            "customer_id": "customer_123",
            "name": "Test Customer",
            "account_id": "account_123",
        }
    )
    return provider


@pytest.fixture
def mock_storage_service():
    """Create a mock storage service."""
    service = Mock()
    service.save_analysis = AsyncMock(return_value="result_123")
    service.get_analysis = AsyncMock(return_value={"id": "result_123"})
    return service


@pytest.fixture
def mock_job_store():
    """Create a mock job store."""
    store = Mock()
    store.save_job_execution = AsyncMock(return_value="exec_123")
    store.update_job_status = AsyncMock(return_value=True)
    store.get_job_execution = AsyncMock(return_value=None)
    store.list_job_executions = AsyncMock(return_value=[])
    return store


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.google_ads = Mock()
    settings.database = Mock()
    settings.reporting = Mock()
    return settings


@pytest.fixture
async def scheduler_service(
    mock_data_provider, mock_storage_service, mock_job_store, mock_settings
):
    """Create a scheduler service instance."""
    service = SchedulerService(
        data_provider=mock_data_provider,
        storage_service=mock_storage_service,
        job_store=mock_job_store,
        settings=mock_settings,
        max_concurrent_audits=5,
        retry_max_attempts=2,
        retry_delay_seconds=1,
    )
    await service.start()
    yield service

    # Ensure all tasks are real asyncio.Task objects before shutdown
    # This prevents TypeErrors during shutdown when tests may have left mocks
    for audit_id, task in list(service.running_audits.items()):
        if not isinstance(task, asyncio.Task):
            # Remove any non-Task objects that tests might have left
            service.running_audits.pop(audit_id, None)

    await service.shutdown()


@pytest.mark.asyncio
class TestSchedulerService:
    """Test cases for SchedulerService."""

    @pytest.mark.asyncio
    async def test_init(
        self, mock_data_provider, mock_storage_service, mock_job_store, mock_settings
    ):
        """Test service initialization."""
        service = SchedulerService(
            data_provider=mock_data_provider,
            storage_service=mock_storage_service,
            job_store=mock_job_store,
            settings=mock_settings,
            max_concurrent_audits=10,
        )

        assert service.data_provider == mock_data_provider
        assert service.storage == mock_storage_service
        assert service.job_store == mock_job_store
        assert service.max_concurrent == 10
        assert service.retry_max_attempts == 3
        assert service.retry_delay_seconds == 60
        assert isinstance(service.metrics, SchedulerMetrics)
        assert len(service.running_audits) == 0

    async def test_start_shutdown(self, scheduler_service):
        """Test service start and shutdown."""
        # Service is already started by fixture
        assert scheduler_service.scheduler.running is True

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_schedule_audit_valid_cron(
        self, mock_audit_job_class, scheduler_service, mock_audit_job
    ):
        """Test scheduling an audit with valid cron expression."""
        mock_audit_job_class.return_value = mock_audit_job

        scheduled_job = await scheduler_service.schedule_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
            schedule="0 0 * * *",  # Daily at midnight
            config={"date_range": {"days": 90}},
        )

        assert isinstance(scheduled_job, ScheduledJob)
        assert scheduled_job.job_type == JobType.QUARTERLY_AUDIT
        assert scheduled_job.context["customer_id"] == "customer_123"
        assert scheduled_job.context["audit_type"] == "keyword_analyzer"
        assert scheduled_job.enabled is True

        # Verify job was added to scheduler
        jobs = scheduler_service.scheduler.get_jobs()
        assert len(jobs) == 1
        assert jobs[0].id == scheduled_job.job_id

    async def test_schedule_audit_invalid_cron(self, scheduler_service):
        """Test scheduling an audit with invalid cron expression."""
        with pytest.raises(ValueError, match="Invalid cron expression"):
            await scheduler_service.schedule_audit(
                customer_id="customer_123",
                audit_type="keyword_analyzer",
                schedule="invalid cron",
                config={},
            )

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_schedule_audit_with_timezone(
        self, mock_audit_job_class, scheduler_service, mock_audit_job
    ):
        """Test scheduling an audit with timezone."""
        mock_audit_job_class.return_value = mock_audit_job

        scheduled_job = await scheduler_service.schedule_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
            schedule="0 9 * * MON",  # Every Monday at 9 AM
            config={},
            timezone_str="America/New_York",
        )

        jobs = scheduler_service.scheduler.get_jobs()
        assert len(jobs) == 1
        job = jobs[0]
        assert isinstance(job.trigger, CronTrigger)
        assert str(job.trigger.timezone) == "America/New_York"

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_run_audit(
        self, mock_audit_job_class, scheduler_service, mock_audit_job
    ):
        """Test running an audit immediately."""
        mock_audit_job_class.return_value = mock_audit_job

        execution_id = await scheduler_service.run_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
            config={"date_range": {"days": 30}},
        )

        assert execution_id.startswith("exec_")
        assert execution_id in scheduler_service.running_audits

        # Wait for execution to complete
        await asyncio.sleep(0.1)

        # Verify job store was called
        scheduler_service.job_store.save_job_execution.assert_called()
        scheduler_service.job_store.update_job_status.assert_called()

        # Ensure the task is completed and removed from running_audits
        # The actual service should clean this up, but ensure it's done
        if execution_id in scheduler_service.running_audits:
            task = scheduler_service.running_audits[execution_id]
            if not task.done():
                await task

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_run_audit_with_failure(
        self, mock_audit_job_class, scheduler_service
    ):
        """Test running an audit that fails."""
        mock_job = Mock()
        mock_job.execute = AsyncMock(side_effect=Exception("Test error"))
        mock_job.get_job_id = Mock(return_value="job_123")
        mock_job.get_job_type = Mock(return_value=JobType.ON_DEMAND_AUDIT)
        mock_job.config = Mock(customer_id="customer_123")
        mock_audit_job_class.return_value = mock_job

        execution_id = await scheduler_service.run_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
        )

        # Wait for execution and retries
        await asyncio.sleep(3)

        # Verify retries occurred
        assert mock_job.execute.call_count == 2  # Initial + 1 retry

        # Verify final status is failed
        final_status_calls = [
            call
            for call in scheduler_service.job_store.update_job_status.call_args_list
            if call[0][1] == JobStatus.FAILED
        ]
        assert len(final_status_calls) == 1

        # Ensure the task is completed and removed from running_audits
        if execution_id in scheduler_service.running_audits:
            task = scheduler_service.running_audits[execution_id]
            if not task.done():
                await task

    async def test_get_audit_status_running(self, scheduler_service):
        """Test getting status of a running audit."""

        # Create a real async task that won't complete
        async def never_complete():
            await asyncio.Event().wait()  # Wait forever

        task = asyncio.create_task(never_complete())
        scheduler_service.running_audits["exec_123"] = task

        try:
            status = await scheduler_service.get_audit_status("exec_123")
            assert status == JobStatus.RUNNING
        finally:
            # Clean up the task properly
            task.cancel()
            try:
                await task
            except asyncio.CancelledError:
                pass
            # Ensure task is removed from running_audits before fixture cleanup
            scheduler_service.running_audits.pop("exec_123", None)

    async def test_get_audit_status_completed(self, scheduler_service):
        """Test getting status of a completed audit."""
        scheduler_service.job_store.get_job_execution.return_value = {
            "id": "exec_123",
            "status": "completed",
        }

        status = await scheduler_service.get_audit_status("exec_123")
        assert status == JobStatus.COMPLETED

    async def test_get_audit_status_not_found(self, scheduler_service):
        """Test getting status of non-existent audit."""
        scheduler_service.job_store.get_job_execution.return_value = None

        with pytest.raises(ValueError, match="Audit exec_999 not found"):
            await scheduler_service.get_audit_status("exec_999")

    async def test_cancel_audit_success(self, scheduler_service):
        """Test cancelling a running audit."""

        # Create a real async task that won't complete
        async def long_running_task():
            try:
                await asyncio.Event().wait()  # Wait forever
            except asyncio.CancelledError:
                raise  # Re-raise to properly handle cancellation

        task = asyncio.create_task(long_running_task())
        scheduler_service.running_audits["exec_123"] = task

        # Ensure task is running before cancelling
        await asyncio.sleep(0.01)  # Give task time to start properly

        try:
            result = await scheduler_service.cancel_audit("exec_123")
            assert result is True

            # The cancel_audit method should have updated the job store
            scheduler_service.job_store.update_job_status.assert_called_with(
                "exec_123", JobStatus.CANCELLED, completed_at=ANY
            )
        finally:
            # Ensure complete cleanup
            if "exec_123" in scheduler_service.running_audits:
                task = scheduler_service.running_audits.pop("exec_123")
                if not task.done():
                    task.cancel()
                    try:
                        await task
                    except asyncio.CancelledError:
                        pass

    async def test_cancel_audit_not_found(self, scheduler_service):
        """Test cancelling non-existent audit."""
        result = await scheduler_service.cancel_audit("exec_999")
        assert result is False

    async def test_cancel_audit_already_done(self, scheduler_service):
        """Test cancelling completed audit."""

        # Create a task that completes immediately
        async def completed_task():
            return "done"

        task = asyncio.create_task(completed_task())
        await task  # Ensure it's done
        scheduler_service.running_audits["exec_123"] = task

        try:
            result = await scheduler_service.cancel_audit("exec_123")
            assert result is False
        finally:
            # Clean up - ensure removal from running_audits
            scheduler_service.running_audits.pop("exec_123", None)

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_list_scheduled_audits(self, mock_audit_job_class, scheduler_service):
        """Test listing scheduled audits."""

        # Create separate mocks for each audit with correct customer_id
        def create_mock_job(customer_id):
            mock_job = Mock()
            mock_job.execute = AsyncMock(
                return_value={"status": "completed", "results": []}
            )
            mock_job.get_job_id = Mock(return_value=f"job_{customer_id}")
            mock_job.get_job_type = Mock(return_value=JobType.ON_DEMAND_AUDIT)
            # Create a config object with __dict__ attribute for list_scheduled_audits
            config_obj = type("Config", (), {})()
            config_obj.customer_id = customer_id
            mock_job.config = config_obj
            return mock_job

        # Return different mock for each call
        mock_audit_job_class.side_effect = [
            create_mock_job("customer_123"),
            create_mock_job("customer_456"),
        ]

        # Schedule some audits
        await scheduler_service.schedule_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
            schedule="0 0 * * *",
            config={},
        )
        await scheduler_service.schedule_audit(
            customer_id="customer_456",
            audit_type="search_term_analyzer",
            schedule="0 0 * * MON",
            config={},
        )

        # List all audits
        all_audits = await scheduler_service.list_scheduled_audits()
        assert len(all_audits) == 2

        # List audits for specific customer
        customer_audits = await scheduler_service.list_scheduled_audits("customer_123")
        assert len(customer_audits) == 1
        assert customer_audits[0].context["customer_id"] == "customer_123"

    @patch("paidsearchnav.scheduler.service.AuditJob")
    async def test_pause_resume_remove_scheduled_audit(
        self, mock_audit_job_class, scheduler_service, mock_audit_job
    ):
        """Test pause, resume, and remove operations."""
        mock_audit_job_class.return_value = mock_audit_job

        scheduled_job = await scheduler_service.schedule_audit(
            customer_id="customer_123",
            audit_type="keyword_analyzer",
            schedule="0 0 * * *",
            config={},
        )
        job_id = scheduled_job.job_id

        # Test pause
        result = await scheduler_service.pause_scheduled_audit(job_id)
        assert result is True

        # Test resume
        result = await scheduler_service.resume_scheduled_audit(job_id)
        assert result is True

        # Test remove
        result = await scheduler_service.remove_scheduled_audit(job_id)
        assert result is True

        # Verify job is removed
        jobs = scheduler_service.scheduler.get_jobs()
        assert len(jobs) == 0

    async def test_get_audit_history(self, scheduler_service):
        """Test getting audit history."""
        mock_executions = [
            {
                "id": "exec_1",
                "job_id": "job_1",
                "job_type": "quarterly_audit",
                "status": "completed",
                "started_at": datetime.now(timezone.utc),
                "completed_at": datetime.now(timezone.utc),
                "context": {"customer_id": "customer_123"},
            },
            {
                "id": "exec_2",
                "job_id": "job_2",
                "job_type": "quarterly_audit",
                "status": "failed",
                "started_at": datetime.now(timezone.utc),
                "error": "Test error",
                "context": {"customer_id": "customer_456"},
            },
        ]
        scheduler_service.job_store.list_job_executions.return_value = mock_executions

        # Get all history
        history = await scheduler_service.get_audit_history()
        assert len(history) == 2
        assert all(isinstance(h, JobExecution) for h in history)

        # Get history for specific customer
        customer_history = await scheduler_service.get_audit_history(
            customer_id="customer_123"
        )
        assert len(customer_history) == 1
        assert customer_history[0].context["customer_id"] == "customer_123"


class TestSchedulerMetrics:
    """Test cases for SchedulerMetrics."""

    def test_init(self):
        """Test metrics initialization."""
        metrics = SchedulerMetrics()
        assert metrics.total_audits_started == 0
        assert metrics.total_audits_completed == 0
        assert metrics.total_audits_failed == 0
        assert metrics.total_audits_cancelled == 0
        assert metrics.total_retries == 0
        assert metrics.average_execution_time == 0.0

    def test_record_audit_start(self):
        """Test recording audit start."""
        metrics = SchedulerMetrics()
        metrics.record_audit_start("customer_123")

        assert metrics.total_audits_started == 1
        assert metrics.audits_by_customer["customer_123"] == 1

    def test_record_audit_completion(self):
        """Test recording audit completion."""
        metrics = SchedulerMetrics()
        metrics.record_audit_completion(120.5, JobStatus.COMPLETED)

        assert metrics.total_audits_completed == 1
        assert metrics.execution_times == [120.5]
        assert metrics.average_execution_time == 120.5
        assert metrics.audits_by_status["completed"] == 1

    def test_record_audit_failure(self):
        """Test recording audit failure."""
        metrics = SchedulerMetrics()
        metrics.record_audit_completion(60.0, JobStatus.FAILED)

        assert metrics.total_audits_failed == 1
        assert metrics.audits_by_status["failed"] == 1

    def test_record_retry(self):
        """Test recording retry."""
        metrics = SchedulerMetrics()
        metrics.record_retry()
        metrics.record_retry()

        assert metrics.total_retries == 2

    def test_record_error(self):
        """Test recording error."""
        metrics = SchedulerMetrics()
        metrics.record_error("ValueError")
        metrics.record_error("ValueError")
        metrics.record_error("KeyError")

        assert metrics.errors_by_type["ValueError"] == 2
        assert metrics.errors_by_type["KeyError"] == 1

    def test_get_summary(self):
        """Test getting metrics summary."""
        metrics = SchedulerMetrics()
        metrics.record_audit_start("customer_123")
        metrics.record_audit_completion(100.0, JobStatus.COMPLETED)
        metrics.record_retry()
        metrics.record_error("TestError")

        summary = metrics.get_summary()

        assert summary["total_audits_started"] == 1
        assert summary["total_audits_completed"] == 1
        assert summary["total_retries"] == 1
        assert summary["success_rate"] == 100.0
        assert summary["average_execution_time_seconds"] == 100.0
        assert "customer_123" in summary["top_customers"]
        assert "TestError" in summary["top_errors"]

    def test_metrics_with_scheduler_service(self, scheduler_service):
        """Test metrics integration with scheduler service."""
        initial_metrics = scheduler_service.get_metrics()
        assert initial_metrics["total_audits_started"] == 0
        assert initial_metrics["current_running_audits"] == 0
        assert initial_metrics["scheduler_running"] is True

        # Reset metrics
        scheduler_service.reset_metrics()
        reset_metrics = scheduler_service.get_metrics()
        assert reset_metrics["total_audits_started"] == 0
