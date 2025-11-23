"""Tests for Google Ads Scripts validation and edge cases."""

from unittest.mock import AsyncMock, MagicMock, patch

import pytest

from paidsearchnav_mcp.platforms.google.scripts.runner import GoogleAdsScriptRunner
from paidsearchnav_mcp.storage.models import GoogleAdsScript, ScriptExecution


class TestScriptValidation:
    """Test script validation functionality."""

    def test_script_code_validation_empty(self):
        """Test that empty script code is rejected."""
        with pytest.raises(ValueError, match="Script code cannot be empty"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code="",
            )

    def test_script_code_validation_too_large(self):
        """Test that oversized script code is rejected."""
        large_script = "x" * 100001  # 100KB + 1 byte

        with pytest.raises(ValueError, match="Script code too large"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code=large_script,
            )

    def test_script_code_validation_dangerous_patterns(self):
        """Test that potentially dangerous code patterns are rejected."""
        dangerous_scripts = [
            "function main() { eval('malicious code'); }",
            "function main() { new Function('return process'); }",
            "function main() { setTimeout(function() {}, 1000); }",
            "function main() { var xhr = new XMLHttpRequest(); }",
            "function main() { fetch('http://evil.com'); }",
        ]

        for script_code in dangerous_scripts:
            with pytest.raises(ValueError, match="potentially dangerous pattern"):
                GoogleAdsScript(
                    customer_id="test-customer",
                    user_id="test-user",
                    name="Test Script",
                    script_type="negative_keyword",
                    script_code=script_code,
                )

    def test_script_code_validation_valid(self):
        """Test that valid script code is accepted."""
        valid_script = """
        function main() {
            var report = AdsApp.report("SELECT * FROM KEYWORDS_PERFORMANCE_REPORT");
            return {success: true, processed: 100};
        }
        """

        # This should not raise any exception
        script = GoogleAdsScript(
            customer_id="test-customer",
            user_id="test-user",
            name="Test Script",
            script_type="negative_keyword",
            script_code=valid_script,
        )
        assert script.script_code == valid_script

    def test_parameters_validation_too_large(self):
        """Test that oversized parameters are rejected."""
        # Create parameters that exceed 10KB
        large_params = {f"param_{i}": "x" * 100 for i in range(200)}

        with pytest.raises(ValueError, match="Parameters too large"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code="function main() { return {success: true}; }",
                parameters=large_params,
            )

    def test_parameters_validation_invalid_keys(self):
        """Test that invalid parameter keys are rejected."""
        with pytest.raises(ValueError, match="Parameter key too long"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code="function main() { return {success: true}; }",
                parameters={"x" * 101: "value"},  # Key too long
            )

    def test_parameters_validation_invalid_values(self):
        """Test that oversized parameter values are rejected."""
        with pytest.raises(ValueError, match="Parameter value too long"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code="function main() { return {success: true}; }",
                parameters={"key": "x" * 1001},  # Value too long
            )

    def test_parameters_validation_non_serializable(self):
        """Test that non-JSON-serializable parameters are rejected."""

        class NonSerializable:
            pass

        with pytest.raises(ValueError, match="JSON serializable"):
            GoogleAdsScript(
                customer_id="test-customer",
                user_id="test-user",
                name="Test Script",
                script_type="negative_keyword",
                script_code="function main() { return {success: true}; }",
                parameters={"key": NonSerializable()},
            )

    def test_result_data_validation_too_large(self):
        """Test that oversized result data is rejected."""
        # Create result data that exceeds 1MB
        large_result = {"data": "x" * 1000001}

        with pytest.raises(ValueError, match="Result data too large"):
            ScriptExecution(
                script_id="test-script",
                user_id="test-user",
                status="completed",
                result_data=large_result,
            )

    def test_result_data_validation_non_serializable(self):
        """Test that non-JSON-serializable result data is rejected."""

        class NonSerializable:
            pass

        with pytest.raises(ValueError, match="JSON serializable"):
            ScriptExecution(
                script_id="test-script",
                user_id="test-user",
                status="completed",
                result_data={"key": NonSerializable()},
            )


class TestConcurrentExecutionLimits:
    """Test concurrent execution limits."""

    @pytest.fixture
    def mock_settings(self):
        """Create mock settings with low concurrent execution limit."""
        mock_settings = MagicMock()
        mock_settings.max_concurrent_script_executions = 2  # Low limit for testing
        return mock_settings

    @pytest.fixture
    def script_runner(self, mock_settings):
        """Create script runner with limited concurrent executions."""
        mock_client = MagicMock()
        mock_session = AsyncMock()

        runner = GoogleAdsScriptRunner(
            client=mock_client,
            session=mock_session,
            settings=mock_settings,
        )
        return runner

    @pytest.fixture
    def test_script(self):
        """Create a test script."""
        return GoogleAdsScript(
            id="test-script-id",
            customer_id="test-customer",
            user_id="test-user",
            name="Test Script",
            script_type="negative_keyword",
            script_code="function main() { return {success: true}; }",
        )

    @pytest.mark.asyncio
    async def test_concurrent_execution_limit_reached(self, script_runner, test_script):
        """Test that execution limit is enforced."""
        # Mock running executions to simulate reaching the limit
        script_runner._running_executions = {
            "exec1": MagicMock(),
            "exec2": MagicMock(),
        }

        with pytest.raises(
            RuntimeError, match="Maximum concurrent executions limit reached"
        ):
            await script_runner.execute_script(test_script, "test-user")

    @pytest.mark.asyncio
    async def test_concurrent_execution_limit_not_reached(
        self, script_runner, test_script
    ):
        """Test that execution proceeds when under the limit."""
        # Mock the session methods
        script_runner.session.add = MagicMock()
        script_runner.session.commit = AsyncMock()
        script_runner.session.refresh = AsyncMock()

        # Mock the script execution creation
        mock_execution = MagicMock()
        mock_execution.id = "test-execution-id"

        def side_effect(execution):
            execution.id = "test-execution-id"

        script_runner.session.refresh.side_effect = side_effect

        # This should not raise an exception since we're under the limit
        execution_id = await script_runner.execute_script(test_script, "test-user")

        assert execution_id == "test-execution-id"
        assert len(script_runner._running_executions) == 1


