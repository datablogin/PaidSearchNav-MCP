"""Tests for scheduler API implementation."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav.core.config import SchedulerConfig, Settings
from paidsearchnav.scheduler.api import (
    JobHistoryResponse,
    JobStatusResponse,
    ScheduleAuditRequest,
    SchedulerAPI,
    TriggerAuditRequest,
)
from paidsearchnav.scheduler.interfaces import JobStatus, JobType


def create_trigger_audit_request(**overrides):
    """Factory for creating TriggerAuditRequest objects with test defaults."""
    defaults = {
        "customer_id": "123456789",
        "analyzers": None,
        "start_date": None,
        "end_date": None,
        "generate_report": True,
        "report_formats": ["html"],
    }
    defaults.update(overrides)
    return TriggerAuditRequest(**defaults)


def create_schedule_audit_request(**overrides):
    """Factory for creating ScheduleAuditRequest objects with test defaults."""
    defaults = {
        "customer_id": "123456789",
        "schedule": "0 0 1 */3 *",
        "analyzers": None,
        "enabled": True,
    }
    defaults.update(overrides)
    return ScheduleAuditRequest(**defaults)


def create_job_execution(**overrides):
    """Factory for creating job execution dictionaries with test defaults."""
    defaults = {
        "id": "exec_123",
        "job_id": "job_123",
        "job_type": "on_demand_audit",
        "status": "completed",
        "started_at": datetime.utcnow() - timedelta(hours=1),
        "completed_at": datetime.utcnow(),
        "result": {"analysis_ids": ["analysis_123"]},
        "error": None,
        "context": {"customer_id": "123456789"},
        "retry_count": 0,
    }
    defaults.update(overrides)
    return defaults


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
def mock_scheduler():
    """Create mock scheduler."""
    scheduler = AsyncMock()
    scheduler.run_job_now = AsyncMock(return_value="exec_123")
    scheduler.schedule_job = AsyncMock(return_value="job_123")
    scheduler.cancel_job = AsyncMock(return_value=True)
    scheduler.get_job_status = AsyncMock(return_value=JobStatus.COMPLETED)
    scheduler.get_job_history = AsyncMock(return_value=[])
    return scheduler


@pytest.fixture
def api_with_scheduler(mock_scheduler):
    """Create API instance with mock scheduler."""
    return SchedulerAPI(scheduler=mock_scheduler)


@pytest.fixture
def api_without_scheduler():
    """Create API instance without scheduler."""
    return SchedulerAPI()


class TestSchedulerAPIInit:
    """Test SchedulerAPI initialization."""

    def test_init_with_scheduler(self, mock_scheduler):
        """Test initialization with scheduler."""
        api = SchedulerAPI(scheduler=mock_scheduler)
        assert api.scheduler is mock_scheduler

    def test_init_without_scheduler(self):
        """Test initialization without scheduler."""
        api = SchedulerAPI()
        assert api.scheduler is None

    def test_settings_property_caching(self, api_without_scheduler):
        """Test settings property caching."""
        with patch("paidsearchnav.scheduler.api.get_settings") as mock_get_settings:
            mock_settings = Mock()
            mock_get_settings.return_value = mock_settings

            # First access
            settings1 = api_without_scheduler.settings
            assert settings1 is mock_settings
            mock_get_settings.assert_called_once()

            # Second access should use cache
            settings2 = api_without_scheduler.settings
            assert settings2 is mock_settings
            assert settings1 is settings2
            mock_get_settings.assert_called_once()  # Still only called once


class TestSchedulerAPIEnsureScheduler:
    """Test scheduler initialization on demand."""

    @patch("paidsearchnav.scheduler.api.AuditScheduler")
    @patch("paidsearchnav.scheduler.api.JobHistoryStore")
    @patch("paidsearchnav.scheduler.api.AnalysisRepository")
    def test_ensure_scheduler_creates_new(
        self,
        mock_repo_class,
        mock_store_class,
        mock_scheduler_class,
        api_without_scheduler,
        mock_settings,
    ):
        """Test _ensure_scheduler creates new scheduler."""
        # Setup mocks
        mock_repo = Mock()
        mock_repo.AsyncSessionLocal = Mock()
        mock_repo_class.return_value = mock_repo

        mock_store = Mock()
        mock_store_class.return_value = mock_store

        mock_scheduler = Mock()
        mock_scheduler_class.return_value = mock_scheduler

        # Mock settings
        api_without_scheduler._settings = mock_settings
        result = api_without_scheduler._ensure_scheduler()

        # Verify components were created
        mock_repo_class.assert_called_once_with(mock_settings)
        mock_store_class.assert_called_once_with(mock_repo.AsyncSessionLocal)
        mock_scheduler_class.assert_called_once_with(mock_settings, mock_store)

        # Verify scheduler was cached
        assert api_without_scheduler.scheduler is mock_scheduler
        assert result is mock_scheduler

    def test_ensure_scheduler_returns_existing(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test _ensure_scheduler returns existing scheduler."""
        result = api_with_scheduler._ensure_scheduler()
        assert result is mock_scheduler


