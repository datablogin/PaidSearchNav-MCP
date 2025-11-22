"""Tests for hybrid quarterly data extraction script."""

from unittest.mock import Mock, patch

import pytest

# Mock the circuit breaker import to avoid dependency issues
with patch.dict("sys.modules", {"circuitbreaker": Mock()}):
    from paidsearchnav.core.config import BigQueryConfig, BigQueryTier, Settings
    from paidsearchnav.platforms.google.client import GoogleAdsClient
    from paidsearchnav.platforms.google.scripts.base import (
        ScriptConfig,
        ScriptStatus,
        ScriptType,
    )
    from paidsearchnav.platforms.google.scripts.hybrid_quarterly_extraction import (
        HybridQuarterlyDataExtractionScript,
    )


class TestHybridQuarterlyDataExtractionScript:
    """Test hybrid quarterly data extraction script."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def base_config(self):
        """Create a base script configuration."""
        return ScriptConfig(
            name="test_hybrid_extraction",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test hybrid extraction",
            enabled=True,
            parameters={"customer_id": "1234567890", "date_range": "LAST_30_DAYS"},
        )

    @pytest.fixture
    def settings_with_bigquery(self):
        """Create settings with BigQuery enabled."""
        bigquery_config = BigQueryConfig(
            enabled=True,
            tier=BigQueryTier.PREMIUM,
            project_id="test-project",
            dataset_id="test_dataset",
        )

        settings = Mock(spec=Settings)
        settings.bigquery = bigquery_config
        return settings

    @pytest.fixture
    def settings_without_bigquery(self):
        """Create settings without BigQuery."""
        bigquery_config = BigQueryConfig(enabled=False)

        settings = Mock(spec=Settings)
        settings.bigquery = bigquery_config
        return settings

    def test_initialization(self, mock_client, base_config):
        """Test script initialization."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        assert script.client == mock_client
        assert script.config == base_config
        assert script.script_type == ScriptType.NEGATIVE_KEYWORD
        assert script.settings is None
        assert script.hybrid_export_manager is not None

    def test_initialization_with_settings(
        self, mock_client, base_config, settings_with_bigquery
    ):
        """Test script initialization with settings."""
        script = HybridQuarterlyDataExtractionScript(
            mock_client, base_config, settings_with_bigquery
        )

        assert script.settings == settings_with_bigquery

    def test_get_required_parameters(self, mock_client, base_config):
        """Test getting required parameters."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        required_params = script.get_required_parameters()
        assert "date_range" in required_params
        assert "customer_id" in required_params

    def test_validate_parameters_success(self, mock_client, base_config):
        """Test successful parameter validation."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        assert script.validate_parameters() is True

    def test_validate_parameters_missing_required(self, mock_client):
        """Test parameter validation with missing required parameters."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            enabled=True,
            parameters={"customer_id": "1234567890"},  # Missing date_range
        )

        script = HybridQuarterlyDataExtractionScript(mock_client, config)

        assert script.validate_parameters() is False

    def test_validate_parameters_invalid_customer_id(self, mock_client):
        """Test parameter validation with invalid customer ID."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            enabled=True,
            parameters={"customer_id": "invalid_id", "date_range": "LAST_30_DAYS"},
        )

        script = HybridQuarterlyDataExtractionScript(mock_client, config)

        assert script.validate_parameters() is False

    def test_validate_customer_id_valid(self, mock_client, base_config):
        """Test customer ID validation with valid IDs."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        # Valid formats
        assert script._validate_customer_id("1234567890") is True
        assert script._validate_customer_id("123-456-7890") is True

    def test_validate_customer_id_invalid(self, mock_client, base_config):
        """Test customer ID validation with invalid IDs."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        # Invalid formats
        assert script._validate_customer_id("123") is False
        assert script._validate_customer_id("12345678901") is False  # Too long
        assert script._validate_customer_id("123abc7890") is False  # Contains letters
        assert script._validate_customer_id("") is False
        assert script._validate_customer_id(None) is False

    def test_generate_script_basic(self, mock_client, base_config):
        """Test basic script generation."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        generated_script = script.generate_script()

        assert "function main()" in generated_script
        assert "1234567890" in generated_script  # Customer ID
        assert "LAST_30_DAYS" in generated_script  # Date range
        assert "Enhanced Quarterly Data Extraction Script" in generated_script

    def test_generate_script_with_bigquery_settings(
        self, mock_client, base_config, settings_with_bigquery
    ):
        """Test script generation with BigQuery settings."""
        script = HybridQuarterlyDataExtractionScript(
            mock_client, base_config, settings_with_bigquery
        )

        generated_script = script.generate_script()

        assert "premium" in generated_script.lower()  # Customer tier
        assert "bigquery" in generated_script.lower()

    def test_generate_script_with_custom_parameters(
        self, mock_client, settings_with_bigquery
    ):
        """Test script generation with custom parameters."""
        config = ScriptConfig(
            name="test_script",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            enabled=True,
            parameters={
                "customer_id": "0987654321",  # Enterprise tier
                "date_range": "LAST_90_DAYS",
                "output_mode": "both",
                "include_bigquery": True,
            },
        )

        script = HybridQuarterlyDataExtractionScript(
            mock_client, config, settings_with_bigquery
        )

        generated_script = script.generate_script()

        assert "0987654321" in generated_script
        assert "LAST_90_DAYS" in generated_script
        assert "both" in generated_script
        assert "enterprise" in generated_script.lower()

    @pytest.mark.asyncio
    async def test_process_results_success(self, mock_client, base_config):
        """Test processing successful extraction results."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": True,
            "rows_processed": 1000,
            "changes_made": 50,
            "extraction_results": {
                "search_terms": {"success": True, "rows_processed": 500},
                "keywords": {"success": True, "rows_processed": 300},
                "geographic": {"success": True, "rows_processed": 200},
            },
            "export_results": [
                {"success": True, "destination": "csv", "records_exported": 1000},
                {"success": True, "destination": "bigquery", "records_exported": 1000},
            ],
            "customer_id": "1234567890",
            "customer_tier": "premium",
            "output_mode": "both",
            "date_range": "LAST_30_DAYS",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.COMPLETED.value
        assert script_result.rows_processed == 1000
        assert script_result.changes_made == 50
        assert len(script_result.errors) == 0
        assert script_result.details["script_type"] == "hybrid_quarterly_extraction"
        assert script_result.details["customer_id"] == "1234567890"
        assert script_result.details["successful_exports"] == 2
        assert script_result.details["failed_exports"] == 0

    @pytest.mark.asyncio
    async def test_process_results_with_extraction_warnings(
        self, mock_client, base_config
    ):
        """Test processing results with some extraction failures."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": True,
            "rows_processed": 800,
            "changes_made": 30,
            "extraction_results": {
                "search_terms": {"success": True, "rows_processed": 500},
                "keywords": {"success": False, "error": "API quota exceeded"},
                "geographic": {"success": True, "rows_processed": 300},
            },
            "export_results": [
                {"success": True, "destination": "csv", "records_exported": 800}
            ],
            "customer_id": "1234567890",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.COMPLETED.value
        assert len(script_result.warnings) == 1
        assert "keywords extraction failed" in script_result.warnings[0]

    @pytest.mark.asyncio
    async def test_process_results_all_exports_failed(self, mock_client, base_config):
        """Test processing results when all exports fail."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": True,
            "rows_processed": 1000,
            "extraction_results": {},
            "export_results": [
                {"success": False, "error": "CSV export failed"},
                {"success": False, "error": "BigQuery export failed"},
            ],
            "customer_id": "1234567890",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.FAILED.value
        assert "All exports failed" in script_result.errors[0]

    @pytest.mark.asyncio
    async def test_process_results_partial_export_failure(
        self, mock_client, base_config
    ):
        """Test processing results with partial export failure."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": True,
            "rows_processed": 1000,
            "extraction_results": {},
            "export_results": [
                {"success": True, "destination": "csv", "records_exported": 1000},
                {
                    "success": False,
                    "destination": "bigquery",
                    "error": "BigQuery connection failed",
                },
            ],
            "customer_id": "1234567890",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.COMPLETED_WITH_WARNINGS.value
        assert len(script_result.warnings) == 1
        assert "Export failed" in script_result.warnings[0]
        assert script_result.details["successful_exports"] == 1
        assert script_result.details["failed_exports"] == 1

    @pytest.mark.asyncio
    async def test_process_results_extraction_error(self, mock_client, base_config):
        """Test processing results when extraction itself fails."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": False,
            "error": "Authentication failed",
            "error_type": "AUTH_ERROR",
            "rows_processed": 0,
            "customer_id": "1234567890",
            "date_range": "LAST_30_DAYS",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.FAILED.value
        assert "Authentication error" in script_result.errors[0]
        assert "Check Google Ads API credentials" in script_result.warnings[0]
        assert script_result.details["error_type"] == "AUTH_ERROR"

    @pytest.mark.asyncio
    async def test_process_results_quota_exceeded(self, mock_client, base_config):
        """Test processing results when quota is exceeded."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": False,
            "error": "API quota exceeded",
            "error_type": "QUOTA_EXCEEDED",
            "rows_processed": 500,
            "customer_id": "1234567890",
        }

        script_result = await script.process_results(results)

        assert script_result.status == ScriptStatus.FAILED.value
        assert "Google Ads API quota exceeded" in script_result.errors[0]
        assert "Consider reducing date range" in script_result.warnings[0]

    def test_create_error_result_general_error(self, mock_client, base_config):
        """Test creating error result for general errors."""
        script = HybridQuarterlyDataExtractionScript(mock_client, base_config)

        results = {
            "success": False,
            "error": "Unknown error occurred",
            "error_type": "GENERAL_ERROR",
            "rows_processed": 100,
        }

        error_result = script._create_error_result(results)

        assert error_result.status == ScriptStatus.FAILED.value
        assert "Unknown error occurred" in error_result.errors[0]
        assert error_result.rows_processed == 100
