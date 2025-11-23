"""Tests for scheduler implementation."""

import asyncio
from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest
from apscheduler.triggers.cron import CronTrigger

from paidsearchnav_mcp.core.config import SchedulerConfig, Settings
from paidsearchnav_mcp.scheduler.interfaces import Job, JobStatus, JobType
from paidsearchnav_mcp.scheduler.scheduler import AuditScheduler


def clear_prometheus_registry():
    """Clear the global Prometheus registry to avoid metric conflicts."""
    from prometheus_client import REGISTRY

    REGISTRY._collector_to_names.clear()
    REGISTRY._names_to_collectors.clear()


class MockJob(Job):
    """Mock job for testing."""

    def __init__(self, job_id: str, job_type: JobType = JobType.ON_DEMAND_AUDIT):
        self._job_id = job_id
        self._job_type = job_type
        self._mock_execute = AsyncMock(return_value={"status": "success"})

    async def execute(self, context: dict) -> dict:
        """Execute the mock job."""
        return await self._mock_execute(context)

    def get_job_id(self) -> str:
        return self._job_id

    def get_job_type(self) -> JobType:
        return self._job_type


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)
    settings.scheduler = SchedulerConfig(
        enabled=True,
        retry_attempts=3,
        job_store_url=None,
    )
    return settings


@pytest.fixture
def mock_job_store():
    """Create mock job store."""
    job_store = AsyncMock()
    job_store.save_job_execution = AsyncMock(return_value="exec_123")
    job_store.update_job_status = AsyncMock(return_value=True)
    job_store.list_job_executions = AsyncMock(return_value=[])
    return job_store


@pytest.fixture
def scheduler(mock_settings, mock_job_store):
    """Create scheduler instance."""
    # Use unique namespace to avoid Prometheus metric conflicts
    import uuid

    # Clear the global registry to avoid conflicts
    clear_prometheus_registry()

    unique_namespace = f"test_scheduler_{uuid.uuid4().hex[:8]}"

    scheduler = AuditScheduler(mock_settings, mock_job_store)
    # Override metrics with unique namespace
    from paidsearchnav.scheduler.monitoring import SchedulerMetrics

    scheduler.metrics = SchedulerMetrics(unique_namespace)
    return scheduler


