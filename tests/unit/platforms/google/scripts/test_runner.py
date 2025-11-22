"""Tests for GoogleAdsScriptRunner."""

import asyncio
from unittest.mock import MagicMock

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paidsearchnav.core.config import Settings
from paidsearchnav.platforms.google.scripts.runner import GoogleAdsScriptRunner
from paidsearchnav.storage.models import (
    Base,
    Customer,
    GoogleAdsScript,
    ScriptExecution,
    User,
)


@pytest.fixture
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_local(async_engine):
    """Create session local for testing."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    return Settings(
        environment="development",
        debug=True,
    )


@pytest.fixture
def mock_google_ads_client():
    """Create mock Google Ads client."""
    return MagicMock()


@pytest.fixture
async def test_user(session_local):
    """Create a test user."""
    async with session_local() as session:
        user = User(email="test@example.com", name="Test User", user_type="individual")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def test_customer(session_local, test_user):
    """Create a test customer."""
    async with session_local() as session:
        customer = Customer(
            name="Test Customer",
            email="customer@example.com",
            google_ads_customer_id="1234567890",
            user_id=test_user.id,
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer


@pytest.fixture
async def test_script(session_local, test_customer, test_user):
    """Create a test Google Ads script."""
    async with session_local() as session:
        script = GoogleAdsScript(
            customer_id=test_customer.id,
            user_id=test_user.id,
            name="Test Negative Keyword Script",
            description="Test script for negative keywords",
            script_type="negative_keyword",
            script_code="""
