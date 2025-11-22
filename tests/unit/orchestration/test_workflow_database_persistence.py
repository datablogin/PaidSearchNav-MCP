"""Unit tests for workflow database persistence."""

import asyncio
import uuid
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.ext.asyncio import AsyncSession

from paidsearchnav.core.config import Settings, WorkflowConfig
from paidsearchnav.orchestration.workflow_engine_db import DatabaseWorkflowOrchestrator
from paidsearchnav.storage.models import (
    WorkflowDefinition as DBWorkflowDefinition,
)
from paidsearchnav.storage.models import (
    WorkflowExecution as DBWorkflowExecution,
)
from paidsearchnav.storage.models import (
    WorkflowStep as DBWorkflowStep,
)


@pytest.fixture
def settings():
    """Create test settings with database persistence enabled."""
    return Settings(
        workflow=WorkflowConfig(
            persistence_mode="database",
            enable_database_persistence=True,
            context_ttl_hours=24,
            cleanup_interval_minutes=30,
        )
    )


@pytest.fixture
def mock_db_session():
    """Create a mock database session."""
    session = AsyncMock(spec=AsyncSession)
    session.add = MagicMock()
    session.commit = AsyncMock()
    session.refresh = AsyncMock()
    session.execute = AsyncMock()
    return session


@pytest.fixture
def mock_step_executor_registry():
    """Create a mock step executor registry."""
    registry = MagicMock()
    executor = AsyncMock()
    executor.execute = AsyncMock(return_value={"result": "success"})
    registry.get_executor = MagicMock(return_value=executor)
    return registry


@pytest.fixture
def mock_workflow_monitor():
    """Create a mock workflow monitor."""
    monitor = MagicMock()
    monitor.start_execution = MagicMock()
    monitor.end_execution = MagicMock()
    return monitor


@pytest.mark.asyncio
async def test_create_workflow_definition_database(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test creating a workflow definition in database mode."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Create workflow definition
    definition = {
        "name": "test_workflow",
        "version": "1.0",
        "steps": [
            {"name": "step1", "service": "test_service"},
            {"name": "step2", "service": "test_service"},
        ],
    }

    result = await orchestrator.create_workflow_definition(
        name="test_workflow", version="1.0", definition=definition
    )

    # Verify database operations
    mock_db_session.add.assert_called_once()
    mock_db_session.commit.assert_called_once()
    mock_db_session.refresh.assert_called_once()

    # Verify the added object is a DBWorkflowDefinition
    added_obj = mock_db_session.add.call_args[0][0]
    assert isinstance(added_obj, DBWorkflowDefinition)
    assert added_obj.name == "test_workflow"
    assert added_obj.version == "1.0"
    assert added_obj.definition == definition
    assert added_obj.enabled is True


@pytest.mark.asyncio
async def test_create_workflow_definition_memory_mode(settings):
    """Test creating a workflow definition in memory mode."""
    # Modify settings for memory mode
    settings.workflow.persistence_mode = "memory"
    settings.workflow.enable_database_persistence = False

    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=None,  # No database session in memory mode
    )

    definition = {
        "name": "test_workflow",
        "version": "1.0",
        "steps": [{"name": "step1", "service": "test_service"}],
    }

    result = await orchestrator.create_workflow_definition(
        name="test_workflow", version="1.0", definition=definition
    )

    # Verify in-memory storage
    assert result.name == "test_workflow"
    assert result.version == "1.0"
    assert result.definition == definition
    assert result.id in orchestrator.workflow_definitions


