"""Tests for Performance Max monitoring scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.performance_max_monitoring import (
    PerformanceMaxAssetOptimizationScript,
    PerformanceMaxMonitoringScript,
)


class TestPerformanceMaxMonitoringScript:
    """Test cases for PerformanceMaxMonitoringScript."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        client = Mock(spec=GoogleAdsClient)
        return client

    @pytest.fixture
    def config(self):
        """Create a script configuration."""
        return ScriptConfig(
            name="test_pmax_monitoring",
            type=ScriptType.PERFORMANCE_MAX_MONITORING,
            description="Test Performance Max monitoring script",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "min_spend": 50.0,
                "target_roas_threshold": 3.0,
                "include_asset_data": True,
                "include_geographic_data": True,
                "locations_of_interest": ["Dallas", "San Antonio", "Atlanta"],
            },
        )

    @pytest.fixture
    def script(self, mock_client, config):
        """Create a PerformanceMaxMonitoringScript instance."""
        return PerformanceMaxMonitoringScript(mock_client, config)

    def test_initialization(self, script, config):
        """Test script initialization."""
        assert script.config == config
        assert script.script_type == ScriptType.PERFORMANCE_MAX_MONITORING
        assert script.client is not None

    def test_get_required_parameters(self, script):
        """Test required parameters."""
        required = script.get_required_parameters()
        assert "date_range" in required
        assert "customer_id" in required

    def test_generate_script(self, script):
        """Test script code generation."""
        script_code = script.generate_script()

        # Verify script contains expected elements
        assert "Performance Max Campaign Monitoring Script" in script_code
        assert "LAST_30_DAYS" in script_code
        assert "analyzePerformanceMaxCampaigns" in script_code
        assert "analyzeAssetGroupPerformance" in script_code
        assert "analyzeSearchTermInsights" in script_code
        assert "analyzeGeographicPerformance" in script_code
        assert "analyzeBiddingStrategies" in script_code
        assert "generateOptimizationRecommendations" in script_code

        # Verify parameters are included
        assert "50" in script_code  # min_spend
        assert "3.0" in script_code  # target_roas_threshold
        assert "Dallas" in script_code
        assert "San Antonio" in script_code

    def test_script_with_minimal_parameters(self, mock_client):
        """Test script generation with minimal parameters."""
        config = ScriptConfig(
            name="minimal_test",
            type=ScriptType.PERFORMANCE_MAX_MONITORING,
            description="Minimal test",
            parameters={
                "date_range": "LAST_7_DAYS",
                "customer_id": "9876543210",
            },
        )

        script = PerformanceMaxMonitoringScript(mock_client, config)
        script_code = script.generate_script()

        assert "LAST_7_DAYS" in script_code
        # Should use defaults for optional parameters
        assert "50" in script_code  # default min_spend

    def test_process_results_success(self, script):
        """Test successful results processing."""
        results = {
            "success": True,
            "rows_processed": 150,
            "execution_time": 45.2,
            "details": {
                "campaigns_analyzed": 5,
                "asset_groups_analyzed": 15,
                "search_terms_analyzed": 120,
                "geo_locations_analyzed": 8,
                "recommendations_generated": 12,
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 150
        assert script_result["execution_time"] == 45.2
        assert script_result["changes_made"] == 0  # Read-only script
        assert len(script_result["errors"]) == 0
        assert script_result["details"]["campaigns_analyzed"] == 5
        assert script_result["details"]["recommendations_generated"] == 12

    def test_process_results_failure(self, script):
        """Test failed results processing."""
        results = {
            "success": False,
            "rows_processed": 0,
            "execution_time": 5.1,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.FAILED.value
        assert script_result["rows_processed"] == 0
        assert len(script_result["errors"]) == 1
        assert "Script execution failed" in script_result["errors"][0]

    def test_process_results_no_data(self, script):
        """Test results processing with no data found."""
        results = {
            "success": True,
            "rows_processed": 0,
            "execution_time": 15.3,
            "details": {},
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert len(script_result["warnings"]) == 1
        assert "No Performance Max campaigns found" in script_result["warnings"][0]

    def test_validate_parameters_success(self, script):
        """Test successful parameter validation."""
        assert script.validate_parameters() is True

    def test_validate_parameters_missing(self, mock_client):
        """Test parameter validation with missing required parameters."""
        config = ScriptConfig(
            name="invalid_test",
            type=ScriptType.PERFORMANCE_MAX_MONITORING,
            description="Invalid test",
            parameters={"date_range": "LAST_30_DAYS"},  # Missing customer_id
        )

        script = PerformanceMaxMonitoringScript(mock_client, config)
        assert script.validate_parameters() is False

    def test_get_script_metadata(self, script):
        """Test script metadata generation."""
        metadata = script.get_script_metadata()

        assert metadata["name"] == "test_pmax_monitoring"
        assert metadata["type"] == "performance_max_monitoring"
        assert metadata["description"] == "Test Performance Max monitoring script"
        assert "parameters" in metadata
        assert "created_at" in metadata


class TestPerformanceMaxAssetOptimizationScript:
    """Test cases for PerformanceMaxAssetOptimizationScript."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def config(self):
        """Create a script configuration."""
        return ScriptConfig(
            name="test_asset_optimization",
            type=ScriptType.PERFORMANCE_MAX_ASSETS,
            description="Test asset optimization script",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "min_impressions": 100,
                "zombie_threshold_days": 30,
                "asset_strength_threshold": "GOOD",
            },
        )

    @pytest.fixture
    def script(self, mock_client, config):
        """Create a PerformanceMaxAssetOptimizationScript instance."""
        return PerformanceMaxAssetOptimizationScript(mock_client, config)

    def test_initialization(self, script, config):
        """Test script initialization."""
        assert script.config == config
        assert script.script_type == ScriptType.PERFORMANCE_MAX_ASSETS

    def test_generate_script(self, script):
        """Test script code generation."""
        script_code = script.generate_script()

        # Verify script contains expected elements
        assert "Performance Max Asset Optimization Script" in script_code
        assert "analyzeAssetPerformance" in script_code
        assert "identifyZombieAssets" in script_code
        assert "identifyTopPerformingAssets" in script_code
        assert "analyzeAssetCombinations" in script_code
        assert "generateAssetRecommendations" in script_code

        # Verify parameters
        assert "100" in script_code  # min_impressions
        assert "30" in script_code  # zombie_threshold_days
        assert "GOOD" in script_code  # asset_strength_threshold

    def test_process_results_success(self, script):
        """Test successful asset optimization results processing."""
        results = {
            "success": True,
            "rows_processed": 85,
            "execution_time": 32.1,
            "details": {
                "assets_analyzed": 45,
                "zombie_assets_found": 8,
                "top_performers_identified": 12,
                "asset_combinations_analyzed": 15,
                "recommendations_generated": 6,
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["details"]["assets_analyzed"] == 45
        assert script_result["details"]["zombie_assets_found"] == 8
        assert script_result["details"]["top_performers_identified"] == 12

    def test_process_results_no_assets(self, script):
        """Test results processing when no assets found."""
        results = {
            "success": True,
            "rows_processed": 0,
            "execution_time": 5.2,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert len(script_result["warnings"]) == 1
        assert "No asset data found" in script_result["warnings"][0]

    def test_asset_optimization_with_custom_parameters(self, mock_client):
        """Test asset optimization with custom parameters."""
        config = ScriptConfig(
            name="custom_asset_test",
            type=ScriptType.PERFORMANCE_MAX_ASSETS,
            description="Custom asset test",
            parameters={
                "date_range": "LAST_14_DAYS",
                "customer_id": "5555555555",
                "min_impressions": 50,
                "zombie_threshold_days": 45,
                "asset_strength_threshold": "EXCELLENT",
            },
        )

        script = PerformanceMaxAssetOptimizationScript(mock_client, config)
        script_code = script.generate_script()

        assert "LAST_14_DAYS" in script_code
        assert "50" in script_code  # min_impressions
        assert "45" in script_code  # zombie_threshold_days
        assert "EXCELLENT" in script_code


@pytest.mark.integration
class TestPerformanceMaxScriptIntegration:
    """Integration tests for Performance Max scripts."""

    def test_monitoring_and_asset_scripts_compatibility(self):
        """Test that monitoring and asset scripts can work together."""
        mock_client = Mock(spec=GoogleAdsClient)

        monitoring_config = ScriptConfig(
            name="monitoring",
            type=ScriptType.PERFORMANCE_MAX_MONITORING,
            description="Monitoring test",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1111111111",
            },
        )

        asset_config = ScriptConfig(
            name="assets",
            type=ScriptType.PERFORMANCE_MAX_ASSETS,
            description="Assets test",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1111111111",
            },
        )

        monitoring_script = PerformanceMaxMonitoringScript(
            mock_client, monitoring_config
        )
        asset_script = PerformanceMaxAssetOptimizationScript(mock_client, asset_config)

        # Both scripts should generate valid code
        monitoring_code = monitoring_script.generate_script()
        asset_code = asset_script.generate_script()

        assert len(monitoring_code) > 1000
        assert len(asset_code) > 1000

        # Both should have the same date_range
        assert "LAST_30_DAYS" in monitoring_code
        assert "LAST_30_DAYS" in asset_code

    def test_script_parameter_inheritance(self):
        """Test that scripts inherit parameters correctly."""
        base_params = {
            "date_range": "LAST_60_DAYS",
            "customer_id": "2222222222",
        }

        mock_client = Mock(spec=GoogleAdsClient)

        # Create multiple scripts with same base parameters
        scripts = []
        script_types = [
            (ScriptType.PERFORMANCE_MAX_MONITORING, PerformanceMaxMonitoringScript),
            (ScriptType.PERFORMANCE_MAX_ASSETS, PerformanceMaxAssetOptimizationScript),
        ]

        for script_type, script_class in script_types:
            config = ScriptConfig(
                name=f"test_{script_type.value}",
                type=script_type,
                description=f"Test {script_type.value}",
                parameters=base_params.copy(),
            )
            scripts.append(script_class(mock_client, config))

        # All scripts should have the same base parameters
        for script in scripts:
            assert script.config.parameters["date_range"] == "LAST_60_DAYS"
            assert script.config.parameters["customer_id"] == "2222222222"
            script_code = script.generate_script()
            assert "LAST_60_DAYS" in script_code
