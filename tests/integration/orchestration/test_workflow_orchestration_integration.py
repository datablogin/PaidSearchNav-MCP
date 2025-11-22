"""Integration tests for workflow orchestration system."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock

import pytest

from paidsearchnav.core.config import Settings
from paidsearchnav.orchestration.monitoring import WorkflowMonitor
from paidsearchnav.orchestration.step_executors import StepExecutorRegistry
from paidsearchnav.orchestration.workflow_definitions import WorkflowDefinitionParser
from paidsearchnav.orchestration.workflow_engine import WorkflowOrchestrator
from paidsearchnav.storage.models import (
    WorkflowDefinition,
    WorkflowExecution,
    WorkflowStep,
)


class MockAsyncSession:
    """Mock async database session for testing."""

    def __init__(self):
        self.objects = []
        self.committed = False
        self._queries = []

    def add(self, obj):
        """Add object to session."""
        self.objects.append(obj)

    async def commit(self):
        """Commit transaction."""
        self.committed = True

    async def rollback(self):
        """Rollback transaction."""
        pass

    async def execute(self, query):
        """Mock execute query."""
        self._queries.append(query)
        result_mock = AsyncMock()
        result_mock.scalar_one_or_none.return_value = None
        result_mock.scalar.return_value = "completed"
        result_mock.scalars.return_value.all.return_value = []
        return result_mock

    async def refresh(self, obj):
        """Mock refresh object."""
        pass


class TestWorkflowOrchestrationIntegration:
    """Integration tests for workflow orchestration."""

    def setup_method(self):
        """Set up test fixtures."""
        self.db_session = MockAsyncSession()
        self.settings = Settings()
        self.step_executor_registry = StepExecutorRegistry()
        self.workflow_monitor = WorkflowMonitor()

        self.orchestrator = WorkflowOrchestrator(
            db_session=self.db_session,
            settings=self.settings,
            step_executor_registry=self.step_executor_registry,
            workflow_monitor=self.workflow_monitor,
        )

        # Mock workflow definition
        self.workflow_def = WorkflowDefinition(
            id="test-workflow-def-id",
            name="test_workflow",
            version="1.0",
            definition={
                "name": "test_workflow",
                "version": "1.0",
                "description": "Test workflow",
                "steps": [
                    {
                        "name": "step1",
                        "service": "default",
                        "timeout": 300,
                        "config": {"operation": "noop"},
                    }
                ],
            },
            enabled=True,
        )

    async def test_create_workflow_definition(self):
        """Test creating a workflow definition."""
        definition = {
            "name": "integration_test_workflow",
            "version": "1.0",
            "description": "Integration test workflow",
            "steps": [
                {
                    "name": "test_step",
                    "service": "default",
                    "timeout": 300,
                    "config": {"operation": "noop"},
                }
            ],
        }

        workflow_def = await self.orchestrator.create_workflow_definition(
            name="integration_test_workflow", version="1.0", definition=definition
        )

        assert workflow_def.name == "integration_test_workflow"
        assert workflow_def.version == "1.0"
        assert workflow_def.enabled is True
        assert self.db_session.committed

    async def test_workflow_definition_validation_error(self):
        """Test workflow definition validation with invalid definition."""
        invalid_definition = {
            "name": "",  # Invalid empty name
            "version": "1.0",
            "steps": [],  # Invalid empty steps
        }

        with pytest.raises(ValueError, match="Schema validation error"):
            await self.orchestrator.create_workflow_definition(
                name="invalid_workflow", version="1.0", definition=invalid_definition
            )

    async def test_start_workflow_execution_success(self):
        """Test successful workflow execution start."""

        # Mock the query to return our test workflow definition
        async def mock_execute(query):
            result_mock = AsyncMock()
            result_mock.scalar_one_or_none.return_value = self.workflow_def
            return result_mock

        self.db_session.execute = mock_execute

        execution = await self.orchestrator.start_workflow(
            workflow_name="test_workflow",
            customer_id="test-customer-123",
            context={"test_key": "test_value"},
        )

        assert execution.workflow_definition_id == self.workflow_def.id
        assert execution.customer_id == "test-customer-123"
        assert execution.status == "pending"
        assert execution.context == {"test_key": "test_value"}

        # Check that execution is tracked
        execution_key = "test-customer-123:test_workflow"
        assert execution_key in self.orchestrator._running_executions
        assert execution.id in self.orchestrator._execution_contexts

    async def test_start_workflow_already_running(self):
        """Test starting workflow when already running for customer."""

        # Mock the query to return our test workflow definition
        async def mock_execute(query):
            result_mock = AsyncMock()
            result_mock.scalar_one_or_none.return_value = self.workflow_def
            return result_mock

        self.db_session.execute = mock_execute

        # Start first execution
        await self.orchestrator.start_workflow(
            workflow_name="test_workflow", customer_id="test-customer-123"
        )

        # Try to start second execution for same customer/workflow
        with pytest.raises(ValueError, match="already running"):
            await self.orchestrator.start_workflow(
                workflow_name="test_workflow", customer_id="test-customer-123"
            )

    async def test_start_workflow_not_found(self):
        """Test starting non-existent workflow."""

        # Mock query to return None (workflow not found)
        async def mock_execute(query):
            result_mock = AsyncMock()
            result_mock.scalar_one_or_none.return_value = None
            return result_mock

        self.db_session.execute = mock_execute

        with pytest.raises(ValueError, match="not found or disabled"):
            await self.orchestrator.start_workflow(
                workflow_name="nonexistent_workflow", customer_id="test-customer-123"
            )

    async def test_get_workflow_status(self):
        """Test getting workflow execution status."""
        # Create mock execution and steps
        mock_execution = WorkflowExecution(
            id="test-execution-id",
            workflow_definition_id="test-workflow-def-id",
            customer_id="test-customer-123",
            status="completed",
            current_step=None,
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
        )

        mock_step = WorkflowStep(
            id="test-step-id",
            execution_id="test-execution-id",
            step_name="test_step",
            status="completed",
            started_at=datetime.now(timezone.utc),
            completed_at=datetime.now(timezone.utc),
            retry_count=0,
        )

        # Mock database queries
        async def mock_execute(query):
            result_mock = AsyncMock()
            if "workflow_executions" in str(query):
                result_mock.scalar_one_or_none.return_value = mock_execution
            else:  # workflow_steps query
                result_mock.scalars.return_value.all.return_value = [mock_step]
            return result_mock

        self.db_session.execute = mock_execute

        status = await self.orchestrator.get_workflow_status("test-execution-id")

        assert status["execution_id"] == "test-execution-id"
        assert status["customer_id"] == "test-customer-123"
        assert status["status"] == "completed"
        assert len(status["steps"]) == 1
        assert status["steps"][0]["step_name"] == "test_step"

    async def test_workflow_execution_cleanup_on_completion(self):
        """Test that workflow execution is cleaned up properly on completion."""
        # This test would require more complex mocking of the execution flow
        # For now, we'll test the cleanup methods directly

        execution_id = "test-execution-id"
        customer_id = "test-customer-123"
        workflow_name = "test_workflow"

        # Simulate adding execution context
        execution_key = f"{customer_id}:{workflow_name}"
        self.orchestrator._running_executions[execution_key] = execution_id
        self.orchestrator._execution_contexts[execution_id] = {"test": "data"}
        self.orchestrator._execution_timestamps[execution_id] = datetime.now(
            timezone.utc
        )

        # Test manual cleanup
        await self.orchestrator.cleanup_execution_context(execution_id)

        # Verify cleanup (contexts should be removed but running executions preserved for TTL cleanup)
        assert execution_id not in self.orchestrator._execution_contexts
        assert execution_id not in self.orchestrator._execution_timestamps

    async def test_context_ttl_cleanup(self):
        """Test TTL-based context cleanup."""
        from datetime import timedelta

        execution_id = "expired-execution-id"
        old_timestamp = datetime.now(timezone.utc) - timedelta(
            hours=25
        )  # Older than TTL

        # Add expired context
        self.orchestrator._execution_contexts[execution_id] = {"test": "data"}
        self.orchestrator._execution_timestamps[execution_id] = old_timestamp

        # Run cleanup
        await self.orchestrator._cleanup_expired_contexts()

        # Verify expired context was removed
        assert execution_id not in self.orchestrator._execution_contexts
        assert execution_id not in self.orchestrator._execution_timestamps

    def test_get_context_stats(self):
        """Test getting context statistics."""
        from datetime import timedelta

        # Add some test contexts
        current_time = datetime.now(timezone.utc)
        fresh_time = current_time - timedelta(minutes=30)
        expired_time = current_time - timedelta(hours=25)

        self.orchestrator._execution_contexts["fresh1"] = {}
        self.orchestrator._execution_timestamps["fresh1"] = fresh_time

        self.orchestrator._execution_contexts["expired1"] = {}
        self.orchestrator._execution_timestamps["expired1"] = expired_time

        stats = self.orchestrator.get_context_stats()

        assert stats["total_contexts"] == 2
        assert stats["expired_contexts"] == 1
        assert stats["active_contexts"] == 1
        assert stats["context_ttl_hours"] == 24

    async def test_workflow_definition_parser_integration(self):
        """Test integration between workflow definition parser and orchestrator."""
        yaml_content = """