@pytest.mark.asyncio
async def test_start_workflow_database(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test starting a workflow execution with database persistence."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock workflow definition query
    mock_workflow_def = DBWorkflowDefinition(
        id=str(uuid.uuid4()),
        name="test_workflow",
        version="1.0",
        definition={
            "name": "test_workflow",
            "steps": [{"name": "step1", "service": "test_service"}],
        },
        enabled=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_workflow_def)
    mock_db_session.execute.return_value = mock_result

    # Start workflow
    context = {"key": "value"}
    with patch("asyncio.create_task"):
        result = await orchestrator.start_workflow(
            workflow_name="test_workflow", customer_id="customer123", context=context
        )

    # Verify database operations
    assert mock_db_session.add.called
    assert mock_db_session.commit.called

    # Verify the execution object
    added_execution = mock_db_session.add.call_args[0][0]
    assert isinstance(added_execution, DBWorkflowExecution)
    assert added_execution.workflow_definition_id == mock_workflow_def.id
    assert added_execution.customer_id == "customer123"
    assert added_execution.status == "pending"
    assert added_execution.context == context

    # Verify workflow monitor was started
    mock_workflow_monitor.start_execution.assert_called_once()


@pytest.mark.asyncio
async def test_get_workflow_status_database(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test getting workflow status from database."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock execution and steps
    execution_id = str(uuid.uuid4())
    mock_execution = DBWorkflowExecution(
        id=execution_id,
        workflow_definition_id=str(uuid.uuid4()),
        customer_id="customer123",
        status="running",
        current_step="step1",
        started_at=datetime.now(timezone.utc),
        context={},
        retry_count=0,
    )

    mock_steps = [
        DBWorkflowStep(
            id=str(uuid.uuid4()),
            execution_id=execution_id,
            step_name="step1",
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            retry_count=0,
        ),
        DBWorkflowStep(
            id=str(uuid.uuid4()),
            execution_id=execution_id,
            step_name="step2",
            status="running",
            started_at=datetime.now(timezone.utc),
            retry_count=0,
        ),
    ]

    # Mock database queries
    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=mock_execution)

    steps_result = MagicMock()
    steps_result.scalars = MagicMock()
    steps_result.scalars.return_value.all = MagicMock(return_value=mock_steps)

    mock_db_session.execute = AsyncMock(side_effect=[exec_result, steps_result])

    # Get workflow status
    status = await orchestrator.get_workflow_status(execution_id)

    # Verify result
    assert status["execution_id"] == execution_id
    assert status["status"] == "running"
    assert status["current_step"] == "step1"
    assert len(status["steps"]) == 2
    assert status["steps"][0]["step_name"] == "step1"
    assert status["steps"][0]["status"] == "completed"
    assert status["steps"][1]["step_name"] == "step2"
    assert status["steps"][1]["status"] == "running"


@pytest.mark.asyncio
async def test_pause_resume_cancel_workflow_database(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test pausing, resuming, and cancelling workflows with database persistence."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    execution_id = str(uuid.uuid4())

    # Test pause
    mock_execution = DBWorkflowExecution(
        id=execution_id,
        workflow_definition_id=str(uuid.uuid4()),
        customer_id="customer123",
        status="running",
    )

    exec_result = MagicMock()
    exec_result.scalar_one_or_none = MagicMock(return_value=mock_execution)
    mock_db_session.execute = AsyncMock(return_value=exec_result)

    await orchestrator.pause_workflow(execution_id)
    assert mock_execution.status == "paused"
    mock_db_session.commit.assert_called()

    # Test resume
    mock_execution.status = "paused"

    # Mock workflow definition for resume
    mock_workflow_def = DBWorkflowDefinition(
        id=mock_execution.workflow_definition_id,
        name="test_workflow",
        version="1.0",
        definition={"steps": []},
        enabled=True,
    )

    # Mock the get_workflow_definition_by_id call
    with patch.object(
        orchestrator, "get_workflow_definition_by_id", return_value=mock_workflow_def
    ):
        with patch("asyncio.create_task"):
            await orchestrator.resume_workflow(execution_id)

    assert mock_execution.status == "running"
    mock_db_session.commit.assert_called()

    # Test cancel
    mock_execution.status = "running"
    await orchestrator.cancel_workflow(execution_id)
    assert mock_execution.status == "cancelled"
    assert mock_execution.completed_at is not None
    mock_db_session.commit.assert_called()


@pytest.mark.asyncio
async def test_list_workflow_definitions_database(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test listing workflow definitions from database."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock workflow definitions (use MagicMock to avoid validation)
    def1 = MagicMock()
    def1.id = str(uuid.uuid4())
    def1.name = "workflow1"
    def1.version = "1.0"
    def1.definition = {"name": "workflow1", "steps": []}
    def1.enabled = True

    def2 = MagicMock()
    def2.id = str(uuid.uuid4())
    def2.name = "workflow2"
    def2.version = "2.0"
    def2.definition = {"name": "workflow2", "steps": []}
    def2.enabled = True

    mock_definitions = [def1, def2]

    result = MagicMock()
    result.scalars = MagicMock()
    result.scalars.return_value.all = MagicMock(return_value=mock_definitions)
    mock_db_session.execute = AsyncMock(return_value=result)

    # List definitions
    definitions = await orchestrator.list_workflow_definitions(enabled_only=True)

    # Verify
    assert len(definitions) == 2
    assert definitions[0].name == "workflow1"
    assert definitions[1].name == "workflow2"


@pytest.mark.asyncio
async def test_context_stats_database_mode(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test getting context stats in database mode."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    stats = orchestrator.get_context_stats()

    assert stats["mode"] == "database"
    assert "message" in stats


@pytest.mark.asyncio
async def test_context_stats_memory_mode(settings):
    """Test getting context stats in memory mode."""
    # Configure for memory mode
    settings.workflow.persistence_mode = "memory"
    settings.workflow.enable_database_persistence = False

    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=None,
    )

    # Add some test contexts
    orchestrator._execution_contexts["exec1"] = {"data": "test1"}
    orchestrator._execution_contexts["exec2"] = {"data": "test2"}
    orchestrator._execution_timestamps["exec1"] = datetime.now(timezone.utc)
    orchestrator._execution_timestamps["exec2"] = datetime.now(timezone.utc)

    stats = orchestrator.get_context_stats()

    assert stats["mode"] == "memory"
    assert stats["total_contexts"] == 2
    assert stats["active_contexts"] == 2
    assert stats["expired_contexts"] == 0
    assert stats["context_ttl_hours"] == 24


@pytest.mark.asyncio
async def test_workflow_execution_with_step_failure_and_retry(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test workflow execution with step failure and retry logic."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock a step executor that fails on first attempt
    executor = AsyncMock()
    executor.execute = AsyncMock(
        side_effect=[Exception("Step failed"), {"result": "success on retry"}]
    )
    mock_step_executor_registry.get_executor = MagicMock(return_value=executor)

    # Create a workflow with retry configuration
    definition = {
        "name": "test_workflow",
        "steps": [{"name": "step1", "service": "test_service", "retry": 1}],
    }

    # Mock workflow definition
    mock_workflow_def = MagicMock(
        id=str(uuid.uuid4()),
        name="test_workflow",
        version="1.0",
        definition=definition,
        enabled=True,
    )

    # Mock execution
    mock_execution = MagicMock(
        id=str(uuid.uuid4()),
        workflow_definition_id=mock_workflow_def.id,
        customer_id="customer123",
        status="running",
        context={},
    )

    # Execute step with retry
    await orchestrator._execute_step(
        mock_execution, definition["steps"][0], MagicMock()
    )

    # Verify step was retried
    assert executor.execute.call_count == 2


@pytest.mark.asyncio
async def test_invalid_workflow_definition(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test creating an invalid workflow definition."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Invalid definition (missing steps and name)
    invalid_definition = {"invalid": "data"}

    with pytest.raises(ValueError, match="must contain 'steps' or 'name'"):
        await orchestrator.create_workflow_definition(
            name="invalid_workflow", version="1.0", definition=invalid_definition
        )


@pytest.mark.asyncio
async def test_concurrent_workflow_prevention(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test prevention of concurrent workflow executions for same customer."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock workflow definition
    mock_workflow_def = DBWorkflowDefinition(
        id=str(uuid.uuid4()),
        name="test_workflow",
        version="1.0",
        definition={"steps": []},
        enabled=True,
    )

    mock_result = MagicMock()
    mock_result.scalar_one_or_none = MagicMock(return_value=mock_workflow_def)
    mock_db_session.execute.return_value = mock_result

    # Start first workflow
    with patch("asyncio.create_task"):
        execution1 = await orchestrator.start_workflow(
            workflow_name="test_workflow", customer_id="customer123", context={}
        )

    # Try to start second workflow for same customer (should fail)
    with pytest.raises(ValueError, match="already running"):
        await orchestrator.start_workflow(
            workflow_name="test_workflow", customer_id="customer123", context={}
        )


@pytest.mark.asyncio
async def test_context_size_validation(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test context size validation."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Create a context that exceeds size limits
    large_context = {"data": "x" * (1024 * 1024 + 1)}  # > 1MB

    with pytest.raises(ValueError, match="Context size.*exceeds maximum"):
        orchestrator._validate_context_size(large_context)


@pytest.mark.asyncio
async def test_step_config_validation(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test step configuration validation."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Test missing required fields
    with pytest.raises(ValueError, match="missing required field: name"):
        orchestrator._validate_step_config({"service": "test"})

    with pytest.raises(ValueError, match="missing required field: service"):
        orchestrator._validate_step_config({"name": "test"})

    # Test invalid field values
    with pytest.raises(ValueError, match="must be a non-empty string"):
        orchestrator._validate_step_config({"name": "", "service": "test"})

    with pytest.raises(ValueError, match="must be a non-empty string"):
        orchestrator._validate_step_config({"name": "test", "service": ""})


@pytest.mark.asyncio
async def test_error_message_truncation(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test error message truncation."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Test normal message (no truncation)
    normal_message = "This is a normal error message"
    result = orchestrator._truncate_error_message(normal_message)
    assert result == normal_message

    # Test long message (should be truncated)
    long_message = "x" * 2000  # Longer than MAX_ERROR_MESSAGE_LENGTH
    result = orchestrator._truncate_error_message(long_message)
    assert len(result) <= 1900  # MAX_ERROR_MESSAGE_LENGTH
    assert result.endswith("...")


@pytest.mark.asyncio
async def test_shutdown_cleanup(settings):
    """Test proper shutdown and cleanup of tasks."""
    # Configure for memory mode to test cleanup task
    settings.workflow.persistence_mode = "memory"
    settings.workflow.enable_database_persistence = False

    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=None,
    )

    # Verify cleanup task was created
    assert orchestrator._cleanup_task is not None
    assert not orchestrator._cleanup_task.done()

    # Test shutdown
    await orchestrator.shutdown()

    # Verify cleanup task was cancelled
    assert orchestrator._cleanup_task.done()
    assert orchestrator._shutdown_event.is_set()


@pytest.mark.asyncio
async def test_background_task_management(settings):
    """Test background task creation and management."""
    settings.workflow.persistence_mode = "memory"
    settings.workflow.enable_database_persistence = False

    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=None,
    )

    # Create a background task
    async def dummy_task():
        await asyncio.sleep(0.1)

    task = orchestrator._create_background_task(dummy_task())

    # Verify task was added to background tasks
    assert task in orchestrator._background_tasks

    # Wait for task completion
    await task

    # Verify task was removed from background tasks after completion
    assert task not in orchestrator._background_tasks

    await orchestrator.shutdown()


@pytest.mark.asyncio
async def test_transaction_rollback_on_error(
    settings, mock_db_session, mock_step_executor_registry, mock_workflow_monitor
):
    """Test transaction rollback on database errors."""
    orchestrator = DatabaseWorkflowOrchestrator(
        settings=settings,
        db_session=mock_db_session,
        step_executor_registry=mock_step_executor_registry,
        workflow_monitor=mock_workflow_monitor,
    )

    # Mock database error during commit
    from sqlalchemy.exc import SQLAlchemyError

    mock_db_session.commit.side_effect = SQLAlchemyError("Database error")

    # Test that database transaction context manager handles errors
    with pytest.raises(SQLAlchemyError):
        async with orchestrator._database_transaction():
            pass

    # Verify rollback was called
    mock_db_session.rollback.assert_called_once()