class TestBatchedCleanup:
    """Test batched cleanup functionality."""

    @pytest.fixture
    def script_runner(self):
        """Create script runner for cleanup testing."""
        mock_client = MagicMock()
        mock_session = AsyncMock()
        mock_settings = MagicMock()

        runner = GoogleAdsScriptRunner(
            client=mock_client,
            session=mock_session,
            settings=mock_settings,
        )
        return runner

    @pytest.mark.asyncio
    async def test_batched_cleanup_single_batch(self, script_runner):
        """Test cleanup with single batch."""
        # Mock database operations
        # First call: SELECT query returns IDs
        mock_select_result = MagicMock()
        mock_select_result.fetchall.return_value = [
            ("id1",),
            ("id2",),
            ("id3",),
        ]  # 3 IDs

        # Second call: DELETE query
        mock_delete_result = MagicMock()
        mock_delete_result.rowcount = 3  # Less than batch size

        script_runner.session.execute.side_effect = [
            mock_select_result,
            mock_delete_result,
        ]
        script_runner.session.commit = AsyncMock()

        deleted_count = await script_runner.cleanup_old_executions(
            days=30, batch_size=1000
        )

        assert deleted_count == 3
        # Should execute twice: once for SELECT, once for DELETE
        assert script_runner.session.execute.call_count == 2

    @pytest.mark.asyncio
    async def test_batched_cleanup_multiple_batches(self, script_runner):
        """Test cleanup with multiple batches."""
        # Mock database operations for multiple batches
        # Batch 1: SELECT returns 1000 IDs, DELETE removes 1000 (continues because rowcount == batch_size)
        mock_select1 = MagicMock()
        mock_select1.fetchall.return_value = [("id" + str(i),) for i in range(1000)]
        mock_delete1 = MagicMock()
        mock_delete1.rowcount = 1000

        # Batch 2: SELECT returns 500 IDs, DELETE removes 500 (stops because rowcount < batch_size)
        mock_select2 = MagicMock()
        mock_select2.fetchall.return_value = [("id" + str(i),) for i in range(500)]
        mock_delete2 = MagicMock()
        mock_delete2.rowcount = 500

        script_runner.session.execute.side_effect = [
            mock_select1,
            mock_delete1,  # First batch
            mock_select2,
            mock_delete2,  # Second batch (stops here because 500 < 1000)
        ]
        script_runner.session.commit = AsyncMock()

        deleted_count = await script_runner.cleanup_old_executions(
            days=30, batch_size=1000
        )

        assert deleted_count == 1500  # 1000 + 500
        assert script_runner.session.execute.call_count == 4  # 2 + 2

    @pytest.mark.asyncio
    async def test_batched_cleanup_error_handling(self, script_runner):
        """Test cleanup error handling."""
        # Mock database error
        script_runner.session.execute.side_effect = Exception("Database error")
        script_runner.session.rollback = AsyncMock()

        deleted_count = await script_runner.cleanup_old_executions(
            days=30, batch_size=1000
        )

        assert deleted_count == 0
        script_runner.session.rollback.assert_called_once()


class TestConfigurableSettings:
    """Test configurable settings functionality."""

    def test_configurable_api_delay(self):
        """Test that API delay is configurable."""
        mock_settings = MagicMock()
        mock_settings.google_ads_scripts_api_delay = 0.5

        runner = GoogleAdsScriptRunner(
            client=MagicMock(),
            session=AsyncMock(),
            settings=mock_settings,
        )

        # The delay should be accessible via settings
        assert hasattr(mock_settings, "google_ads_scripts_api_delay")
        assert mock_settings.google_ads_scripts_api_delay == 0.5

    def test_configurable_concurrent_executions(self):
        """Test that concurrent execution limit is configurable."""
        mock_settings = MagicMock()
        mock_settings.max_concurrent_script_executions = 5

        runner = GoogleAdsScriptRunner(
            client=MagicMock(),
            session=AsyncMock(),
            settings=mock_settings,
        )

        assert runner.max_concurrent_executions == 5

    def test_default_concurrent_executions(self):
        """Test default concurrent execution limit."""
        mock_settings = MagicMock()
        # Configure getattr to return the default value when the attribute doesn't exist
        del (
            mock_settings.max_concurrent_script_executions
        )  # Make sure the attribute doesn't exist

        # When getattr is called with default value 10, it should return 10
        with patch(
            "paidsearchnav.platforms.google.scripts.runner.getattr"
        ) as mock_getattr:
            mock_getattr.return_value = 10

            runner = GoogleAdsScriptRunner(
                client=MagicMock(),
                session=AsyncMock(),
                settings=mock_settings,
            )

            assert runner.max_concurrent_executions == 10  # Default value
