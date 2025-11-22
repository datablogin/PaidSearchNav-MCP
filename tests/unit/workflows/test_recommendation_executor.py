"""Tests for Recommendation Executor."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.core.exceptions import RecommendationError
from paidsearchnav.integrations.google_ads_write_client import GoogleAdsWriteClient
from paidsearchnav.workflows.recommendation_executor import (
    ExecutionResult,
    Recommendation,
    RecommendationBatch,
    RecommendationExecutor,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.workflows.workflow_engine import (
    WorkflowDefinition,
    WorkflowEngine,
    WorkflowExecution,
    WorkflowPriority,
    WorkflowStatus,
)


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    return Settings()


@pytest.fixture
def mock_workflow_engine():
    """Create mock workflow engine."""
    return AsyncMock(spec=WorkflowEngine)


@pytest.fixture
def mock_write_client():
    """Create mock write client."""
    return AsyncMock(spec=GoogleAdsWriteClient)


@pytest.fixture
def recommendation_executor(mock_settings, mock_workflow_engine, mock_write_client):
    """Create recommendation executor for testing."""
    return RecommendationExecutor(
        settings=mock_settings,
        workflow_engine=mock_workflow_engine,
        write_client=mock_write_client,
    )


@pytest.fixture
def sample_negative_keywords_recommendation():
    """Create sample negative keywords recommendation."""
    return Recommendation(
        recommendation_id="rec_001",
        type=RecommendationType.NEGATIVE_KEYWORDS,
        priority=RecommendationPriority.HIGH,
        title="Add negative keywords",
        description="Add blocking keywords to reduce wasted spend",
        customer_id="1234567890",
        campaign_ids=["111", "222"],
        data={"keywords": ["free", "cheap", "discount"], "match_type": "BROAD"},
        dry_run=True,
    )


@pytest.fixture
def sample_budget_recommendation():
    """Create sample budget optimization recommendation."""
    return Recommendation(
        recommendation_id="rec_002",
        type=RecommendationType.BUDGET_OPTIMIZATION,
        priority=RecommendationPriority.MEDIUM,
        title="Optimize campaign budgets",
        description="Adjust budgets based on performance data",
        customer_id="1234567890",
        campaign_ids=["111", "222"],
        data={
            "budget_changes": [
                {
                    "campaign_id": "111",
                    "new_budget_micros": 1000000,
                    "delivery_method": "STANDARD",
                },
                {
                    "campaign_id": "222",
                    "new_budget_micros": 2000000,
                    "delivery_method": "ACCELERATED",
                },
            ]
        },
        dry_run=True,
    )


@pytest.fixture
def sample_campaign_status_recommendation():
    """Create sample campaign status recommendation."""
    return Recommendation(
        recommendation_id="rec_003",
        type=RecommendationType.CAMPAIGN_PAUSE,
        priority=RecommendationPriority.CRITICAL,
        title="Pause underperforming campaigns",
        description="Pause campaigns with poor performance",
        customer_id="1234567890",
        campaign_ids=["333", "444"],
        data={},
        dry_run=True,
    )


class TestRecommendationExecutor:
    """Test RecommendationExecutor functionality."""

    async def test_execute_negative_keywords_recommendation(
        self,
        recommendation_executor,
        sample_negative_keywords_recommendation,
        mock_workflow_engine,
    ):
        """Test executing negative keywords recommendation."""
        mock_execution_id = "exec_001"
        mock_workflow_engine.submit_workflow.return_value = mock_execution_id

        # Mock workflow completion
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id=mock_execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.COMPLETED,
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            result = await recommendation_executor.execute_recommendation(
                sample_negative_keywords_recommendation
            )

        assert isinstance(result, ExecutionResult)
        assert result.recommendation_id == "rec_001"
        assert result.success is True
        assert result.execution_id == mock_execution_id
        assert result.completed_at is not None

        # Verify workflow was submitted
        mock_workflow_engine.submit_workflow.assert_called_once()
        submitted_workflow = mock_workflow_engine.submit_workflow.call_args[0][0]
        assert isinstance(submitted_workflow, WorkflowDefinition)
        assert submitted_workflow.customer_id == "1234567890"

    async def test_execute_budget_recommendation(
        self,
        recommendation_executor,
        sample_budget_recommendation,
        mock_workflow_engine,
    ):
        """Test executing budget optimization recommendation."""
        mock_execution_id = "exec_002"
        mock_workflow_engine.submit_workflow.return_value = mock_execution_id

        # Mock workflow completion
        mock_execution = WorkflowExecution(
            workflow_id="workflow_002",
            execution_id=mock_execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.COMPLETED,
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            result = await recommendation_executor.execute_recommendation(
                sample_budget_recommendation
            )

        assert result.success is True
        assert result.operations_count > 0  # Should have budget operations

    async def test_execute_campaign_status_recommendation(
        self,
        recommendation_executor,
        sample_campaign_status_recommendation,
        mock_workflow_engine,
    ):
        """Test executing campaign status recommendation."""
        mock_execution_id = "exec_003"
        mock_workflow_engine.submit_workflow.return_value = mock_execution_id

        # Mock workflow completion
        mock_execution = WorkflowExecution(
            workflow_id="workflow_003",
            execution_id=mock_execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.COMPLETED,
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            result = await recommendation_executor.execute_recommendation(
                sample_campaign_status_recommendation
            )

        assert result.success is True

    async def test_execute_recommendation_workflow_creation_failure(
        self, recommendation_executor, sample_negative_keywords_recommendation
    ):
        """Test recommendation execution with workflow creation failure."""
        # Mock workflow creation failure
        with patch.object(
            recommendation_executor,
            "_create_workflow_from_recommendation",
            return_value=None,
        ):
            result = await recommendation_executor.execute_recommendation(
                sample_negative_keywords_recommendation
            )

        assert result.success is False
        assert "Failed to create workflow" in result.error_message

    async def test_execute_recommendation_workflow_submission_failure(
        self,
        recommendation_executor,
        sample_negative_keywords_recommendation,
        mock_workflow_engine,
    ):
        """Test recommendation execution with workflow submission failure."""
        mock_workflow_engine.submit_workflow.side_effect = Exception(
            "Submission failed"
        )

        result = await recommendation_executor.execute_recommendation(
            sample_negative_keywords_recommendation
        )

        assert result.success is False
        assert "Submission failed" in result.error_message

    async def test_execute_recommendation_workflow_execution_failure(
        self,
        recommendation_executor,
        sample_negative_keywords_recommendation,
        mock_workflow_engine,
    ):
        """Test recommendation execution with workflow execution failure."""
        mock_execution_id = "exec_001"
        mock_workflow_engine.submit_workflow.return_value = mock_execution_id

        # Mock workflow failure
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id=mock_execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.FAILED,
            error_summary="Workflow execution failed",
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            result = await recommendation_executor.execute_recommendation(
                sample_negative_keywords_recommendation
            )

        assert result.success is False
        assert "Workflow failed" in result.error_message

    async def test_execute_batch_success(
        self,
        recommendation_executor,
        sample_negative_keywords_recommendation,
        sample_budget_recommendation,
        mock_workflow_engine,
    ):
        """Test successful batch execution."""
        batch = RecommendationBatch(
            batch_id="batch_001",
            name="Test Batch",
            customer_id="1234567890",
            recommendations=[
                sample_negative_keywords_recommendation,
                sample_budget_recommendation,
            ],
            dry_run=True,
        )

        mock_workflow_engine.submit_workflow.return_value = "exec_001"

        # Mock successful completions
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id="exec_001",
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.COMPLETED,
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            results = await recommendation_executor.execute_batch(batch)

        assert len(results) == 2
        assert all(r.success for r in results)

    async def test_execute_batch_critical_failure_stops_execution(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test batch execution stops on critical failure."""
        # Create critical recommendation that will fail
        critical_rec = Recommendation(
            recommendation_id="critical_001",
            type=RecommendationType.CAMPAIGN_PAUSE,
            priority=RecommendationPriority.CRITICAL,
            title="Critical operation",
            description="Critical operation that will fail",
            customer_id="1234567890",
            campaign_ids=["111"],
            data={},
            dry_run=False,  # Not dry run
        )

        # Create normal recommendation
        normal_rec = Recommendation(
            recommendation_id="normal_001",
            type=RecommendationType.NEGATIVE_KEYWORDS,
            priority=RecommendationPriority.MEDIUM,
            title="Normal operation",
            description="Normal operation",
            customer_id="1234567890",
            campaign_ids=["222"],
            data={"keywords": ["test"]},
            dry_run=False,
        )

        batch = RecommendationBatch(
            batch_id="batch_002",
            name="Test Batch with Critical Failure",
            customer_id="1234567890",
            recommendations=[critical_rec, normal_rec],
            dry_run=False,
        )

        # Mock workflow submission and failure
        mock_workflow_engine.submit_workflow.return_value = "exec_001"
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id="exec_001",
            customer_id="1234567890",
            dry_run=False,
            status=WorkflowStatus.FAILED,
            error_summary="Critical failure",
        )

        with patch.object(
            recommendation_executor,
            "_wait_for_workflow_completion",
            return_value=mock_execution,
        ):
            results = await recommendation_executor.execute_batch(batch)

        # Only one result (critical failed, normal not executed)
        assert len(results) == 1
        assert results[0].success is False

    async def test_create_negative_keywords_workflow(
        self, recommendation_executor, sample_negative_keywords_recommendation
    ):
        """Test creating workflow from negative keywords recommendation."""
        workflow = await recommendation_executor._create_negative_keywords_workflow(
            sample_negative_keywords_recommendation
        )

        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.customer_id == "1234567890"
        assert workflow.dry_run is True
        assert len(workflow.steps) == 2  # Two campaigns
        assert all("Add negative keywords" in step.name for step in workflow.steps)

    async def test_create_budget_workflow(
        self, recommendation_executor, sample_budget_recommendation
    ):
        """Test creating workflow from budget recommendation."""
        workflow = await recommendation_executor._create_budget_workflow(
            sample_budget_recommendation
        )

        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.customer_id == "1234567890"
        assert len(workflow.steps) == 1
        assert "budget" in workflow.steps[0].name.lower()

    async def test_create_campaign_status_workflow(
        self, recommendation_executor, sample_campaign_status_recommendation
    ):
        """Test creating workflow from campaign status recommendation."""
        workflow = await recommendation_executor._create_campaign_status_workflow(
            sample_campaign_status_recommendation, "PAUSED"
        )

        assert isinstance(workflow, WorkflowDefinition)
        assert workflow.customer_id == "1234567890"
        assert len(workflow.steps) == 1
        assert "campaigns" in workflow.steps[0].name.lower()

    async def test_create_workflow_empty_keywords_fails(self, recommendation_executor):
        """Test workflow creation fails with empty keywords."""
        recommendation = Recommendation(
            recommendation_id="rec_fail",
            type=RecommendationType.NEGATIVE_KEYWORDS,
            title="Empty keywords",
            description="Test",
            customer_id="1234567890",
            campaign_ids=["111"],
            data={"keywords": []},  # Empty keywords
        )

        with pytest.raises(RecommendationError, match="No negative keywords provided"):
            await recommendation_executor._create_negative_keywords_workflow(
                recommendation
            )

    async def test_create_workflow_empty_budget_changes_fails(
        self, recommendation_executor
    ):
        """Test workflow creation fails with empty budget changes."""
        recommendation = Recommendation(
            recommendation_id="rec_fail",
            type=RecommendationType.BUDGET_OPTIMIZATION,
            title="Empty budget changes",
            description="Test",
            customer_id="1234567890",
            campaign_ids=["111"],
            data={"budget_changes": []},  # Empty changes
        )

        with pytest.raises(RecommendationError, match="No budget changes provided"):
            await recommendation_executor._create_budget_workflow(recommendation)

    async def test_map_priority_levels(self, recommendation_executor):
        """Test mapping recommendation priorities to workflow priorities."""
        assert (
            recommendation_executor._map_priority(RecommendationPriority.LOW)
            == WorkflowPriority.LOW
        )
        assert (
            recommendation_executor._map_priority(RecommendationPriority.MEDIUM)
            == WorkflowPriority.NORMAL
        )
        assert (
            recommendation_executor._map_priority(RecommendationPriority.HIGH)
            == WorkflowPriority.HIGH
        )
        assert (
            recommendation_executor._map_priority(RecommendationPriority.CRITICAL)
            == WorkflowPriority.CRITICAL
        )

    def test_get_priority_value(self, recommendation_executor):
        """Test getting numeric priority values."""
        assert (
            recommendation_executor._get_priority_value(RecommendationPriority.LOW) == 1
        )
        assert (
            recommendation_executor._get_priority_value(RecommendationPriority.MEDIUM)
            == 2
        )
        assert (
            recommendation_executor._get_priority_value(RecommendationPriority.HIGH)
            == 3
        )
        assert (
            recommendation_executor._get_priority_value(RecommendationPriority.CRITICAL)
            == 4
        )

    async def test_wait_for_workflow_completion_success(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test waiting for workflow completion successfully."""
        execution_id = "exec_001"

        # Mock progression from running to completed
        mock_executions = [
            WorkflowExecution(
                workflow_id="workflow_001",
                execution_id=execution_id,
                customer_id="1234567890",
                dry_run=True,
                status=WorkflowStatus.RUNNING,
            ),
            WorkflowExecution(
                workflow_id="workflow_001",
                execution_id=execution_id,
                customer_id="1234567890",
                dry_run=True,
                status=WorkflowStatus.COMPLETED,
            ),
        ]

        mock_workflow_engine.get_workflow_status.side_effect = mock_executions

        with patch("asyncio.sleep"):  # Speed up polling
            result = await recommendation_executor._wait_for_workflow_completion(
                execution_id, timeout_seconds=10
            )

        assert result is not None
        assert result.status == WorkflowStatus.COMPLETED

    async def test_wait_for_workflow_completion_timeout(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test workflow completion timeout."""
        execution_id = "exec_001"

        # Mock always running (never completes)
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id=execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.RUNNING,
        )

        mock_workflow_engine.get_workflow_status.return_value = mock_execution

        with patch("asyncio.sleep"):  # Speed up polling
            with patch(
                "paidsearchnav.workflows.recommendation_executor.datetime"
            ) as mock_datetime:
                # Mock time progression to trigger timeout
                mock_now = datetime(2023, 1, 1, 12, 0, 0)
                mock_timeout = datetime(2023, 1, 1, 12, 0, 1)  # 1 second later
                mock_datetime.utcnow.side_effect = [
                    mock_now,
                    mock_timeout,
                    mock_timeout,
                ]
                mock_datetime.timedelta = datetime.timedelta

                result = await recommendation_executor._wait_for_workflow_completion(
                    execution_id, timeout_seconds=1
                )

        assert result is None

    def test_get_execution_result(self, recommendation_executor):
        """Test getting execution result."""
        recommendation_id = "rec_001"

        # Initially no result
        result = recommendation_executor.get_execution_result(recommendation_id)
        assert result is None

        # Add result
        execution_result = ExecutionResult(
            recommendation_id=recommendation_id,
            success=True,
        )
        recommendation_executor._execution_results[recommendation_id] = execution_result

        result = recommendation_executor.get_execution_result(recommendation_id)
        assert result == execution_result

    async def test_cancel_recommendation(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test cancelling recommendation."""
        recommendation_id = "rec_001"
        execution_id = "exec_001"

        # Add execution result
        execution_result = ExecutionResult(
            recommendation_id=recommendation_id,
            execution_id=execution_id,
            success=False,  # Still running
        )
        recommendation_executor._execution_results[recommendation_id] = execution_result

        mock_workflow_engine.cancel_workflow.return_value = True

        success = await recommendation_executor.cancel_recommendation(recommendation_id)

        assert success is True
        mock_workflow_engine.cancel_workflow.assert_called_once_with(execution_id)

    async def test_cancel_recommendation_not_found(self, recommendation_executor):
        """Test cancelling non-existent recommendation."""
        success = await recommendation_executor.cancel_recommendation("non_existent")
        assert success is False

    async def test_get_recommendation_status(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test getting recommendation status."""
        recommendation_id = "rec_001"
        execution_id = "exec_001"

        # Add execution result
        execution_result = ExecutionResult(
            recommendation_id=recommendation_id,
            execution_id=execution_id,
            success=True,
            operations_count=5,
            completed_at=datetime.utcnow(),
        )
        recommendation_executor._execution_results[recommendation_id] = execution_result

        # Mock workflow status
        mock_execution = WorkflowExecution(
            workflow_id="workflow_001",
            execution_id=execution_id,
            customer_id="1234567890",
            dry_run=True,
            status=WorkflowStatus.COMPLETED,
            progress_percentage=100.0,
            completed_operations=5,
            failed_operations=0,
        )
        mock_workflow_engine.get_workflow_status.return_value = mock_execution

        status = await recommendation_executor.get_recommendation_status(
            recommendation_id
        )

        assert status is not None
        assert status["recommendation_id"] == recommendation_id
        assert status["success"] is True
        assert status["operations_count"] == 5
        assert status["workflow_status"] == "completed"
        assert status["progress_percentage"] == 100.0

    async def test_get_recommendation_status_not_found(self, recommendation_executor):
        """Test getting status for non-existent recommendation."""
        status = await recommendation_executor.get_recommendation_status("non_existent")
        assert status is None

    async def test_list_pending_recommendations(
        self, recommendation_executor, mock_workflow_engine
    ):
        """Test listing pending recommendations."""
        # Add completed recommendation (should not be listed)
        completed_result = ExecutionResult(
            recommendation_id="rec_completed",
            execution_id="exec_completed",
            success=True,
            completed_at=datetime.utcnow(),
        )
        recommendation_executor._execution_results["rec_completed"] = completed_result

        # Add pending recommendation
        pending_result = ExecutionResult(
            recommendation_id="rec_pending",
            execution_id="exec_pending",
            success=False,  # Still running
        )
        recommendation_executor._execution_results["rec_pending"] = pending_result

        # Mock workflow statuses
        mock_workflow_engine.get_workflow_status.side_effect = [
            WorkflowExecution(
                workflow_id="workflow_pending",
                execution_id="exec_pending",
                customer_id="1234567890",
                dry_run=True,
                status=WorkflowStatus.RUNNING,
            )
        ]

        pending = await recommendation_executor.list_pending_recommendations()

        assert len(pending) == 1
        assert "rec_pending" in pending

    async def test_health_check_success(
        self, recommendation_executor, mock_workflow_engine, mock_write_client
    ):
        """Test successful health check."""
        mock_workflow_engine.health_check.return_value = {"healthy": True}
        mock_write_client.health_check.return_value = {"healthy": True}

        result = await recommendation_executor.health_check()

        assert result["healthy"] is True
        assert "tracked_executions" in result
        assert "workflow_engine" in result
        assert "write_client" in result

    async def test_health_check_failure(
        self, recommendation_executor, mock_workflow_engine, mock_write_client
    ):
        """Test health check failure."""
        mock_workflow_engine.health_check.side_effect = Exception("Health check failed")

        result = await recommendation_executor.health_check()

        assert result["healthy"] is False
        assert "error" in result


class TestRecommendationModels:
    """Test recommendation data models."""

    def test_recommendation_creation(self):
        """Test Recommendation model creation."""
        recommendation = Recommendation(
            recommendation_id="rec_001",
            type=RecommendationType.NEGATIVE_KEYWORDS,
            priority=RecommendationPriority.HIGH,
            title="Test Recommendation",
            description="Test description",
            customer_id="1234567890",
            campaign_ids=["111", "222"],
            ad_group_ids=["333", "444"],
            data={"keywords": ["test"]},
            metadata={"source": "analyzer"},
            auto_approve=True,
            dry_run=False,
            rollback_window_hours=48,
        )

        assert recommendation.recommendation_id == "rec_001"
        assert recommendation.type == RecommendationType.NEGATIVE_KEYWORDS
        assert recommendation.priority == RecommendationPriority.HIGH
        assert recommendation.title == "Test Recommendation"
        assert recommendation.description == "Test description"
        assert recommendation.customer_id == "1234567890"
        assert recommendation.campaign_ids == ["111", "222"]
        assert recommendation.ad_group_ids == ["333", "444"]
        assert recommendation.data == {"keywords": ["test"]}
        assert recommendation.metadata == {"source": "analyzer"}
        assert recommendation.auto_approve is True
        assert recommendation.dry_run is False
        assert recommendation.rollback_window_hours == 48

    def test_recommendation_batch_creation(self):
        """Test RecommendationBatch model creation."""
        recommendation = Recommendation(
            recommendation_id="rec_001",
            type=RecommendationType.NEGATIVE_KEYWORDS,
            title="Test",
            description="Test",
            customer_id="1234567890",
            data={"keywords": ["test"]},
        )

        batch = RecommendationBatch(
            batch_id="batch_001",
            name="Test Batch",
            customer_id="1234567890",
            recommendations=[recommendation],
            dry_run=False,
            auto_rollback=True,
            priority=WorkflowPriority.HIGH,
        )

        assert batch.batch_id == "batch_001"
        assert batch.name == "Test Batch"
        assert batch.customer_id == "1234567890"
        assert len(batch.recommendations) == 1
        assert batch.dry_run is False
        assert batch.auto_rollback is True
        assert batch.priority == WorkflowPriority.HIGH

    def test_execution_result_creation(self):
        """Test ExecutionResult model creation."""
        result = ExecutionResult(
            recommendation_id="rec_001",
            workflow_id="workflow_001",
            execution_id="exec_001",
            success=True,
            operations_count=5,
            completed_at=datetime.utcnow(),
        )

        assert result.recommendation_id == "rec_001"
        assert result.workflow_id == "workflow_001"
        assert result.execution_id == "exec_001"
        assert result.success is True
        assert result.operations_count == 5
        assert result.completed_at is not None
        assert result.error_message is None