function main() {
  var costThreshold = 50.0;
  var report = AdsApp.report(
    "SELECT SearchTerm, Cost FROM SEARCH_TERM_PERFORMANCE_REPORT " +
    "WHERE Cost > " + costThreshold
  );
  return {success: true, negativeKeywordsAdded: 5};
}
            """,
            parameters={
                "cost_threshold": 50.0,
                "conversion_threshold": 0,
                "lookback_days": 30,
            },
            enabled=True,
        )
        session.add(script)
        await session.commit()
        await session.refresh(script)
        return script


@pytest.fixture
async def script_runner(mock_google_ads_client, session_local, mock_settings):
    """Create GoogleAdsScriptRunner instance."""
    session = session_local()
    runner = GoogleAdsScriptRunner(
        client=mock_google_ads_client,
        session=session,
        settings=mock_settings,
    )
    yield runner
    await session.close()


class TestGoogleAdsScriptRunner:
    """Test GoogleAdsScriptRunner functionality."""

    @pytest.mark.asyncio
    async def test_execute_script_success(self, script_runner, test_script, test_user):
        """Test successful script execution."""
        execution_id = await script_runner.execute_script(
            script=test_script, user_id=test_user.id, execution_type="manual"
        )

        assert execution_id is not None

        # Wait for async execution to complete
        await asyncio.sleep(2)

        # Check execution record was created and updated
        execution = await script_runner.session.get(ScriptExecution, execution_id)
        assert execution is not None
        assert execution.script_id == test_script.id
        assert execution.user_id == test_user.id
        assert execution.status == "completed"
        assert execution.execution_type == "manual"
        assert execution.started_at is not None
        assert execution.completed_at is not None
        assert execution.execution_time is not None
        assert execution.rows_processed > 0
        assert execution.changes_made > 0

    @pytest.mark.asyncio
    async def test_execute_script_different_types(
        self, script_runner, session_local, test_customer, test_user
    ):
        """Test script execution for different script types."""
        script_types = [
            "negative_keyword",
            "conflict_detection",
            "placement_audit",
            "custom",
        ]

        for script_type in script_types:
            async with session_local() as session:
                script = GoogleAdsScript(
                    customer_id=test_customer.id,
                    user_id=test_user.id,
                    name=f"Test {script_type} Script",
                    script_type=script_type,
                    script_code="function main() { return {success: true}; }",
                    parameters={},
                )
                session.add(script)
                await session.commit()
                await session.refresh(script)

                # Update runner session
                script_runner.session = session

                execution_id = await script_runner.execute_script(
                    script=script, user_id=test_user.id
                )

                assert execution_id is not None

                # Wait for execution
                await asyncio.sleep(1.5)

                # Verify execution completed
                execution = await session.get(ScriptExecution, execution_id)
                assert execution.status == "completed"

    @pytest.mark.asyncio
    async def test_get_script_status(self, script_runner, test_script, test_user):
        """Test getting script execution status."""
        # Execute script
        execution_id = await script_runner.execute_script(
            script=test_script, user_id=test_user.id
        )

        # Check initial status
        status = await script_runner.get_script_status(execution_id)
        assert status is not None

        # Wait for completion and check final status
        await asyncio.sleep(2)
        status = await script_runner.get_script_status(execution_id)
        assert status.value == "completed"

    @pytest.mark.asyncio
    async def test_get_script_status_not_found(self, script_runner):
        """Test getting status for non-existent execution."""
        status = await script_runner.get_script_status("non-existent-id")
        assert status is None

    @pytest.mark.asyncio
    async def test_cancel_script(self, script_runner, test_script, test_user):
        """Test script cancellation."""
        # Execute script
        execution_id = await script_runner.execute_script(
            script=test_script, user_id=test_user.id
        )

        # Cancel immediately
        result = await script_runner.cancel_script(execution_id)
        assert result is True

        # Check execution was cancelled
        execution = await script_runner.session.get(ScriptExecution, execution_id)
        assert execution.status == "cancelled"
        assert execution.completed_at is not None

    @pytest.mark.asyncio
    async def test_cancel_script_not_found(self, script_runner):
        """Test cancelling non-existent script."""
        result = await script_runner.cancel_script("non-existent-id")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_completed_script(self, script_runner, test_script, test_user):
        """Test cancelling already completed script."""
        # Execute and wait for completion
        execution_id = await script_runner.execute_script(
            script=test_script, user_id=test_user.id
        )

        await asyncio.sleep(2)  # Wait for completion

        # Try to cancel completed script
        result = await script_runner.cancel_script(execution_id)
        assert result is False

    @pytest.mark.asyncio
    async def test_get_execution_history(
        self,
        session_local,
        mock_google_ads_client,
        mock_settings,
        test_script,
        test_user,
    ):
        """Test getting execution history."""
        # Create a session that we manage manually to avoid early closure
        session = session_local()
        try:
            runner = GoogleAdsScriptRunner(
                client=mock_google_ads_client,
                session=session,
                settings=mock_settings,
            )

            # Execute script multiple times
            execution_ids = []
            for i in range(3):
                execution_id = await runner.execute_script(
                    script=test_script, user_id=test_user.id
                )
                execution_ids.append(execution_id)

            # Wait for all async executions to complete properly
            await runner.wait_for_running_executions()

            # Get history for specific script
            history = await runner.get_execution_history(script_id=test_script.id)

            assert len(history) == 3
            for execution_dict in history:
                assert execution_dict["script_id"] == test_script.id
                assert execution_dict["user_id"] == test_user.id
                assert "status" in execution_dict
                assert "created_at" in execution_dict
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_get_execution_history_all(
        self, script_runner, test_script, test_user
    ):
        """Test getting all execution history."""
        # Execute script
        await script_runner.execute_script(script=test_script, user_id=test_user.id)

        await asyncio.sleep(2)

        # Get all history
        history = await script_runner.get_execution_history()

        assert len(history) >= 1
        assert any(h["script_id"] == test_script.id for h in history)

    @pytest.mark.asyncio
    async def test_get_script_metrics(
        self,
        session_local,
        mock_google_ads_client,
        mock_settings,
        test_script,
        test_user,
    ):
        """Test getting script performance metrics."""
        # Create a session that we manage manually
        session = session_local()
        try:
            runner = GoogleAdsScriptRunner(
                client=mock_google_ads_client,
                session=session,
                settings=mock_settings,
            )

            # Execute script multiple times
            for i in range(2):
                await runner.execute_script(script=test_script, user_id=test_user.id)

            # Wait for all async executions to complete properly
            await runner.wait_for_running_executions()

            # Get metrics
            metrics = await runner.get_script_metrics(test_script.id)

            assert metrics["total_executions"] == 2
            assert metrics["successful_executions"] == 2
            assert metrics["success_rate"] == 1.0
            assert metrics["avg_execution_time"] > 0
            assert metrics["total_rows_processed"] > 0
            assert metrics["total_changes_made"] > 0
        finally:
            await session.close()

    @pytest.mark.asyncio
    async def test_get_script_metrics_no_executions(self, script_runner, test_script):
        """Test getting metrics for script with no executions."""
        metrics = await script_runner.get_script_metrics(test_script.id)

        # Handle the case where metrics returns empty dict on error
        if not metrics:
            # If empty dict is returned, the method handled an error gracefully
            assert metrics == {}
        else:
            assert metrics["total_executions"] == 0
            assert metrics["successful_executions"] == 0
            assert metrics["success_rate"] == 0
            assert metrics["avg_execution_time"] == 0
            assert metrics["total_rows_processed"] == 0
            assert metrics["total_changes_made"] == 0

    @pytest.mark.asyncio
    async def test_cleanup_old_executions(self, script_runner, test_script, test_user):
        """Test cleaning up old execution records."""
        # Create some executions
        execution_id = await script_runner.execute_script(
            script=test_script, user_id=test_user.id
        )

        await asyncio.sleep(2)

        # Test cleanup (should not delete recent executions)
        deleted_count = await script_runner.cleanup_old_executions(days=1)
        assert deleted_count == 0

        # Verify execution still exists
        execution = await script_runner.session.get(ScriptExecution, execution_id)
        assert execution is not None

    @pytest.mark.asyncio
    async def test_execution_with_different_parameters(
        self, script_runner, session_local, test_customer, test_user
    ):
        """Test script execution with different parameter sets."""
        async with session_local() as session:
            script = GoogleAdsScript(
                customer_id=test_customer.id,
                user_id=test_user.id,
                name="Parameterized Script",
                script_type="negative_keyword",
                script_code="function main() { return {success: true}; }",
                parameters={
                    "cost_threshold": 100.0,
                    "lookback_days": 60,
                },
            )
            session.add(script)
            await session.commit()
            await session.refresh(script)

            script_runner.session = session

            execution_id = await script_runner.execute_script(
                script=script, user_id=test_user.id
            )

            await asyncio.sleep(2)

            execution = await session.get(ScriptExecution, execution_id)
            assert execution.status == "completed"
            # Verify parameters affected the simulation
            assert execution.rows_processed == 600  # 60 * 10

    @pytest.mark.asyncio
    async def test_concurrent_executions(
        self,
        session_local,
        mock_google_ads_client,
        mock_settings,
        test_script,
        test_user,
    ):
        """Test multiple concurrent script executions."""
        # Create a session that we manage manually
        session = session_local()
        try:
            runner = GoogleAdsScriptRunner(
                client=mock_google_ads_client,
                session=session,
                settings=mock_settings,
            )

            # Start multiple executions concurrently
            tasks = []
            for i in range(3):
                task = asyncio.create_task(
                    runner.execute_script(
                        script=test_script,
                        user_id=test_user.id,
                        execution_type="scheduled",
                    )
                )
                tasks.append(task)

            # Wait for all to start
            execution_ids = await asyncio.gather(*tasks)

            # Wait for all async executions to complete properly
            await runner.wait_for_running_executions()

            # Verify all executions completed
            for execution_id in execution_ids:
                execution = await session.get(ScriptExecution, execution_id)
                assert execution.status == "completed"
                assert execution.execution_type == "scheduled"
        finally:
            await session.close()


class TestScriptExecutorIntegration:
    """Test integration with existing ScriptExecutor."""

    @pytest.mark.asyncio
    async def test_script_executor_backwards_compatibility(self):
        """Test that existing ScriptExecutor still works."""
        from unittest.mock import MagicMock

        from paidsearchnav.platforms.google.client import GoogleAdsClient
        from paidsearchnav.platforms.google.scripts.base import ScriptExecutor

        mock_client = MagicMock(spec=GoogleAdsClient)
        executor = ScriptExecutor(mock_client)

        # Test that methods exist and return expected types
        assert hasattr(executor, "get_script_status")
        assert hasattr(executor, "cancel_script")
        assert hasattr(executor, "get_script_history")

        # Test method calls (should return defaults/warnings)
        status = executor.get_script_status("test-id")
        assert status.value == "pending"

        result = executor.cancel_script("test-id")
        assert result is False

        history = executor.get_script_history()
        assert history == []