class TestTriggerAudit:
    """Test trigger_audit functionality."""

    @pytest.mark.asyncio
    async def test_trigger_audit_basic(self, api_with_scheduler, mock_scheduler):
        """Test basic audit triggering."""
        request = create_trigger_audit_request()

        with patch("paidsearchnav.scheduler.api.AuditJob") as mock_job_class:
            mock_job = Mock()
            mock_job.get_job_id.return_value = "audit_job_123"
            mock_job_class.return_value = mock_job

            result = await api_with_scheduler.trigger_audit(request)

        # Verify job was created with correct parameters
        mock_job_class.assert_called_once()
        job_config = mock_job_class.call_args[0][0]
        settings = mock_job_class.call_args[0][1]
        assert job_config.customer_id == "123456789"
        assert job_config.analyzers is None
        assert job_config.generate_report is True
        assert job_config.report_formats == ["html"]
        assert settings is api_with_scheduler.settings

        # Verify scheduler was called with the created job
        mock_scheduler.run_job_now.assert_called_once_with(mock_job)

        # Verify response
        assert result == {
            "execution_id": "exec_123",
            "job_id": "audit_job_123",
            "customer_id": "123456789",
            "status": "started",
        }

    @pytest.mark.asyncio
    async def test_trigger_audit_with_options(self, api_with_scheduler, mock_scheduler):
        """Test audit triggering with all options."""
        start_date = datetime.utcnow() - timedelta(days=30)
        end_date = datetime.utcnow()

        request = create_trigger_audit_request(
            analyzers=["keyword_match", "search_terms"],
            start_date=start_date,
            end_date=end_date,
            generate_report=False,
            report_formats=["pdf", "json"],
        )

        with patch("paidsearchnav.scheduler.api.AuditJob") as mock_job_class:
            mock_job = Mock()
            mock_job.get_job_id.return_value = "audit_job_123"
            mock_job_class.return_value = mock_job

            result = await api_with_scheduler.trigger_audit(request)

        # Verify job configuration
        job_config = mock_job_class.call_args[0][0]
        assert job_config.customer_id == "123456789"
        assert job_config.analyzers == ["keyword_match", "search_terms"]
        assert job_config.start_date == start_date
        assert job_config.end_date == end_date
        assert job_config.generate_report is False
        assert job_config.report_formats == ["pdf", "json"]

        assert result["customer_id"] == "123456789"

    @pytest.mark.asyncio
    async def test_trigger_audit_scheduler_error(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test audit triggering with scheduler error."""
        mock_scheduler.run_job_now.side_effect = Exception("Scheduler error")

        request = TriggerAuditRequest(customer_id="123456789")

        with patch("paidsearchnav.scheduler.api.AuditJob"):
            with pytest.raises(Exception, match="Scheduler error"):
                await api_with_scheduler.trigger_audit(request)


class TestScheduleAudit:
    """Test schedule_audit functionality."""

    @pytest.mark.asyncio
    async def test_schedule_audit_enabled(self, api_with_scheduler, mock_scheduler):
        """Test scheduling enabled audit."""
        request = ScheduleAuditRequest(
            customer_id="123456789",
            schedule="0 0 1 */3 *",  # Quarterly
            analyzers=["keyword_match"],
            enabled=True,
        )

        with patch("paidsearchnav.scheduler.api.AuditJob") as mock_job_class:
            mock_job = Mock()
            mock_job_class.return_value = mock_job

            result = await api_with_scheduler.schedule_audit(request)

        # Verify old schedule was cancelled
        mock_scheduler.cancel_job.assert_called_once_with("scheduled_audit_123456789")

        # Verify new schedule was created
        mock_scheduler.schedule_job.assert_called_once_with(
            job=mock_job,
            trigger="0 0 1 */3 *",
            job_id="scheduled_audit_123456789",
            replace_existing=True,
        )

        # Verify response
        assert result == {
            "job_id": "job_123",
            "customer_id": "123456789",
            "schedule": "0 0 1 */3 *",
            "enabled": True,
            "status": "scheduled",
        }

    @pytest.mark.asyncio
    async def test_schedule_audit_disabled(self, api_with_scheduler, mock_scheduler):
        """Test scheduling disabled audit."""
        request = ScheduleAuditRequest(
            customer_id="123456789",
            schedule="0 0 1 */3 *",
            enabled=False,
        )

        with patch("paidsearchnav.scheduler.api.AuditJob"):
            result = await api_with_scheduler.schedule_audit(request)

        # Verify old schedule was cancelled
        mock_scheduler.cancel_job.assert_called_once_with("scheduled_audit_123456789")

        # Verify no new schedule was created
        mock_scheduler.schedule_job.assert_not_called()

        # Verify response
        assert result == {
            "job_id": "scheduled_audit_123456789",
            "customer_id": "123456789",
            "schedule": "0 0 1 */3 *",
            "enabled": False,
            "status": "disabled",
        }

    @pytest.mark.asyncio
    async def test_schedule_audit_job_config(self, api_with_scheduler, mock_scheduler):
        """Test schedule audit job configuration."""
        request = ScheduleAuditRequest(
            customer_id="123456789",
            schedule="0 0 * * *",
            analyzers=["search_terms", "negative_conflicts"],
            enabled=True,
        )

        with patch("paidsearchnav.scheduler.api.AuditJob") as mock_job_class:
            await api_with_scheduler.schedule_audit(request)

        # Verify job configuration
        job_config = mock_job_class.call_args[0][0]
        assert job_config.customer_id == "123456789"
        assert job_config.analyzers == ["search_terms", "negative_conflicts"]
        assert job_config.generate_report is True
        assert job_config.report_formats == ["html"]


class TestGetJobStatus:
    """Test get_job_status functionality."""

    @pytest.mark.asyncio
    async def test_get_job_status_from_history(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test getting job status from history."""
        # Mock execution history
        mock_execution = {
            "status": "completed",
            "started_at": datetime.utcnow() - timedelta(hours=1),
            "completed_at": datetime.utcnow(),
            "result": {"analysis_ids": ["analysis_123"]},
            "error": None,
        }
        mock_scheduler.get_job_history.return_value = [mock_execution]

        result = await api_with_scheduler.get_job_status("job_123")

        # Verify history was queried
        mock_scheduler.get_job_history.assert_called_once_with(
            job_id="job_123", limit=1
        )

        # Verify response
        assert isinstance(result, JobStatusResponse)
        assert result.job_id == "job_123"
        assert result.status == "completed"
        assert result.started_at == mock_execution["started_at"]
        assert result.completed_at == mock_execution["completed_at"]
        assert result.result == mock_execution["result"]
        assert result.error is None

    @pytest.mark.asyncio
    async def test_get_job_status_from_scheduler(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test getting job status from scheduler when no history."""
        # No history found
        mock_scheduler.get_job_history.return_value = []
        mock_scheduler.get_job_status.return_value = JobStatus.RUNNING

        result = await api_with_scheduler.get_job_status("job_123")

        # Verify scheduler status was checked
        mock_scheduler.get_job_status.assert_called_once_with("job_123")

        # Verify response
        assert result.job_id == "job_123"
        assert result.status == "running"
        assert result.started_at is None
        assert result.completed_at is None
        assert result.result is None
        assert result.error is None

    @pytest.mark.asyncio
    async def test_get_job_status_not_found(self, api_with_scheduler, mock_scheduler):
        """Test getting status for non-existent job."""
        # No history and no scheduled job
        mock_scheduler.get_job_history.return_value = []
        mock_scheduler.get_job_status.return_value = None

        with pytest.raises(ValueError, match="Job job_123 not found"):
            await api_with_scheduler.get_job_status("job_123")


class TestGetJobHistory:
    """Test get_job_history functionality."""

    @pytest.mark.asyncio
    async def test_get_job_history_no_filters(self, api_with_scheduler, mock_scheduler):
        """Test getting job history without filters."""
        # Mock executions
        mock_executions = [
            {
                "id": "exec_1",
                "job_id": "job_1",
                "job_type": "on_demand_audit",
                "status": "completed",
                "started_at": datetime.utcnow(),
                "context": {"customer_id": "123456789"},
            },
            {
                "id": "exec_2",
                "job_id": "job_2",
                "job_type": "quarterly_audit",
                "status": "failed",
                "started_at": datetime.utcnow() - timedelta(hours=1),
                "context": {"customer_id": "987654321"},
            },
        ]
        mock_scheduler.get_job_history.return_value = mock_executions

        result = await api_with_scheduler.get_job_history()

        # Verify scheduler was called
        mock_scheduler.get_job_history.assert_called_once_with(
            job_type=None,
            status=None,
            limit=51,  # page_size + 1
        )

        # Verify response
        assert isinstance(result, JobHistoryResponse)
        assert result.executions == mock_executions
        assert result.total == 2
        assert result.page == 1
        assert result.page_size == 50

    @pytest.mark.asyncio
    async def test_get_job_history_with_filters(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test getting job history with filters."""
        mock_executions = [
            {
                "id": "exec_1",
                "job_id": "job_1",
                "status": "completed",
                "context": {"customer_id": "123456789"},
            }
        ]
        mock_scheduler.get_job_history.return_value = mock_executions

        result = await api_with_scheduler.get_job_history(
            customer_id="123456789",
            job_type="on_demand_audit",
            status="completed",
            page=1,
            page_size=10,
        )

        # Verify scheduler was called with enum conversions
        mock_scheduler.get_job_history.assert_called_once_with(
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.COMPLETED,
            limit=11,  # page_size + 1
        )

        # Verify filtering by customer_id
        assert result.executions == mock_executions
        assert result.page == 1
        assert result.page_size == 10

    @pytest.mark.asyncio
    async def test_get_job_history_customer_filtering(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test customer ID filtering in job history."""
        mock_executions = [
            {
                "id": "exec_1",
                "context": {"customer_id": "123456789"},
            },
            {
                "id": "exec_2",
                "context": {"customer_id": "987654321"},
            },
            {
                "id": "exec_3",
                "context": {},  # No customer_id
            },
        ]
        mock_scheduler.get_job_history.return_value = mock_executions

        result = await api_with_scheduler.get_job_history(customer_id="123456789")

        # Should only return executions for specified customer
        assert len(result.executions) == 1
        assert result.executions[0]["id"] == "exec_1"

    @pytest.mark.asyncio
    async def test_get_job_history_pagination(self, api_with_scheduler, mock_scheduler):
        """Test pagination in job history."""
        # More executions than page size
        mock_executions = [{"id": f"exec_{i}"} for i in range(21)]  # 21 executions
        mock_scheduler.get_job_history.return_value = mock_executions

        result = await api_with_scheduler.get_job_history(page_size=20)

        # Should indicate more pages available
        assert result.total == 21  # len(executions) + 1 (has_more)
        assert len(result.executions) == 20

    @pytest.mark.asyncio
    async def test_get_job_history_pagination_bug_fix(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test that pagination is applied correctly without double pagination."""
        # Create 25 executions
        mock_executions = [{"id": f"exec_{i}", "context": {}} for i in range(25)]
        mock_scheduler.get_job_history.return_value = mock_executions

        # Test first page with page_size=10
        result = await api_with_scheduler.get_job_history(page=1, page_size=10)

        # Should get first 10 items
        assert len(result.executions) == 10
        assert result.total == 25
        assert result.page == 1
        assert result.page_size == 10
        assert [e["id"] for e in result.executions] == [f"exec_{i}" for i in range(10)]

        # Test second page
        result = await api_with_scheduler.get_job_history(page=2, page_size=10)

        # Should get next 10 items (exec_10 to exec_19)
        assert len(result.executions) == 10
        assert result.total == 25
        assert result.page == 2
        assert [e["id"] for e in result.executions] == [
            f"exec_{i}" for i in range(10, 20)
        ]

        # Test third page (partial)
        result = await api_with_scheduler.get_job_history(page=3, page_size=10)

        # Should get remaining 5 items (exec_20 to exec_24)
        assert len(result.executions) == 5
        assert result.total == 25
        assert result.page == 3
        assert [e["id"] for e in result.executions] == [
            f"exec_{i}" for i in range(20, 25)
        ]

    @pytest.mark.asyncio
    async def test_get_job_history_pagination_with_customer_filter(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test pagination works correctly with customer ID filtering."""
        # Create executions with different customer IDs
        mock_executions = []
        for i in range(20):
            customer_id = "123456789" if i % 2 == 0 else "987654321"
            mock_executions.append(
                {"id": f"exec_{i}", "context": {"customer_id": customer_id}}
            )

        mock_scheduler.get_job_history.return_value = mock_executions

        # Filter by customer_id="123456789" (should have 10 matching executions)
        result = await api_with_scheduler.get_job_history(
            customer_id="123456789", page=1, page_size=5
        )

        # Should get first 5 filtered items
        assert len(result.executions) == 5
        assert result.total == 10  # Total matching executions after filtering
        assert result.page == 1
        assert result.page_size == 5

        # All returned executions should match the customer filter
        for execution in result.executions:
            assert execution["context"]["customer_id"] == "123456789"


class TestCancelJob:
    """Test cancel_job functionality."""

    @pytest.mark.asyncio
    async def test_cancel_job_success(self, api_with_scheduler, mock_scheduler):
        """Test successful job cancellation."""
        mock_scheduler.cancel_job.return_value = True

        result = await api_with_scheduler.cancel_job("job_123")

        mock_scheduler.cancel_job.assert_called_once_with("job_123")

        assert result == {
            "job_id": "job_123",
            "status": "cancelled",
            "success": True,
        }

    @pytest.mark.asyncio
    async def test_cancel_job_not_found(self, api_with_scheduler, mock_scheduler):
        """Test cancelling non-existent job."""
        mock_scheduler.cancel_job.return_value = False

        result = await api_with_scheduler.cancel_job("job_123")

        assert result == {
            "job_id": "job_123",
            "status": "not_found",
            "success": False,
        }


class TestTriggerSingleAnalyzer:
    """Test trigger_single_analyzer functionality."""

    @pytest.mark.asyncio
    async def test_trigger_single_analyzer_basic(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test basic single analyzer triggering."""
        with patch("paidsearchnav.scheduler.api.SingleAnalyzerJob") as mock_job_class:
            mock_job = Mock()
            mock_job.get_job_id.return_value = "analyzer_job_123"
            mock_job_class.return_value = mock_job

            result = await api_with_scheduler.trigger_single_analyzer(
                customer_id="123456789",
                analyzer_name="keyword_match",
            )

        # Verify job was created
        mock_job_class.assert_called_once_with(
            customer_id="123456789",
            analyzer_name="keyword_match",
            settings=api_with_scheduler.settings,
            start_date=None,
            end_date=None,
        )

        # Verify scheduler was called
        mock_scheduler.run_job_now.assert_called_once_with(mock_job)

        # Verify response
        assert result == {
            "execution_id": "exec_123",
            "job_id": "analyzer_job_123",
            "customer_id": "123456789",
            "analyzer": "keyword_match",
            "status": "started",
        }

    @pytest.mark.asyncio
    async def test_trigger_single_analyzer_with_dates(
        self, api_with_scheduler, mock_scheduler
    ):
        """Test single analyzer with date range."""
        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        with patch("paidsearchnav.scheduler.api.SingleAnalyzerJob") as mock_job_class:
            mock_job = Mock()
            mock_job.get_job_id.return_value = "analyzer_job_123"
            mock_job_class.return_value = mock_job

            await api_with_scheduler.trigger_single_analyzer(
                customer_id="123456789",
                analyzer_name="search_terms",
                start_date=start_date,
                end_date=end_date,
            )

        # Verify dates were passed
        mock_job_class.assert_called_once_with(
            customer_id="123456789",
            analyzer_name="search_terms",
            settings=api_with_scheduler.settings,
            start_date=start_date,
            end_date=end_date,
        )


class TestPydanticModels:
    """Test Pydantic model validation."""

    def test_trigger_audit_request_validation(self):
        """Test TriggerAuditRequest validation."""
        # Valid request
        request = TriggerAuditRequest(customer_id="123456789")
        assert request.customer_id == "123456789"
        assert request.analyzers is None
        assert request.generate_report is True
        assert request.report_formats == ["html"]

        # Request with all fields
        request = TriggerAuditRequest(
            customer_id="123456789",
            analyzers=["keyword_match"],
            start_date=datetime.utcnow(),
            end_date=datetime.utcnow(),
            generate_report=False,
            report_formats=["pdf", "json"],
        )
        assert request.analyzers == ["keyword_match"]
        assert request.generate_report is False
        assert request.report_formats == ["pdf", "json"]

    def test_schedule_audit_request_validation(self):
        """Test ScheduleAuditRequest validation."""
        # Valid request
        request = ScheduleAuditRequest(
            customer_id="123456789",
            schedule="0 0 * * *",
        )
        assert request.customer_id == "123456789"
        assert request.schedule == "0 0 * * *"
        assert request.enabled is True

        # Request with all fields
        request = ScheduleAuditRequest(
            customer_id="123456789",
            schedule="0 0 1 */3 *",
            analyzers=["keyword_match", "search_terms"],
            enabled=False,
        )
        assert request.analyzers == ["keyword_match", "search_terms"]
        assert request.enabled is False

    def test_job_status_response_model(self):
        """Test JobStatusResponse model."""
        response = JobStatusResponse(
            job_id="job_123",
            status="completed",
            started_at=datetime.utcnow(),
            completed_at=datetime.utcnow(),
            result={"analysis_ids": ["analysis_123"]},
            error=None,
        )
        assert response.job_id == "job_123"
        assert response.status == "completed"
        assert response.result == {"analysis_ids": ["analysis_123"]}

    def test_job_history_response_model(self):
        """Test JobHistoryResponse model."""
        executions = [
            {"id": "exec_1", "status": "completed"},
            {"id": "exec_2", "status": "failed"},
        ]
        response = JobHistoryResponse(
            executions=executions,
            total=2,
            page=1,
            page_size=50,
        )
        assert response.executions == executions
        assert response.total == 2
        assert response.page == 1
        assert response.page_size == 50
