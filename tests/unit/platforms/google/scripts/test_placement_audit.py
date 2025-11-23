"""Tests for placement audit scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.placement_audit import (
    PlacementAnalysis,
    PlacementAuditScript,
    PlacementQuality,
)


class TestPlacementAuditScript:
    """Test PlacementAuditScript functionality."""

    @pytest.fixture
    def client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def config(self):
        """Create a placement audit script config."""
        return ScriptConfig(
            name="Placement Audit",
            type=ScriptType.PLACEMENT_AUDIT,
            description="Test placement audit",
            parameters={
                "min_impressions": 100,
                "max_cpa_ratio": 2.0,
                "min_ctr": 0.001,
                "check_character_sets": True,
            },
        )

    def test_initialization(self, client, config):
        """Test script initialization."""
        script = PlacementAuditScript(client, config)

        assert script.client == client
        assert script.config == config
        assert script.template_manager is not None

    def test_get_required_parameters(self, client, config):
        """Test getting required parameters."""
        script = PlacementAuditScript(client, config)
        required = script.get_required_parameters()

        # No required parameters for placement audit
        assert required == []

    def test_generate_script_with_template(self, client, config):
        """Test generating script with template."""
        script = PlacementAuditScript(client, config)

        # Mock template manager to return template
        template = Mock()
        template.render.return_value = "// Template rendered code"
        script.template_manager.get_template = Mock(return_value=template)

        generated_code = script.generate_script()

        assert generated_code == "// Template rendered code"
        template.render.assert_called_once_with(
            {
                "min_impressions": 100,
                "max_cpa_ratio": 2.0,
            }
        )

    def test_generate_advanced_script(self, client, config):
        """Test generating advanced placement audit script."""
        script = PlacementAuditScript(client, config)

        # Mock template manager to return None (use advanced script)
        script.template_manager.get_template = Mock(return_value=None)

        generated_code = script.generate_script()

        assert "function main()" in generated_code
        assert "var minImpressions = 100" in generated_code
        assert "var maxCpaRatio = 2.0" in generated_code
        assert "var minCtr = 0.001" in generated_code
        assert "var checkCharacterSets = true" in generated_code
        assert "function analyzePlacement" in generated_code
        assert "function detectCharacterSets" in generated_code
        assert "function isDomainSuspicious" in generated_code

    def test_process_results_success(self, client, config):
        """Test processing successful placement audit results."""
        script = PlacementAuditScript(client, config)

        results = {
            "success": True,
            "placementsAnalyzed": 250,
            "accountBenchmarks": {
                "ctr": 0.02,
                "cpc": 1.5,
                "cpa": 50.0,
            },
            "categories": {
                "high": [{"domain": "good1.com"}] * 100,
                "medium": [{"domain": "ok1.com"}] * 80,
                "low": [{"domain": "poor1.com"}] * 40,
                "poor": [{"domain": "bad1.com"}] * 20,
                "suspicious": [{"domain": "spam1.com"}] * 10,
            },
            "exclusions": {
                "immediate": [{"domain": "bad.com", "reason": "Poor performance"}] * 30,
                "recommended": [{"domain": "maybe.com", "reason": "Low CTR"}] * 15,
                "totalCostSavings": 5000.0,
            },
            "topIssues": [
                {"issue": "Low CTR", "count": 50},
                {"issue": "High CPC", "count": 30},
            ],
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 250
        assert script_result["changes_made"] == 0
        assert script_result["errors"] == []
        assert len(script_result["warnings"]) == 2
        assert "10 suspicious placements" in script_result["warnings"][0]
        assert (
            "High number of exclusions recommended: 30" in script_result["warnings"][1]
        )

        details = script_result["details"]
        assert details["placements_analyzed"] == 250
        assert details["immediate_exclusions"] == 30
        assert details["recommended_exclusions"] == 15
        assert details["potential_cost_savings"] == 5000.0

    def test_process_results_no_warnings(self, client, config):
        """Test processing results with no warnings."""
        script = PlacementAuditScript(client, config)

        results = {
            "success": True,
            "placementsAnalyzed": 50,
            "accountBenchmarks": {},
            "categories": {
                "high": [],
                "medium": [],
                "low": [],
                "poor": [],
                "suspicious": [],
            },
            "exclusions": {
                "immediate": [],
                "recommended": [],
                "totalCostSavings": 0,
            },
            "topIssues": [],
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["warnings"] == []

    def test_process_results_failure(self, client, config):
        """Test processing failed results."""
        script = PlacementAuditScript(client, config)

        results = {
            "success": False,
            "errors": ["API quota exceeded"],
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.FAILED.value
        assert script_result["rows_processed"] == 0
        assert script_result["changes_made"] == 0
        assert "API quota exceeded" in script_result["errors"]

    def test_analyze_placements(self, client, config):
        """Test analyzing placements."""
        script = PlacementAuditScript(client, config)

        # Currently returns empty list (placeholder)
        analyses = script.analyze_placements(["campaign_1"], lookback_days=30)
        assert analyses == []

    def test_apply_exclusions_dry_run(self, client, config):
        """Test applying exclusions in dry run mode."""
        script = PlacementAuditScript(client, config)

        exclusions = [
            {"domain": "bad1.com", "reason": "Poor performance"},
            {"domain": "bad2.com", "reason": "Low quality"},
        ]

        result = script.apply_exclusions(exclusions, dry_run=True)

        assert result["applied"] == 0
        assert result["exclusions"] == 2
        assert "Dry run mode" in result["message"]
        assert len(result["preview"]) == 2

    def test_apply_exclusions_actual(self, client, config):
        """Test applying exclusions (not dry run)."""
        script = PlacementAuditScript(client, config)

        exclusions = [
            {"domain": f"bad{i}.com", "reason": "Poor performance"} for i in range(5)
        ]

        result = script.apply_exclusions(exclusions, dry_run=False)

        assert result["applied"] == 5
        assert result["exclusions"] == 5
        assert result["errors"] == []
        assert "Applied 5 placement exclusions" in result["message"]

    def test_detect_placement_patterns(self, client, config):
        """Test detecting patterns in placement data."""
        script = PlacementAuditScript(client, config)

        placements = [
            PlacementAnalysis(
                domain="example.com",
                impressions=1000,
                clicks=10,
                cost=50.0,
                conversions=0,
                ctr=0.01,
                cpc=5.0,
                cpa=None,
                quality_score=30,
                quality_level=PlacementQuality.POOR,
                issues=["No conversions"],
                character_sets={"latin"},
                recommendation="Exclude",
            ),
            PlacementAnalysis(
                domain="verylongdomainname12345678901234567890.tk",
                impressions=500,
                clicks=5,
                cost=25.0,
                conversions=0,
                ctr=0.01,
                cpc=5.0,
                cpa=None,
                quality_score=20,
                quality_level=PlacementQuality.POOR,
                issues=["Long domain"],
                character_sets={"latin", "cyrillic"},
                recommendation="Exclude",
            ),
            PlacementAnalysis(
                domain="good-site.org",
                impressions=2000,
                clicks=40,
                cost=60.0,
                conversions=2,
                ctr=0.02,
                cpc=1.5,
                cpa=30.0,
                quality_score=85,
                quality_level=PlacementQuality.HIGH,
                issues=[],
                character_sets={"latin"},
                recommendation="Continue",
            ),
        ]

        patterns = script.detect_placement_patterns(placements)

        assert patterns["tld_distribution"]["com"] == 1
        assert patterns["tld_distribution"]["tk"] == 1
        assert patterns["tld_distribution"]["org"] == 1

        assert patterns["character_set_distribution"]["latin"] == 3
        assert patterns["character_set_distribution"]["cyrillic"] == 1

        assert "Long domain names" in patterns["quality_patterns"]


class TestPlacementAnalysis:
    """Test PlacementAnalysis dataclass."""

    def test_analysis_creation(self):
        """Test creating a placement analysis."""
        analysis = PlacementAnalysis(
            domain="example.com",
            impressions=5000,
            clicks=50,
            cost=100.0,
            conversions=2,
            ctr=0.01,
            cpc=2.0,
            cpa=50.0,
            quality_score=75.0,
            quality_level=PlacementQuality.MEDIUM,
            issues=["High CPC"],
            character_sets={"latin"},
            recommendation="Monitor closely",
        )

        assert analysis.domain == "example.com"
        assert analysis.impressions == 5000
        assert analysis.clicks == 50
        assert analysis.cost == 100.0
        assert analysis.conversions == 2
        assert analysis.ctr == 0.01
        assert analysis.cpc == 2.0
        assert analysis.cpa == 50.0
        assert analysis.quality_score == 75.0
        assert analysis.quality_level == PlacementQuality.MEDIUM
        assert analysis.issues == ["High CPC"]
        assert analysis.character_sets == {"latin"}
        assert analysis.recommendation == "Monitor closely"


class TestPlacementQuality:
    """Test PlacementQuality enum."""

    def test_quality_values(self):
        """Test PlacementQuality enum values."""
        assert PlacementQuality.HIGH.value == "high"
        assert PlacementQuality.MEDIUM.value == "medium"
        assert PlacementQuality.LOW.value == "low"
        assert PlacementQuality.POOR.value == "poor"
        assert PlacementQuality.SUSPICIOUS.value == "suspicious"
