"""Tests for Performance Max geographic and bidding optimization scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.performance_max_geographic import (
    PerformanceMaxBiddingOptimizationScript,
    PerformanceMaxGeographicScript,
)


class TestPerformanceMaxGeographicScript:
    """Test cases for PerformanceMaxGeographicScript."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def config(self):
        """Create a script configuration."""
        return ScriptConfig(
            name="test_pmax_geographic",
            type=ScriptType.PERFORMANCE_MAX_GEOGRAPHIC,
            description="Test Performance Max geographic script",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "target_locations": [
                    {"name": "Dallas", "state": "Texas", "criterion_id": "1026201"},
                    {
                        "name": "San Antonio",
                        "state": "Texas",
                        "criterion_id": "1026216",
                    },
                    {"name": "Atlanta", "state": "Georgia", "criterion_id": "1015254"},
                ],
                "radius_analysis": True,
                "store_locations": [
                    {
                        "id": "store_001",
                        "name": "Dallas Red Bird",
                        "address": "3662 W Camp Wisdom Rd, Dallas, TX 75237",
                        "city": "Dallas",
                        "state": "Texas",
                        "latitude": 32.6899,
                        "longitude": -96.8890,
                        "type": "fitness_center",
                    }
                ],
                "local_intent_indicators": [
                    "near me",
                    "nearby",
                    "gym near",
                    "fitness near",
                ],
            },
        )

    @pytest.fixture
    def script(self, mock_client, config):
        """Create a PerformanceMaxGeographicScript instance."""
        return PerformanceMaxGeographicScript(mock_client, config)

    def test_initialization(self, script, config):
        """Test script initialization."""
        assert script.config == config
        assert script.script_type == ScriptType.PERFORMANCE_MAX_GEOGRAPHIC

    def test_get_required_parameters(self, script):
        """Test required parameters."""
        required = script.get_required_parameters()
        assert "date_range" in required
        assert "customer_id" in required

    def test_generate_script(self, script):
        """Test script code generation."""
        script_code = script.generate_script()

        # Verify script contains expected elements
        assert "Performance Max Geographic Performance Analysis Script" in script_code
        assert "analyzeGeographicPerformance" in script_code
        assert "analyzeRadiusPerformance" in script_code
        assert "analyzeStorePerformance" in script_code
        assert "analyzeLocalIntentTerms" in script_code
        assert "analyzeCompetitivePerformance" in script_code
        assert "generateGeographicRecommendations" in script_code

        # Verify parameters are included
        assert "Dallas" in script_code
        assert "San Antonio" in script_code
        assert "Atlanta" in script_code
        assert "Texas" in script_code
        assert "Georgia" in script_code
        assert "near me" in script_code
        assert "gym near" in script_code

    def test_generate_script_with_minimal_parameters(self, mock_client):
        """Test script generation with minimal parameters."""
        config = ScriptConfig(
            name="minimal_geo_test",
            type=ScriptType.PERFORMANCE_MAX_GEOGRAPHIC,
            description="Minimal geo test",
            parameters={
                "date_range": "LAST_7_DAYS",
                "customer_id": "9876543210",
            },
        )

        script = PerformanceMaxGeographicScript(mock_client, config)
        script_code = script.generate_script()

        assert "LAST_7_DAYS" in script_code
        # Should contain default locations
        assert "Dallas" in script_code  # From default target_locations

    def test_process_results_success(self, script):
        """Test successful results processing."""
        results = {
            "success": True,
            "rows_processed": 200,
            "execution_time": 38.5,
            "details": {
                "locations_analyzed": 12,
                "stores_analyzed": 3,
                "local_intent_terms": 45,
                "competitive_locations": 8,
                "radius_analysis_performed": True,
                "recommendations_generated": 7,
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 200
        assert script_result["execution_time"] == 38.5
        assert script_result["details"]["locations_analyzed"] == 12
        assert script_result["details"]["radius_analysis_performed"] is True

    def test_process_results_no_geographic_data(self, script):
        """Test results processing when no geographic data found."""
        results = {
            "success": True,
            "rows_processed": 0,
            "execution_time": 8.2,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert len(script_result["warnings"]) == 1
        assert "No geographic performance data found" in script_result["warnings"][0]

    def test_script_with_no_store_locations(self, mock_client):
        """Test script with no store locations configured."""
        config = ScriptConfig(
            name="no_stores_test",
            type=ScriptType.PERFORMANCE_MAX_GEOGRAPHIC,
            description="No stores test",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1111111111",
                "store_locations": [],
                "radius_analysis": False,
            },
        )

        script = PerformanceMaxGeographicScript(mock_client, config)
        script_code = script.generate_script()

        # Should still work without store locations
        assert "analyzeGeographicPerformance" in script_code
        assert "false" in script_code.lower()  # radius_analysis = false

    def test_validate_parameters(self, script):
        """Test parameter validation."""
        assert script.validate_parameters() is True


class TestPerformanceMaxBiddingOptimizationScript:
    """Test cases for PerformanceMaxBiddingOptimizationScript."""

    @pytest.fixture
    def mock_client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def config(self):
        """Create a script configuration."""
        return ScriptConfig(
            name="test_pmax_bidding",
            type=ScriptType.PERFORMANCE_MAX_BIDDING,
            description="Test Performance Max bidding script",
            parameters={
                "date_range": "LAST_30_DAYS",
                "customer_id": "1234567890",
                "target_roas_threshold": 3.0,
                "target_cpa_threshold": 50.0,
                "min_conversions_for_analysis": 5,
                "performance_lookback_days": 30,
            },
        )

    @pytest.fixture
    def script(self, mock_client, config):
        """Create a PerformanceMaxBiddingOptimizationScript instance."""
        return PerformanceMaxBiddingOptimizationScript(mock_client, config)

    def test_initialization(self, script, config):
        """Test script initialization."""
        assert script.config == config
        assert script.script_type == ScriptType.PERFORMANCE_MAX_BIDDING

    def test_generate_script(self, script):
        """Test script code generation."""
        script_code = script.generate_script()

        # Verify script contains expected elements
        assert "Performance Max Bidding Strategy Optimization Script" in script_code
        assert "analyzeBiddingStrategyPerformance" in script_code
        assert "analyzeCampaignBidding" in script_code
        assert "analyzeTargetVsActual" in script_code
        assert "identifyOptimizationOpportunities" in script_code
        assert "extractSmartBiddingInsights" in script_code
        assert "generateBiddingRecommendations" in script_code

        # Verify parameters
        assert "3.0" in script_code  # target_roas_threshold
        assert "50.0" in script_code  # target_cpa_threshold
        assert "5" in script_code  # min_conversions_for_analysis
        assert "30" in script_code  # performance_lookback_days

    def test_generate_script_with_custom_thresholds(self, mock_client):
        """Test script with custom bidding thresholds."""
        config = ScriptConfig(
            name="custom_bidding_test",
            type=ScriptType.PERFORMANCE_MAX_BIDDING,
            description="Custom bidding test",
            parameters={
                "date_range": "LAST_14_DAYS",
                "customer_id": "5555555555",
                "target_roas_threshold": 4.5,
                "target_cpa_threshold": 25.0,
                "min_conversions_for_analysis": 10,
                "performance_lookback_days": 60,
            },
        )

        script = PerformanceMaxBiddingOptimizationScript(mock_client, config)
        script_code = script.generate_script()

        assert "4.5" in script_code  # custom target_roas_threshold
        assert "25.0" in script_code  # custom target_cpa_threshold
        assert "10" in script_code  # custom min_conversions
        assert "60" in script_code  # custom lookback_days

    def test_process_results_success(self, script):
        """Test successful bidding optimization results processing."""
        results = {
            "success": True,
            "rows_processed": 75,
            "execution_time": 42.8,
            "details": {
                "strategies_analyzed": 8,
                "campaigns_analyzed": 15,
                "optimization_opportunities": 12,
                "smart_bidding_insights": {
                    "strategy_distribution": {"TARGET_ROAS": 5, "TARGET_CPA": 3},
                    "avg_performance": {"roas": 3.2, "cpa": 45.5},
                },
                "recommendations_generated": 9,
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["details"]["strategies_analyzed"] == 8
        assert script_result["details"]["campaigns_analyzed"] == 15
        assert script_result["details"]["optimization_opportunities"] == 12
        assert (
            "strategy_distribution"
            in script_result["details"]["smart_bidding_insights"]
        )

    def test_process_results_no_bidding_data(self, script):
        """Test results processing when no bidding data found."""
        results = {
            "success": True,
            "rows_processed": 0,
            "execution_time": 12.1,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert len(script_result["warnings"]) == 1
        assert "No bidding strategy data found" in script_result["warnings"][0]

    def test_process_results_failure(self, script):
        """Test failed results processing."""
        results = {
            "success": False,
            "rows_processed": 0,
            "execution_time": 3.5,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.FAILED.value
        assert len(script_result["errors"]) == 1
        assert (
            "Bidding optimization script execution failed" in script_result["errors"][0]
        )


@pytest.mark.integration
class TestGeographicBiddingIntegration:
    """Integration tests for geographic and bidding scripts."""

    def test_geographic_and_bidding_scripts_compatibility(self):
        """Test that geographic and bidding scripts work together."""
        mock_client = Mock(spec=GoogleAdsClient)

        # Common parameters for both scripts
        base_params = {
            "date_range": "LAST_30_DAYS",
            "customer_id": "3333333333",
        }

        geo_config = ScriptConfig(
            name="geo_integration",
            type=ScriptType.PERFORMANCE_MAX_GEOGRAPHIC,
            description="Geographic integration test",
            parameters={
                **base_params,
                "target_locations": [
                    {"name": "Houston", "state": "Texas", "criterion_id": "1026222"}
                ],
            },
        )

        bidding_config = ScriptConfig(
            name="bidding_integration",
            type=ScriptType.PERFORMANCE_MAX_BIDDING,
            description="Bidding integration test",
            parameters={
                **base_params,
                "target_roas_threshold": 2.5,
            },
        )

        geo_script = PerformanceMaxGeographicScript(mock_client, geo_config)
        bidding_script = PerformanceMaxBiddingOptimizationScript(
            mock_client, bidding_config
        )

        # Both scripts should generate valid code
        geo_code = geo_script.generate_script()
        bidding_code = bidding_script.generate_script()

        # Verify both scripts have compatible structure
        assert "function main()" in geo_code
        assert "function main()" in bidding_code
        assert "Logger.log" in geo_code
        assert "Logger.log" in bidding_code

        # Both should use the same date range
        for code in [geo_code, bidding_code]:
            assert "LAST_30_DAYS" in code

    def test_script_result_compatibility(self):
        """Test that results from different scripts have compatible formats."""
        mock_client = Mock(spec=GoogleAdsClient)

        configs = [
            (ScriptType.PERFORMANCE_MAX_GEOGRAPHIC, PerformanceMaxGeographicScript),
            (
                ScriptType.PERFORMANCE_MAX_BIDDING,
                PerformanceMaxBiddingOptimizationScript,
            ),
        ]

        results_template = {
            "success": True,
            "rows_processed": 50,
            "execution_time": 25.0,
            "details": {},
        }

        for script_type, script_class in configs:
            config = ScriptConfig(
                name=f"compatibility_test_{script_type.value}",
                type=script_type,
                description=f"Compatibility test for {script_type.value}",
                parameters={
                    "date_range": "LAST_30_DAYS",
                    "customer_id": "4444444444",
                },
            )

            script = script_class(mock_client, config)
            script_result = script.process_results(results_template.copy())

            # All scripts should have compatible result structure
            assert "status" in script_result
            assert "execution_time" in script_result
            assert "rows_processed" in script_result
            assert "changes_made" in script_result
            assert "errors" in script_result
            assert "warnings" in script_result
            assert "details" in script_result
            assert "script_type" in script_result["details"]
            assert "execution_timestamp" in script_result["details"]
