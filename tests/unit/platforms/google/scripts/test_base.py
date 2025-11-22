"""Tests for base Google Ads Scripts functionality."""

from unittest.mock import MagicMock, Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptBase,
    ScriptConfig,
    ScriptExecutor,
    ScriptResult,
    ScriptStatus,
    ScriptType,
)


class MockScript(ScriptBase):
    """Mock script for testing."""

    def generate_script(self) -> str:
        return "function main() { return { success: true }; }"

    def process_results(self, results: dict) -> ScriptResult:
        return ScriptResult(
            status=ScriptStatus.COMPLETED.value,
            execution_time=0.0,
            rows_processed=results.get("rows_processed", 0),
            changes_made=results.get("changes_made", 0),
            errors=[],
            warnings=[],
            details=results,
        )

    def get_required_parameters(self) -> list:
        return ["param1", "param2"]


class TestScriptBase:
    """Test ScriptBase functionality."""

    def test_script_initialization(self):
        """Test script initialization."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            parameters={"param1": "value1", "param2": "value2"},
        )

        script = MockScript(client, config)

        assert script.client == client
        assert script.config == config
        assert script.config.name == "Test Script"
        assert script.config.type == ScriptType.NEGATIVE_KEYWORD

    def test_validate_parameters_success(self):
        """Test successful parameter validation."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            parameters={"param1": "value1", "param2": "value2"},
        )

        script = MockScript(client, config)
        assert script.validate_parameters() is True

    def test_validate_parameters_missing(self):
        """Test parameter validation with missing parameters."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            parameters={"param1": "value1"},  # Missing param2
        )

        script = MockScript(client, config)
        assert script.validate_parameters() is False

    def test_get_script_metadata(self):
        """Test script metadata generation."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.CONFLICT_DETECTION,
            description="Test description",
            parameters={"test": "value"},
        )

        script = MockScript(client, config)
        metadata = script.get_script_metadata()

        assert metadata["name"] == "Test Script"
        assert metadata["type"] == "conflict_detection"
        assert metadata["description"] == "Test description"
        assert metadata["parameters"] == {"test": "value"}
        assert "created_at" in metadata


class TestScriptExecutor:
    """Test ScriptExecutor functionality."""

    @pytest.fixture
    def executor(self):
        """Create a script executor."""
        client = Mock(spec=GoogleAdsClient)
        return ScriptExecutor(client)

    @pytest.fixture
    def mock_script(self):
        """Create a mock script."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            parameters={"param1": "value1", "param2": "value2"},
        )
        return MockScript(client, config)

    def test_register_script(self, executor, mock_script):
        """Test script registration."""
        script_id = executor.register_script(mock_script)

        assert script_id.startswith("negative_keyword_")
        assert script_id in executor._scripts
        assert executor._scripts[script_id] == mock_script

    def test_execute_script_success(self, executor, mock_script):
        """Test successful script execution."""
        script_id = executor.register_script(mock_script)

        # Mock the _execute_ads_script method
        executor._execute_ads_script = MagicMock(
            return_value={
                "success": True,
                "rows_processed": 100,
                "changes_made": 10,
                "details": {"test": "data"},
            }
        )

        result = executor.execute_script(script_id)

        assert result["status"] == ScriptStatus.COMPLETED.value
        assert result["rows_processed"] == 100
        assert result["changes_made"] == 10
        assert result["execution_time"] > 0
        assert result["errors"] == []
        assert result["warnings"] == []

    def test_execute_script_invalid_parameters(self, executor):
        """Test script execution with invalid parameters."""
        client = Mock(spec=GoogleAdsClient)
        config = ScriptConfig(
            name="Test Script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test description",
            parameters={"param1": "value1"},  # Missing param2
        )
        script = MockScript(client, config)
        script_id = executor.register_script(script)

        result = executor.execute_script(script_id)

        assert result["status"] == ScriptStatus.FAILED.value
        assert result["errors"] == ["Invalid parameters"]
        assert result["rows_processed"] == 0
        assert result["changes_made"] == 0

    def test_execute_script_not_found(self, executor):
        """Test executing non-existent script."""
        with pytest.raises(ValueError, match="Script not found"):
            executor.execute_script("non_existent_script")

    def test_execute_script_exception(self, executor, mock_script):
        """Test script execution with exception."""
        script_id = executor.register_script(mock_script)

        # Mock the _execute_ads_script method to raise exception
        executor._execute_ads_script = MagicMock(side_effect=Exception("Test error"))

        result = executor.execute_script(script_id)

        assert result["status"] == ScriptStatus.FAILED.value
        assert "Test error" in result["errors"][0]
        assert result["rows_processed"] == 0
        assert result["changes_made"] == 0

    def test_get_script_status(self, executor):
        """Test getting script status."""
        # Currently returns PENDING for all scripts
        status = executor.get_script_status("any_script_id")
        assert status == ScriptStatus.PENDING

    def test_cancel_script(self, executor):
        """Test canceling a script."""
        # Currently returns False (not implemented)
        result = executor.cancel_script("any_script_id")
        assert result is False

    def test_get_script_history(self, executor):
        """Test getting script history."""
        # Currently returns empty list
        history = executor.get_script_history()
        assert history == []

        # Test with specific type
        history = executor.get_script_history(ScriptType.NEGATIVE_KEYWORD)
        assert history == []


class TestScriptConfig:
    """Test ScriptConfig functionality."""

    def test_config_initialization_minimal(self):
        """Test minimal config initialization."""
        config = ScriptConfig(
            name="Test",
            type=ScriptType.PLACEMENT_AUDIT,
            description="Test description",
        )

        assert config.name == "Test"
        assert config.type == ScriptType.PLACEMENT_AUDIT
        assert config.description == "Test description"
        assert config.schedule is None
        assert config.enabled is True
        assert config.parameters == {}

    def test_config_initialization_full(self):
        """Test full config initialization."""
        config = ScriptConfig(
            name="Test",
            type=ScriptType.CONFLICT_DETECTION,
            description="Test description",
            schedule="0 0 * * *",
            enabled=False,
            parameters={"key": "value"},
        )

        assert config.name == "Test"
        assert config.type == ScriptType.CONFLICT_DETECTION
        assert config.description == "Test description"
        assert config.schedule == "0 0 * * *"
        assert config.enabled is False
        assert config.parameters == {"key": "value"}


class TestScriptEnums:
    """Test script enumerations."""

    def test_script_status_values(self):
        """Test ScriptStatus enum values."""
        assert ScriptStatus.PENDING.value == "pending"
        assert ScriptStatus.RUNNING.value == "running"
        assert ScriptStatus.COMPLETED.value == "completed"
        assert ScriptStatus.FAILED.value == "failed"
        assert ScriptStatus.CANCELLED.value == "cancelled"

    def test_script_type_values(self):
        """Test ScriptType enum values."""
        assert ScriptType.NEGATIVE_KEYWORD.value == "negative_keyword"
        assert ScriptType.CONFLICT_DETECTION.value == "conflict_detection"
        assert ScriptType.PLACEMENT_AUDIT.value == "placement_audit"
        assert ScriptType.MASTER_NEGATIVE_LIST.value == "master_negative_list"
        assert ScriptType.N_GRAM_ANALYSIS.value == "n_gram_analysis"