class TestAuditScheduler:
    """Test AuditScheduler class."""

    @pytest.mark.asyncio
    async def test_start_and_shutdown(self, scheduler):
        """Test starting and shutting down scheduler."""
        # Start scheduler
        await scheduler.start()
        assert scheduler._scheduler is not None
        assert scheduler._scheduler.running

        # Shutdown scheduler
        await scheduler.shutdown()
        assert scheduler._scheduler is None

    @pytest.mark.asyncio
    async def test_schedule_job_with_cron(self, scheduler):
        """Test scheduling a job with cron trigger."""
        await scheduler.start()

        # Create mock job
        job = MockJob("test_job")

        # Schedule job
        job_id = await scheduler.schedule_job(
            job=job,
            trigger="0 0 * * *",  # Daily at midnight
        )

        assert job_id.startswith("on_demand_audit_")

        # Verify job was scheduled
        scheduled_jobs = scheduler._scheduler.get_jobs()
        assert len(scheduled_jobs) == 1
        assert scheduled_jobs[0].id == job_id
        assert isinstance(scheduled_jobs[0].trigger, CronTrigger)

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_schedule_job_with_dict_trigger(self, scheduler):
        """Test scheduling a job with dict trigger."""
        await scheduler.start()

        # Create mock job
        job = MockJob("test_job")

        # Schedule job with dict trigger
        job_id = await scheduler.schedule_job(
            job=job,
            trigger={
                "type": "cron",
                "hour": 2,
                "minute": 30,
            },
            job_id="custom_job_id",
        )

        assert job_id == "custom_job_id"

        # Verify job was scheduled
        scheduled_jobs = scheduler._scheduler.get_jobs()
        assert len(scheduled_jobs) == 1
        assert scheduled_jobs[0].id == "custom_job_id"

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_run_job_now(self, scheduler, mock_job_store):
        """Test running a job immediately."""
        await scheduler.start()

        # Create mock job
        job = MockJob("test_job")

        # Run job
        execution_id = await scheduler.run_job_now(job, context={"test": "data"})

        assert execution_id.startswith("exec_")

        # Wait for job to complete
        await asyncio.sleep(0.1)

        # Verify job was executed
        job._mock_execute.assert_called_once()

        # Verify job execution was saved
        assert mock_job_store.save_job_execution.called
        assert mock_job_store.update_job_status.called

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_run_job_with_failure(self, scheduler, mock_job_store):
        """Test running a job that fails."""
        await scheduler.start()

        # Create mock job that fails
        job = MockJob("test_job")
        job._mock_execute.side_effect = Exception("Job failed")

        # Run job
        await scheduler.run_job_now(job)

        # Wait for job to complete
        await asyncio.sleep(0.1)

        # Verify job was executed
        job._mock_execute.assert_called()

        # Verify failure was recorded
        update_calls = mock_job_store.update_job_status.call_args_list
        assert any(
            call.kwargs.get("status") == JobStatus.FAILED for call in update_calls
        )
        assert any(
            "Job failed" in str(call.kwargs.get("error", "")) for call in update_calls
        )

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_cancel_job(self, scheduler):
        """Test cancelling a scheduled job."""
        await scheduler.start()

        # Schedule a job
        job = MockJob("test_job")
        job_id = await scheduler.schedule_job(job, trigger="0 0 * * *")

        # Verify job exists
        assert len(scheduler._scheduler.get_jobs()) == 1

        # Cancel job
        success = await scheduler.cancel_job(job_id)
        assert success is True

        # Verify job was removed
        assert len(scheduler._scheduler.get_jobs()) == 0

        # Try to cancel non-existent job
        success = await scheduler.cancel_job("non_existent")
        assert success is False

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_get_job_status_running(self, scheduler, mock_job_store):
        """Test getting status of running job."""
        # Mock the job history to return a running job
        mock_job_store.list_job_executions.return_value = [
            {
                "id": "exec_123",
                "job_id": "test_job",
                "status": JobStatus.RUNNING.value,
            }
        ]

        await scheduler.start()

        # Create and start a job
        job = MockJob("test_job")
        await scheduler.run_job_now(job)

        # Small delay to let the job register
        await asyncio.sleep(0.05)

        # Get status immediately (should be running)
        status = await scheduler.get_job_status("test_job")
        assert status in [JobStatus.PENDING, JobStatus.RUNNING]

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_get_job_status_from_history(self, scheduler, mock_job_store):
        """Test getting status from job history."""
        # Mock job history
        mock_job_store.list_job_executions.return_value = [
            {
                "id": "exec_123",
                "job_id": "test_job",
                "status": "completed",
            }
        ]

        # Get status
        status = await scheduler.get_job_status("test_job")
        assert status == JobStatus.COMPLETED

        # Verify history was queried
        mock_job_store.list_job_executions.assert_called_with(
            job_id="test_job",
            limit=1,
        )

    @pytest.mark.asyncio
    async def test_get_job_history(self, scheduler, mock_job_store):
        """Test getting job execution history."""
        # Mock history data
        mock_history = [
            {
                "id": "exec_1",
                "job_id": "job_1",
                "job_type": "quarterly_audit",
                "status": "completed",
                "started_at": datetime.utcnow() - timedelta(hours=1),
            },
            {
                "id": "exec_2",
                "job_id": "job_2",
                "job_type": "on_demand_audit",
                "status": "failed",
                "started_at": datetime.utcnow() - timedelta(hours=2),
            },
        ]
        mock_job_store.list_job_executions.return_value = mock_history

        # Get history with filters
        history = await scheduler.get_job_history(
            job_type=JobType.QUARTERLY_AUDIT,
            status=JobStatus.COMPLETED,
            limit=50,
        )

        assert history == mock_history

        # Verify filters were passed
        mock_job_store.list_job_executions.assert_called_with(
            job_id=None,
            job_type=JobType.QUARTERLY_AUDIT,
            status=JobStatus.COMPLETED,
            start_date=None,
            end_date=None,
            limit=50,
        )

    @pytest.mark.asyncio
    async def test_scheduler_without_job_store_url(self, mock_settings, mock_job_store):
        """Test scheduler without persistent job store."""
        # Create scheduler without job store URL
        mock_settings.scheduler.job_store_url = None

        # Clear registry to avoid conflicts
        clear_prometheus_registry()

        scheduler = AuditScheduler(mock_settings, mock_job_store)

        await scheduler.start()

        # Should still work with in-memory job store
        job = MockJob("test_job")
        job_id = await scheduler.schedule_job(job, trigger="0 0 * * *")

        assert job_id is not None
        assert len(scheduler._scheduler.get_jobs()) == 1

        await scheduler.shutdown()

    @pytest.mark.asyncio
    async def test_scheduler_with_job_store_url(self, mock_settings, mock_job_store):
        """Test scheduler with persistent job store."""
        from pydantic import SecretStr

        # Set job store URL as SecretStr
        mock_settings.scheduler.job_store_url = SecretStr("sqlite:///test_jobs.db")

        # Patch SQLAlchemyJobStore before creating scheduler
        with patch(
            "paidsearchnav.scheduler.scheduler.SQLAlchemyJobStore"
        ) as mock_store_class:
            # Create a proper mock that APScheduler will accept
            from apscheduler.jobstores.base import BaseJobStore

            mock_store_instance = Mock(spec=BaseJobStore)
            mock_store_class.return_value = mock_store_instance

            # Patch the AsyncIOScheduler to avoid the actual initialization
            with patch(
                "paidsearchnav.scheduler.scheduler.AsyncIOScheduler"
            ) as mock_scheduler_class:
                mock_scheduler = Mock()
                mock_scheduler_class.return_value = mock_scheduler

                # Clear registry to avoid conflicts
                clear_prometheus_registry()

                scheduler = AuditScheduler(mock_settings, mock_job_store)
                await scheduler.start()

                # Verify SQLAlchemy job store was created
                mock_store_class.assert_called_once_with(url="sqlite:///test_jobs.db")

                # Verify scheduler was configured with jobstores
                mock_scheduler_class.assert_called_once()
                call_kwargs = mock_scheduler_class.call_args[1]
                assert "jobstores" in call_kwargs
                assert "default" in call_kwargs["jobstores"]

                await scheduler.shutdown()
