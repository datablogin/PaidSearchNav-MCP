"""Tests for Workflow Engine."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav_mcp.auth.oauth_manager import OAuth2Manager
from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.core.exceptions import WorkflowError
from paidsearchnav_mcp.integrations.google_ads_write_client import (
    GoogleAdsWriteClient,
    WriteOperationResult,
    WriteOperationStatus,
    WriteOperationType,
)
from paidsearchnav_mcp.workflows.workflow_engine import (
    StepStatus,
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowPriority,
    WorkflowStatus,
    WorkflowStep,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings()


@pytest.fixture
def mock_oauth_manager():
    """Create mock OAuth manager."""
    return AsyncMock(spec=OAuth2Manager)


@pytest.fixture
def mock_write_client():
    """Create mock write client."""
    return AsyncMock(spec=GoogleAdsWriteClient)


@pytest.fixture
def workflow_engine(mock_settings, mock_oauth_manager, mock_write_client):
    """Create workflow engine for testing."""
    return WorkflowEngine(
        settings=mock_settings,
        oauth_manager=mock_oauth_manager,
        write_client=mock_write_client,
        max_concurrent_workflows=2,
        max_concurrent_steps=3,
    )


@pytest.fixture
def sample_workflow_step():
    """Create sample workflow step."""
    return WorkflowStep(
        name="Add negative keywords",
        operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
        operation_data={
            "campaign_id": "111",
            "keywords": ["free", "cheap"],
            "match_type": "BROAD",
        },
    )


@pytest.fixture
def sample_workflow_definition(sample_workflow_step):
    """Create sample workflow definition."""
    return WorkflowDefinition(
        name="Test Workflow",
        description="Test workflow for negative keywords",
        customer_id="1234567890",
        priority=WorkflowPriority.NORMAL,
        dry_run=True,
        steps=[sample_workflow_step],
    )


class TestWorkflowEngine:
    """Test WorkflowEngine functionality."""

    async def test_submit_workflow_success(
        self, workflow_engine, sample_workflow_definition, mock_write_client
    ):
        """Test successful workflow submission."""
        mock_write_client.validate_write_permissions.return_value = True

        execution_id = await workflow_engine.submit_workflow(sample_workflow_definition)

        assert execution_id is not None
        assert execution_id in workflow_engine._active_executions

        execution = workflow_engine._active_executions[execution_id]
        assert execution.workflow_id == sample_workflow_definition.workflow_id
        assert execution.customer_id == sample_workflow_definition.customer_id
        assert execution.total_operations == len(sample_workflow_definition.steps)

    async def test_submit_workflow_validation_failure(
        self, workflow_engine, mock_write_client
    ):
        """Test workflow submission with validation failure."""
        # Create invalid workflow (no steps)
        invalid_workflow = WorkflowDefinition(
            name="Invalid Workflow",
            customer_id="1234567890",
            steps=[],
        )

        with pytest.raises(WorkflowError, match="Workflow must have at least one step"):
            await workflow_engine.submit_workflow(invalid_workflow)

    async def test_submit_workflow_permission_failure(
        self, workflow_engine, sample_workflow_definition, mock_write_client
    ):
        """Test workflow submission with permission failure."""
        # Non-dry-run workflow without permissions
        sample_workflow_definition.dry_run = False
        mock_write_client.validate_write_permissions.return_value = False

        with pytest.raises(WorkflowError, match="Insufficient permissions"):
            await workflow_engine.submit_workflow(sample_workflow_definition)

    async def test_validate_workflow_dependency_cycle(self, workflow_engine):
        """Test workflow validation with dependency cycle."""
        step1 = WorkflowStep(
            name="Step 1",
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            operation_data={},
            depends_on=["step2_id"],
        )
        step2 = WorkflowStep(
            step_id="step2_id",
            name="Step 2",
            operation_type=WriteOperationType.UPDATE_BUDGETS,
            operation_data={},
            depends_on=[step1.step_id],
        )

        workflow = WorkflowDefinition(
            name="Cyclic Workflow",
            customer_id="1234567890",
            steps=[step1, step2],
        )

        # This should pass validation despite the cycle (basic validation only checks existence)
        await workflow_engine._validate_workflow(workflow)

    async def test_validate_workflow_invalid_dependencies(self, workflow_engine):
        """Test workflow validation with invalid dependencies."""
        step = WorkflowStep(
            name="Step with invalid dep",
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            operation_data={},
            depends_on=["non_existent_step"],
        )

        workflow = WorkflowDefinition(
            name="Invalid Dependencies",
            customer_id="1234567890",
            steps=[step],
        )

        with pytest.raises(WorkflowError, match="invalid dependencies"):
            await workflow_engine._validate_workflow(workflow)

    async def test_execute_step_success(
        self, workflow_engine, sample_workflow_step, mock_write_client
    ):
        """Test successful step execution."""
        customer_id = "1234567890"
        workflow = WorkflowDefinition(
            name="Test", customer_id=customer_id, steps=[sample_workflow_step]
        )
        execution = WorkflowExecution(
            workflow_id=workflow.workflow_id,
            customer_id=customer_id,
            dry_run=True,
            step_executions={sample_workflow_step.step_id: sample_workflow_step},
        )

        # Mock successful operation result
        mock_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.COMPLETED,
            resource_name="test_resource",
            success=True,
        )
        mock_write_client.add_negative_keywords.return_value = [mock_result]

        success = await workflow_engine._execute_step(
            workflow, sample_workflow_step, execution
        )

        assert success is True
        assert (
            execution.step_executions[sample_workflow_step.step_id].status
            == StepStatus.COMPLETED
        )

    async def test_execute_step_failure(
        self, workflow_engine, sample_workflow_step, mock_write_client
    ):
        """Test step execution failure."""
        customer_id = "1234567890"
        workflow = WorkflowDefinition(
            name="Test", customer_id=customer_id, steps=[sample_workflow_step]
        )
        execution = WorkflowExecution(
            workflow_id=workflow.workflow_id,
            customer_id=customer_id,
            dry_run=True,
            step_executions={sample_workflow_step.step_id: sample_workflow_step},
        )

        # Mock failed operation result
        mock_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.FAILED,
            resource_name="",
            success=False,
            error_message="API Error",
        )
        mock_write_client.add_negative_keywords.return_value = [mock_result]

        success = await workflow_engine._execute_step(
            workflow, sample_workflow_step, execution
        )

        assert success is False
        assert (
            execution.step_executions[sample_workflow_step.step_id].status
            == StepStatus.FAILED
        )

    async def test_execute_step_retry_logic(
        self, workflow_engine, sample_workflow_step, mock_write_client
    ):
        """Test step retry logic."""
        customer_id = "1234567890"
        sample_workflow_step.max_retries = 2
        workflow = WorkflowDefinition(
            name="Test", customer_id=customer_id, steps=[sample_workflow_step]
        )
        execution = WorkflowExecution(
            workflow_id=workflow.workflow_id,
            customer_id=customer_id,
            dry_run=True,
            step_executions={sample_workflow_step.step_id: sample_workflow_step},
        )

        # First call raises exception, second call succeeds
        mock_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.COMPLETED,
            resource_name="test_resource",
            success=True,
        )
        mock_write_client.add_negative_keywords.side_effect = [
            Exception("Temporary failure"),
            [mock_result],
        ]

        with patch("asyncio.sleep"):  # Speed up retry delay
            success = await workflow_engine._execute_step(
                workflow, sample_workflow_step, execution
            )

        assert success is True
        assert execution.step_executions[sample_workflow_step.step_id].retry_count == 1

    async def test_execute_step_max_retries_exceeded(
        self, workflow_engine, sample_workflow_step, mock_write_client
    ):
        """Test step execution with max retries exceeded."""
        customer_id = "1234567890"
        sample_workflow_step.max_retries = 1
        workflow = WorkflowDefinition(
            name="Test", customer_id=customer_id, steps=[sample_workflow_step]
        )
        execution = WorkflowExecution(
            workflow_id=workflow.workflow_id,
            customer_id=customer_id,
            dry_run=True,
            step_executions={sample_workflow_step.step_id: sample_workflow_step},
        )

        # Always fails
        mock_write_client.add_negative_keywords.side_effect = Exception(
            "Persistent failure"
        )

        with patch("asyncio.sleep"):  # Speed up retry delay
            success = await workflow_engine._execute_step(
                workflow, sample_workflow_step, execution
            )

        assert success is False
        assert (
            execution.step_executions[sample_workflow_step.step_id].status
            == StepStatus.FAILED
        )
        assert execution.step_executions[sample_workflow_step.step_id].retry_count == 1

    async def test_rollback_workflow(
        self, workflow_engine, sample_workflow_definition, mock_write_client
    ):
        """Test workflow rollback."""
        execution = WorkflowExecution(
            workflow_id=sample_workflow_definition.workflow_id,
            customer_id=sample_workflow_definition.customer_id,
            dry_run=False,
            step_executions={},
        )

        # Mock rollback success
        mock_rollback_result = WriteOperationResult(
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            status=WriteOperationStatus.ROLLED_BACK,
            resource_name="test_resource",
            success=True,
        )
        mock_write_client.rollback_operations.return_value = [mock_rollback_result]

        completed_steps = {"step1", "step2"}
        await workflow_engine._rollback_workflow(
            sample_workflow_definition, execution, completed_steps
        )

        assert execution.status == WorkflowStatus.ROLLED_BACK
        assert execution.rollback_completed is True

    async def test_rollback_workflow_failure(
        self, workflow_engine, sample_workflow_definition, mock_write_client
    ):
        """Test workflow rollback failure."""
        execution = WorkflowExecution(
            workflow_id=sample_workflow_definition.workflow_id,
            customer_id=sample_workflow_definition.customer_id,
            dry_run=False,
            step_executions={},
        )

        mock_write_client.rollback_operations.side_effect = Exception("Rollback failed")

        completed_steps = {"step1"}
        await workflow_engine._rollback_workflow(
            sample_workflow_definition, execution, completed_steps
        )

        assert execution.status == WorkflowStatus.FAILED
        assert "Rollback failed" in execution.error_summary

    async def test_get_workflow_status(
        self, workflow_engine, sample_workflow_definition
    ):
        """Test getting workflow status."""
        # Submit workflow to create execution
        execution_id = await workflow_engine.submit_workflow(sample_workflow_definition)

        # Get status
        status = await workflow_engine.get_workflow_status(execution_id)

        assert status is not None
        assert status.execution_id == execution_id
        assert status.workflow_id == sample_workflow_definition.workflow_id

    async def test_get_workflow_status_not_found(self, workflow_engine):
        """Test getting status for non-existent workflow."""
        status = await workflow_engine.get_workflow_status("non_existent_id")
        assert status is None

    async def test_cancel_workflow_success(
        self, workflow_engine, sample_workflow_definition
    ):
        """Test successful workflow cancellation."""
        execution_id = await workflow_engine.submit_workflow(sample_workflow_definition)

        success = await workflow_engine.cancel_workflow(execution_id)

        assert success is True

        execution = workflow_engine._active_executions[execution_id]
        assert execution.status == WorkflowStatus.CANCELLED

    async def test_cancel_workflow_not_found(self, workflow_engine):
        """Test cancelling non-existent workflow."""
        success = await workflow_engine.cancel_workflow("non_existent_id")
        assert success is False

    async def test_cancel_already_completed_workflow(
        self, workflow_engine, sample_workflow_definition
    ):
        """Test cancelling already completed workflow."""
        execution_id = await workflow_engine.submit_workflow(sample_workflow_definition)

        # Mark as completed
        execution = workflow_engine._active_executions[execution_id]
        execution.status = WorkflowStatus.COMPLETED

        success = await workflow_engine.cancel_workflow(execution_id)
        assert success is False

    async def test_list_active_workflows(
        self, workflow_engine, sample_workflow_definition
    ):
        """Test listing active workflows."""
        # Initially empty
        workflows = await workflow_engine.list_active_workflows()
        assert len(workflows) == 0

        # Submit workflow
        await workflow_engine.submit_workflow(sample_workflow_definition)

        workflows = await workflow_engine.list_active_workflows()
        assert len(workflows) == 1

    async def test_cleanup_completed_workflows(
        self, workflow_engine, sample_workflow_definition
    ):
        """Test cleanup of completed workflows."""
        execution_id = await workflow_engine.submit_workflow(sample_workflow_definition)

        # Mark as completed and old
        execution = workflow_engine._active_executions[execution_id]
        execution.status = WorkflowStatus.COMPLETED
        execution.completed_at = datetime.utcnow() - timedelta(hours=25)

        cleaned_count = await workflow_engine.cleanup_completed_workflows(
            max_age_hours=24
        )

        assert cleaned_count == 1
        assert execution_id not in workflow_engine._active_executions

    async def test_health_check_success(self, workflow_engine, mock_write_client):
        """Test successful health check."""
        mock_write_client.health_check.return_value = {"healthy": True}

        result = await workflow_engine.health_check()

        assert result["healthy"] is True
        assert "active_executions" in result
        assert "queued_workflows" in result
        assert "write_client" in result

    async def test_health_check_failure(self, workflow_engine, mock_write_client):
        """Test health check failure."""
        mock_write_client.health_check.side_effect = Exception("Health check failed")

        result = await workflow_engine.health_check()

        assert result["healthy"] is False
        assert "error" in result


class TestWorkflowModels:
    """Test workflow data models."""

    def test_workflow_step_creation(self):
        """Test WorkflowStep creation."""
        step = WorkflowStep(
            name="Test Step",
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            operation_data={"test": "data"},
            depends_on=["step1"],
            max_retries=5,
        )

        assert step.name == "Test Step"
        assert step.operation_type == WriteOperationType.ADD_NEGATIVE_KEYWORDS
        assert step.operation_data == {"test": "data"}
        assert step.depends_on == ["step1"]
        assert step.max_retries == 5
        assert step.status == StepStatus.PENDING
        assert step.retry_count == 0

    def test_workflow_definition_creation(self):
        """Test WorkflowDefinition creation."""
        step = WorkflowStep(
            name="Test Step",
            operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
            operation_data={},
        )

        workflow = WorkflowDefinition(
            name="Test Workflow",
            description="Test workflow description",
            customer_id="1234567890",
            priority=WorkflowPriority.HIGH,
            dry_run=False,
            steps=[step],
            metadata={"test": "metadata"},
        )

        assert workflow.name == "Test Workflow"
        assert workflow.description == "Test workflow description"
        assert workflow.customer_id == "1234567890"
        assert workflow.priority == WorkflowPriority.HIGH
        assert workflow.dry_run is False
        assert len(workflow.steps) == 1
        assert workflow.metadata == {"test": "metadata"}

    def test_workflow_execution_creation(self):
        """Test WorkflowExecution creation."""
        execution = WorkflowExecution(
            workflow_id="workflow123",
            customer_id="1234567890",
            dry_run=True,
            total_operations=5,
        )

        assert execution.workflow_id == "workflow123"
        assert execution.customer_id == "1234567890"
        assert execution.dry_run is True
        assert execution.total_operations == 5
        assert execution.status == WorkflowStatus.PENDING
        assert execution.completed_operations == 0
        assert execution.failed_operations == 0
        assert execution.progress_percentage == 0.0


class TestWorkflowQueue:
    """Test workflow queue functionality."""

    async def test_workflow_priority_queue(self, workflow_engine):
        """Test workflow priority queueing."""
        # Create workflows with different priorities
        low_priority = WorkflowDefinition(
            name="Low Priority",
            customer_id="1234567890",
            priority=WorkflowPriority.LOW,
            steps=[
                WorkflowStep(
                    name="Test",
                    operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                    operation_data={},
                )
            ],
        )

        critical_priority = WorkflowDefinition(
            name="Critical Priority",
            customer_id="1234567890",
            priority=WorkflowPriority.CRITICAL,
            steps=[
                WorkflowStep(
                    name="Test",
                    operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                    operation_data={},
                )
            ],
        )

        high_priority = WorkflowDefinition(
            name="High Priority",
            customer_id="1234567890",
            priority=WorkflowPriority.HIGH,
            steps=[
                WorkflowStep(
                    name="Test",
                    operation_type=WriteOperationType.ADD_NEGATIVE_KEYWORDS,
                    operation_data={},
                )
            ],
        )

        # Submit in order: low, critical, high
        await workflow_engine.submit_workflow(low_priority)
        await workflow_engine.submit_workflow(critical_priority)
        await workflow_engine.submit_workflow(high_priority)

        # Queue should be ordered: critical, high, low
        assert len(workflow_engine._workflow_queue) == 3
        assert workflow_engine._workflow_queue[0].priority == WorkflowPriority.CRITICAL
        assert workflow_engine._workflow_queue[1].priority == WorkflowPriority.HIGH
        assert workflow_engine._workflow_queue[2].priority == WorkflowPriority.LOW