name: "integration_test"
version: "1.0"
description: "Integration test workflow"

steps:
  - name: "init_step"
    service: "default"
    timeout: 300
    config:
      operation: "noop"
  - name: "process_step"
    service: "default"
    depends_on: ["init_step"]
    timeout: 600
    retry: 2
    config:
      operation: "process"
"""

        parser = WorkflowDefinitionParser()
        parsed_def = parser.parse_yaml(yaml_content)

        assert parsed_def.name == "integration_test"
        assert len(parsed_def.steps) == 2
        assert parsed_def.steps[1].depends_on == ["init_step"]

        # Test execution order calculation
        execution_order = parser.get_execution_order(parsed_def.steps)
        assert len(execution_order) == 2
        assert execution_order[0] == ["init_step"]
        assert execution_order[1] == ["process_step"]

    def test_step_executor_registry_integration(self):
        """Test step executor registry functionality."""
        registry = StepExecutorRegistry()

        # Test that default executors are registered
        assert registry.has_executor("default")
        assert registry.has_executor("customer_init_service")
        assert registry.has_executor("notification_service")

        # Test getting executor
        executor = registry.get_executor("default")
        assert executor is not None

        # Test listing services
        services = registry.list_services()
        assert "default" in services
        assert len(services) > 0

    def test_workflow_monitor_integration(self):
        """Test workflow monitoring integration."""
        monitor = WorkflowMonitor()

        execution_id = "test-execution-id"
        workflow_name = "test_workflow"
        customer_id = "test-customer-123"

        # Start monitoring
        monitor.start_execution(execution_id, workflow_name, customer_id)

        # Check active executions
        active = monitor.get_active_executions()
        assert len(active) == 1
        assert active[0]["execution_id"] == execution_id

        # Update progress
        monitor.update_execution_progress(execution_id, 1, 2)

        # Record step execution
        monitor.record_step_execution(execution_id, "test_step", True)

        # End execution
        monitor.end_execution(execution_id, "completed")

        # Check metrics
        metrics = monitor.get_metrics()
        assert metrics["total_executions"] == 1
        assert metrics["successful_executions"] == 1
        assert metrics["step_execution_counts"]["test_step"] == 1

        # Check recent executions
        recent = monitor.get_recent_executions()
        assert len(recent) == 1
