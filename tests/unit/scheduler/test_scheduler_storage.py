"""Tests for scheduler storage implementation."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, Mock
from uuid import uuid4

import pytest
from sqlalchemy.exc import SQLAlchemyError

from paidsearchnav_mcp.scheduler.interfaces import JobStatus, JobType
from paidsearchnav_mcp.scheduler.storage import JobHistoryStore
from paidsearchnav_mcp.storage.models import JobExecutionRecord


@pytest.fixture
def mock_session():
    """Create mock database session."""
    session = AsyncMock()
    session.add = Mock()
    session.commit = AsyncMock()
    session.rollback = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_session_factory(mock_session):
    """Create mock session factory."""

    class MockSessionFactory:
        def __call__(self):
            # Return an async context manager
            class AsyncContextManager:
                async def __aenter__(self):
                    return mock_session

                async def __aexit__(self, exc_type, exc_val, exc_tb):
                    pass

            return AsyncContextManager()

    return MockSessionFactory()


@pytest.fixture
def job_store(mock_session_factory):
    """Create JobHistoryStore instance."""
    return JobHistoryStore(mock_session_factory)


@pytest.fixture
def sample_execution_data():
    """Sample job execution data."""
    return {
        "job_id": "job_123",
        "job_type": JobType.ON_DEMAND_AUDIT,
        "status": JobStatus.COMPLETED,
        "started_at": datetime.utcnow() - timedelta(hours=1),
        "completed_at": datetime.utcnow(),
        "result": {"analysis_ids": ["analysis_123"]},
        "error": None,
        "context": {"customer_id": "123456789"},
    }


class TestJobHistoryStoreInit:
    """Test JobHistoryStore initialization."""

    def test_init(self, mock_session_factory):
        """Test store initialization."""
        store = JobHistoryStore(mock_session_factory)
        assert store.session_factory is mock_session_factory


class TestSaveJobExecution:
    """Test save_job_execution functionality."""

    @pytest.mark.asyncio
    async def test_save_job_execution_success(
        self, job_store, mock_session, sample_execution_data
    ):
        """Test successful job execution save."""
        # Mock execution record
        mock_execution = Mock()
        mock_execution.id = uuid4()

        # Mock session refresh to set the ID
        async def mock_refresh(execution):
            execution.id = mock_execution.id

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # Call save_job_execution
        execution_id = await job_store.save_job_execution(**sample_execution_data)

        # Verify session operations were called in correct order
        mock_session.add.assert_called_once()
        mock_session.commit.assert_called_once()
        mock_session.refresh.assert_called_once()
        mock_session.rollback.assert_not_called()

        # Verify execution record was created correctly
        added_execution = mock_session.add.call_args[0][0]
        assert isinstance(added_execution, JobExecutionRecord)
        assert mock_session.refresh.call_args[0][0] is added_execution
        assert added_execution.job_id == "job_123"
        assert added_execution.job_type == JobType.ON_DEMAND_AUDIT.value
        assert added_execution.status == JobStatus.COMPLETED.value
        assert added_execution.started_at == sample_execution_data["started_at"]
        assert added_execution.completed_at == sample_execution_data["completed_at"]
        assert added_execution.result == sample_execution_data["result"]
        assert added_execution.error is None
        assert added_execution.context == sample_execution_data["context"]

        # Verify return value
        assert execution_id == str(mock_execution.id)

    @pytest.mark.asyncio
    async def test_save_job_execution_with_defaults(self, job_store, mock_session):
        """Test save with default values."""
        # Mock execution record
        mock_execution = Mock()
        mock_execution.id = uuid4()

        async def mock_refresh(execution):
            execution.id = mock_execution.id

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # Call with minimal data
        execution_id = await job_store.save_job_execution(
            job_id="job_123",
            job_type=JobType.QUARTERLY_AUDIT,
            status=JobStatus.PENDING,
            started_at=datetime.utcnow(),
        )

        # Verify defaults were used
        added_execution = mock_session.add.call_args[0][0]
        assert added_execution.completed_at is None
        assert added_execution.result is None
        assert added_execution.error is None
        assert added_execution.context == {}  # Default empty dict

        assert execution_id == str(mock_execution.id)

    @pytest.mark.asyncio
    async def test_save_job_execution_database_error(
        self, job_store, mock_session, sample_execution_data
    ):
        """Test save with database error."""
        # Mock commit to raise exception
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        # Call should raise exception
        with pytest.raises(SQLAlchemyError):
            await job_store.save_job_execution(**sample_execution_data)

        # Verify rollback was called
        mock_session.rollback.assert_called_once()

    @pytest.mark.asyncio
    async def test_save_job_execution_with_none_context(self, job_store, mock_session):
        """Test save with None context."""
        mock_execution = Mock()
        mock_execution.id = uuid4()

        async def mock_refresh(execution):
            execution.id = mock_execution.id

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        await job_store.save_job_execution(
            job_id="job_123",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.PENDING,
            started_at=datetime.utcnow(),
            context=None,
        )

        # Verify empty dict was used
        added_execution = mock_session.add.call_args[0][0]
        assert added_execution.context == {}


class TestUpdateJobStatus:
    """Test update_job_status functionality."""

    @pytest.mark.asyncio
    async def test_update_job_status_success(self, job_store, mock_session):
        """Test successful job status update."""
        # Mock existing execution
        mock_execution = Mock()
        mock_execution.status = JobStatus.RUNNING.value
        mock_execution.completed_at = None
        mock_execution.result = None
        mock_execution.error = None

        # Mock query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        mock_session.execute.return_value = mock_result

        # Update status
        completed_at = datetime.utcnow()
        result = {"analysis_ids": ["analysis_123"]}

        success = await job_store.update_job_status(
            execution_id="exec_123",
            status=JobStatus.COMPLETED,
            completed_at=completed_at,
            result=result,
            error=None,
        )

        # Verify query was executed
        mock_session.execute.assert_called_once()

        # Verify execution was updated
        assert mock_execution.status == JobStatus.COMPLETED.value
        assert mock_execution.completed_at == completed_at
        assert mock_execution.result == result
        assert mock_execution.error is None

        # Verify commit was called
        mock_session.commit.assert_called_once()
        mock_session.rollback.assert_not_called()

        assert success is True

    @pytest.mark.asyncio
    async def test_update_job_status_not_found(self, job_store, mock_session):
        """Test update when execution not found."""
        # Mock query to return None
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        success = await job_store.update_job_status(
            execution_id="exec_123",
            status=JobStatus.FAILED,
        )

        # Verify no commit was called
        mock_session.commit.assert_not_called()
        assert success is False

    @pytest.mark.asyncio
    async def test_update_job_status_partial_update(self, job_store, mock_session):
        """Test partial status update."""
        # Mock existing execution
        mock_execution = Mock()
        mock_execution.status = JobStatus.RUNNING.value
        mock_execution.completed_at = None
        mock_execution.result = {"partial": "data"}
        mock_execution.error = None

        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        mock_session.execute.return_value = mock_result

        # Update only status and error
        success = await job_store.update_job_status(
            execution_id="exec_123",
            status=JobStatus.FAILED,
            error="Job failed due to timeout",
        )

        # Verify only specified fields were updated
        assert mock_execution.status == JobStatus.FAILED.value
        assert mock_execution.completed_at is None  # Not updated
        assert mock_execution.result == {"partial": "data"}  # Not updated
        assert mock_execution.error == "Job failed due to timeout"

        assert success is True

    @pytest.mark.asyncio
    async def test_update_job_status_database_error(self, job_store, mock_session):
        """Test update with database error."""
        # Mock execution found
        mock_execution = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        mock_session.execute.return_value = mock_result

        # Mock commit to raise exception
        mock_session.commit.side_effect = SQLAlchemyError("Database error")

        with pytest.raises(SQLAlchemyError):
            await job_store.update_job_status(
                execution_id="exec_123",
                status=JobStatus.FAILED,
            )

        # Verify rollback was called
        mock_session.rollback.assert_called_once()


class TestGetJobExecution:
    """Test get_job_execution functionality."""

    @pytest.mark.asyncio
    async def test_get_job_execution_found(self, job_store, mock_session):
        """Test getting existing job execution."""
        # Mock execution record
        mock_execution = Mock()
        mock_execution.id = uuid4()
        mock_execution.job_id = "job_123"
        mock_execution.job_type = "on_demand_audit"
        mock_execution.status = "completed"
        mock_execution.started_at = datetime.utcnow() - timedelta(hours=1)
        mock_execution.completed_at = datetime.utcnow()
        mock_execution.result = {"analysis_ids": ["analysis_123"]}
        mock_execution.error = None
        mock_execution.context = {"customer_id": "123456789"}
        mock_execution.retry_count = 0

        # Mock query result
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        mock_session.execute.return_value = mock_result

        execution = await job_store.get_job_execution("exec_123")

        # Verify query was executed correctly
        mock_session.execute.assert_called_once()

        # Verify returned data
        assert execution is not None
        assert execution["id"] == str(mock_execution.id)
        assert execution["job_id"] == "job_123"
        assert execution["job_type"] == "on_demand_audit"
        assert execution["status"] == "completed"
        assert execution["started_at"] == mock_execution.started_at
        assert execution["completed_at"] == mock_execution.completed_at
        assert execution["result"] == mock_execution.result
        assert execution["error"] is None
        assert execution["context"] == mock_execution.context
        assert execution["retry_count"] == 0

    @pytest.mark.asyncio
    async def test_get_job_execution_not_found(self, job_store, mock_session):
        """Test getting non-existent job execution."""
        # Mock query to return None
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = None
        mock_session.execute.return_value = mock_result

        execution = await job_store.get_job_execution("exec_123")

        assert execution is None


class TestListJobExecutions:
    """Test list_job_executions functionality."""

    @pytest.mark.asyncio
    async def test_list_job_executions_no_filters(self, job_store, mock_session):
        """Test listing all job executions."""
        # Mock execution records
        mock_executions = [
            self._create_mock_execution("exec_1", "job_1"),
            self._create_mock_execution("exec_2", "job_2"),
        ]

        # Mock query result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result

        executions = await job_store.list_job_executions()

        # Verify query was built correctly
        mock_session.execute.assert_called_once()

        # Verify returned data
        assert len(executions) == 2
        assert executions[0]["id"] == "exec_1"
        assert executions[1]["id"] == "exec_2"

    @pytest.mark.asyncio
    async def test_list_job_executions_with_filters(self, job_store, mock_session):
        """Test listing with filters."""
        mock_executions = [self._create_mock_execution("exec_1", "job_1")]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result

        start_date = datetime.utcnow() - timedelta(days=7)
        end_date = datetime.utcnow()

        executions = await job_store.list_job_executions(
            job_id="job_123",
            job_type=JobType.QUARTERLY_AUDIT,
            status=JobStatus.COMPLETED,
            start_date=start_date,
            end_date=end_date,
            limit=50,
        )

        # Verify query was executed
        mock_session.execute.assert_called_once()

        # Verify returned data
        assert len(executions) == 1
        assert executions[0]["id"] == "exec_1"

    @pytest.mark.asyncio
    async def test_list_job_executions_empty_result(self, job_store, mock_session):
        """Test listing with no results."""
        # Mock empty result
        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = []
        mock_session.execute.return_value = mock_result

        executions = await job_store.list_job_executions()

        assert executions == []

    @pytest.mark.asyncio
    async def test_list_job_executions_with_individual_filters(
        self, job_store, mock_session
    ):
        """Test listing with individual filter combinations."""
        mock_executions = [self._create_mock_execution("exec_1", "job_1")]

        mock_result = Mock()
        mock_result.scalars.return_value.all.return_value = mock_executions
        mock_session.execute.return_value = mock_result

        # Test job_id filter only
        await job_store.list_job_executions(job_id="job_123")
        mock_session.execute.assert_called()

        # Test job_type filter only
        await job_store.list_job_executions(job_type=JobType.ON_DEMAND_AUDIT)
        assert mock_session.execute.call_count == 2

        # Test status filter only
        await job_store.list_job_executions(status=JobStatus.FAILED)
        assert mock_session.execute.call_count == 3

        # Test date filters only
        start_date = datetime.utcnow() - timedelta(days=1)
        await job_store.list_job_executions(start_date=start_date)
        assert mock_session.execute.call_count == 4

        end_date = datetime.utcnow()
        await job_store.list_job_executions(end_date=end_date)
        assert mock_session.execute.call_count == 5

    def _create_mock_execution(self, exec_id: str, job_id: str):
        """Helper to create mock execution record."""
        mock_execution = Mock()
        mock_execution.id = exec_id
        mock_execution.job_id = job_id
        mock_execution.job_type = "on_demand_audit"
        mock_execution.status = "completed"
        mock_execution.started_at = datetime.utcnow()
        mock_execution.completed_at = datetime.utcnow()
        mock_execution.result = {}
        mock_execution.error = None
        mock_execution.context = {}
        mock_execution.retry_count = 0
        return mock_execution


class TestJobHistoryStoreIntegration:
    """Integration-style tests for JobHistoryStore."""

    @pytest.mark.asyncio
    async def test_complete_job_lifecycle(self, job_store, mock_session):
        """Test complete job execution lifecycle."""
        # Mock execution for save
        mock_execution = Mock()
        mock_execution.id = "exec_123"

        async def mock_refresh(execution):
            execution.id = "exec_123"

        mock_session.refresh = AsyncMock(side_effect=mock_refresh)

        # 1. Save new execution
        execution_id = await job_store.save_job_execution(
            job_id="job_123",
            job_type=JobType.ON_DEMAND_AUDIT,
            status=JobStatus.PENDING,
            started_at=datetime.utcnow(),
        )
        assert execution_id == "exec_123"

        # 2. Update to running
        mock_execution_record = Mock()
        mock_execution_record.status = JobStatus.PENDING.value
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution_record
        mock_session.execute.return_value = mock_result

        success = await job_store.update_job_status(
            execution_id=execution_id,
            status=JobStatus.RUNNING,
        )
        assert success is True
        assert mock_execution_record.status == JobStatus.RUNNING.value

        # 3. Update to completed
        mock_execution_record.status = JobStatus.RUNNING.value
        completed_at = datetime.utcnow()
        result = {"analysis_ids": ["analysis_123"]}

        success = await job_store.update_job_status(
            execution_id=execution_id,
            status=JobStatus.COMPLETED,
            completed_at=completed_at,
            result=result,
        )
        assert success is True
        assert mock_execution_record.status == JobStatus.COMPLETED.value
        assert mock_execution_record.completed_at == completed_at
        assert mock_execution_record.result == result

        # Verify all operations committed
        assert mock_session.commit.call_count == 3
        mock_session.rollback.assert_not_called()

    @pytest.mark.asyncio
    async def test_error_handling_with_rollback(self, job_store, mock_session):
        """Test error handling ensures proper rollback."""
        # Test save with error
        mock_session.commit.side_effect = [SQLAlchemyError("Save error")]

        with pytest.raises(SQLAlchemyError):
            await job_store.save_job_execution(
                job_id="job_123",
                job_type=JobType.ON_DEMAND_AUDIT,
                status=JobStatus.PENDING,
                started_at=datetime.utcnow(),
            )

        # Verify rollback was called
        mock_session.rollback.assert_called_once()

        # Reset for update test
        mock_session.reset_mock()
        mock_execution = Mock()
        mock_result = Mock()
        mock_result.scalar_one_or_none.return_value = mock_execution
        mock_session.execute.return_value = mock_result
        mock_session.commit.side_effect = [SQLAlchemyError("Update error")]

        with pytest.raises(SQLAlchemyError):
            await job_store.update_job_status(
                execution_id="exec_123",
                status=JobStatus.FAILED,
            )

        # Verify rollback was called again
        mock_session.rollback.assert_called_once()
