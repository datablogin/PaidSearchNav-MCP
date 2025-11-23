"""Tests for conflict detection scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.conflict_detection import (
    ConflictDetectionScript,
    ConflictType,
    KeywordConflict,
)


class TestConflictDetectionScript:
    """Test ConflictDetectionScript functionality."""

    @pytest.fixture
    def client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def config(self):
        """Create a conflict detection script config."""
        return ScriptConfig(
            name="Conflict Detection",
            type=ScriptType.CONFLICT_DETECTION,
            description="Test conflict detection",
            parameters={
                "check_campaign_level": True,
                "check_adgroup_level": True,
                "check_list_level": True,
            },
        )

    def test_initialization(self, client, config):
        """Test script initialization."""
        script = ConflictDetectionScript(client, config)

        assert script.client == client
        assert script.config == config
        assert script.template_manager is not None

    def test_get_required_parameters(self, client, config):
        """Test getting required parameters."""
        script = ConflictDetectionScript(client, config)
        required = script.get_required_parameters()

        # No required parameters for conflict detection
        assert required == []

    def test_generate_script_with_template(self, client, config):
        """Test generating script with template."""
        script = ConflictDetectionScript(client, config)

        # Mock template manager to return template
        template = Mock()
        template.render.return_value = "// Template rendered code"
        script.template_manager.get_template = Mock(return_value=template)

        generated_code = script.generate_script()

        assert generated_code == "// Template rendered code"
        template.render.assert_called_once_with(
            {
                "check_campaign_level": True,
                "check_adgroup_level": True,
            }
        )

    def test_generate_enhanced_script(self, client, config):
        """Test generating enhanced conflict detection script."""
        script = ConflictDetectionScript(client, config)

        # Mock template manager to return None (use enhanced script)
        script.template_manager.get_template = Mock(return_value=None)

        generated_code = script.generate_script()

        assert "function main()" in generated_code
        assert "var checkCampaignLevel = true" in generated_code
        assert "var checkAdGroupLevel = true" in generated_code
        assert "var checkListLevel = true" in generated_code
        assert "function checkConflict" in generated_code
        assert "function calculateImpactScore" in generated_code
        assert "function generateSummary" in generated_code

    def test_process_results_success(self, client, config):
        """Test processing successful conflict detection results."""
        script = ConflictDetectionScript(client, config)

        results = {
            "success": True,
            "keywordsChecked": 500,
            "conflictsFound": 10,
            "conflicts": [
                {
                    "keyword": "buy shoes",
                    "negativeKeyword": "shoes",
                    "campaign": "Campaign 1",
                    "adGroup": "Ad Group 1",
                    "type": "campaign",
                    "conflictType": "phrase_match",
                    "impactScore": 0.8,
                }
            ]
            * 10,
            "summary": {
                "byType": {"phrase_match": 8, "exact_match": 2},
                "byLevel": {"campaign": 6, "adgroup": 4},
                "topConflicts": [],
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 500
        assert script_result["changes_made"] == 0
        assert script_result["errors"] == []
        assert len(script_result["warnings"]) == 1
        assert "10 high-impact conflicts" in script_result["warnings"][0]
        assert script_result["details"]["keywords_checked"] == 500
        assert script_result["details"]["conflicts_found"] == 10

    def test_process_results_no_high_impact_conflicts(self, client, config):
        """Test processing results with no high-impact conflicts."""
        script = ConflictDetectionScript(client, config)

        results = {
            "success": True,
            "keywordsChecked": 100,
            "conflictsFound": 5,
            "conflicts": [
                {
                    "keyword": "test",
                    "negativeKeyword": "testing",
                    "campaign": "Campaign 1",
                    "adGroup": "Ad Group 1",
                    "type": "campaign",
                    "conflictType": "broad_match",
                    "impactScore": 0.5,
                }
            ]
            * 5,
            "summary": {
                "byType": {"broad_match": 5},
                "byLevel": {"campaign": 5},
                "topConflicts": [],
            },
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["warnings"] == []  # No high-impact conflicts

    def test_process_results_failure(self, client, config):
        """Test processing failed results."""
        script = ConflictDetectionScript(client, config)

        results = {
            "success": False,
            "errors": ["Script execution timeout"],
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.FAILED.value
        assert script_result["rows_processed"] == 0
        assert script_result["changes_made"] == 0
        assert "Script execution timeout" in script_result["errors"]

    def test_analyze_conflicts(self, client, config):
        """Test analyzing conflicts."""
        script = ConflictDetectionScript(client, config)

        # Currently returns empty list (placeholder)
        conflicts = script.analyze_conflicts(["campaign_1", "campaign_2"])
        assert conflicts == []

    def test_suggest_resolutions(self, client, config):
        """Test suggesting conflict resolutions."""
        script = ConflictDetectionScript(client, config)

        conflicts = [
            KeywordConflict(
                positive_keyword="buy red shoes",
                negative_keyword="shoes",
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 1",
                conflict_type=ConflictType.PHRASE_MATCH,
                negative_level="campaign",
                impact_score=0.95,
                resolution_suggestion="",
            ),
            KeywordConflict(
                positive_keyword="cheap flights",
                negative_keyword="cheap",
                campaign_name="Campaign 2",
                ad_group_name="Ad Group 2",
                conflict_type=ConflictType.BROAD_MATCH,
                negative_level="adgroup",
                impact_score=0.75,
                resolution_suggestion="",
            ),
            KeywordConflict(
                positive_keyword="free trial",
                negative_keyword="free",
                campaign_name="Campaign 3",
                ad_group_name="Ad Group 3",
                conflict_type=ConflictType.EXACT_MATCH,
                negative_level="campaign",
                impact_score=0.6,
                resolution_suggestion="",
            ),
            KeywordConflict(
                positive_keyword="test keyword",
                negative_keyword="test",
                campaign_name="Campaign 4",
                ad_group_name="Ad Group 4",
                conflict_type=ConflictType.CONTAINS,
                negative_level="list",
                impact_score=0.3,
                resolution_suggestion="",
            ),
        ]

        resolutions = script.suggest_resolutions(conflicts)

        assert len(resolutions["remove_negatives"]) == 1  # High impact
        assert len(resolutions["modify_negatives"]) == 1  # Medium impact
        assert len(resolutions["modify_positives"]) == 1  # Low impact
        assert len(resolutions["no_action_needed"]) == 1  # Very low impact

        # Check resolution reasons
        assert "High-impact conflict" in resolutions["remove_negatives"][0]["reason"]
        assert "exact match" in resolutions["modify_negatives"][0]["suggestion"]

    def test_export_conflicts_report_csv(self, client, config):
        """Test exporting conflicts report in CSV format."""
        script = ConflictDetectionScript(client, config)

        conflicts = [
            KeywordConflict(
                positive_keyword="buy shoes",
                negative_keyword="shoes",
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 1",
                conflict_type=ConflictType.PHRASE_MATCH,
                negative_level="campaign",
                impact_score=0.85,
                resolution_suggestion="Remove negative keyword",
            ),
        ]

        csv_report = script.export_conflicts_report(conflicts, format="csv")

        lines = csv_report.split("\n")
        assert len(lines) == 2  # Header + 1 data row
        assert "Campaign,Ad Group,Positive Keyword,Negative Keyword" in lines[0]
        assert '"Campaign 1","Ad Group 1","buy shoes","shoes"' in lines[1]
        assert "phrase_match" in lines[1]
        assert "0.85" in lines[1]

    def test_export_conflicts_report_unsupported_format(self, client, config):
        """Test exporting conflicts report with unsupported format."""
        script = ConflictDetectionScript(client, config)

        with pytest.raises(ValueError, match="Unsupported format"):
            script.export_conflicts_report([], format="xml")


class TestKeywordConflict:
    """Test KeywordConflict dataclass."""

    def test_conflict_creation(self):
        """Test creating a keyword conflict."""
        conflict = KeywordConflict(
            positive_keyword="buy red shoes online",
            negative_keyword="shoes",
            campaign_name="Footwear Campaign",
            ad_group_name="Running Shoes",
            conflict_type=ConflictType.PHRASE_MATCH,
            negative_level="campaign",
            impact_score=0.9,
            resolution_suggestion="Consider using exact match negative",
        )

        assert conflict.positive_keyword == "buy red shoes online"
        assert conflict.negative_keyword == "shoes"
        assert conflict.campaign_name == "Footwear Campaign"
        assert conflict.ad_group_name == "Running Shoes"
        assert conflict.conflict_type == ConflictType.PHRASE_MATCH
        assert conflict.negative_level == "campaign"
        assert conflict.impact_score == 0.9
        assert conflict.resolution_suggestion == "Consider using exact match negative"


class TestConflictType:
    """Test ConflictType enum."""

    def test_conflict_type_values(self):
        """Test ConflictType enum values."""
        assert ConflictType.EXACT_MATCH.value == "exact_match"
        assert ConflictType.PHRASE_MATCH.value == "phrase_match"
        assert ConflictType.BROAD_MATCH.value == "broad_match"
        assert ConflictType.CONTAINS.value == "contains"
