"""Tests for negative keyword automation scripts."""

from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.platforms.google.client import GoogleAdsClient
from paidsearchnav_mcp.platforms.google.scripts.base import (
    ScriptConfig,
    ScriptStatus,
    ScriptType,
)
from paidsearchnav_mcp.platforms.google.scripts.negative_keywords import (
    NegativeKeywordScript,
    NegativeKeywordSuggestion,
)


class TestNegativeKeywordScript:
    """Test NegativeKeywordScript functionality."""

    @pytest.fixture
    def client(self):
        """Create a mock Google Ads client."""
        return Mock(spec=GoogleAdsClient)

    @pytest.fixture
    def performance_config(self):
        """Create a performance-based script config."""
        return ScriptConfig(
            name="Performance Negative Keywords",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test performance script",
            parameters={
                "subtype": "performance",
                "cost_threshold": 50.0,
                "conversion_threshold": 0,
                "lookback_days": 30,
            },
        )

    @pytest.fixture
    def ngram_config(self):
        """Create an n-gram analysis script config."""
        return ScriptConfig(
            name="N-Gram Analysis",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test n-gram script",
            parameters={
                "subtype": "n_gram",
                "n_gram_length": 2,
                "min_occurrences": 10,
                "min_cost": 100,
            },
        )

    @pytest.fixture
    def master_list_config(self):
        """Create a master list script config."""
        return ScriptConfig(
            name="Master Negative List",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test master list script",
            parameters={
                "subtype": "master_list",
                "list_name": "Test Master List",
                "apply_to_campaigns": ["Campaign 1", "Campaign 2"],
            },
        )

    def test_initialization(self, client, performance_config):
        """Test script initialization."""
        script = NegativeKeywordScript(client, performance_config)

        assert script.client == client
        assert script.config == performance_config
        assert script.template_manager is not None

    def test_get_required_parameters_performance(self, client, performance_config):
        """Test required parameters for performance subtype."""
        script = NegativeKeywordScript(client, performance_config)
        required = script.get_required_parameters()

        assert "cost_threshold" in required
        assert "conversion_threshold" in required

    def test_get_required_parameters_ngram(self, client, ngram_config):
        """Test required parameters for n-gram subtype."""
        script = NegativeKeywordScript(client, ngram_config)
        required = script.get_required_parameters()

        assert "n_gram_length" in required
        assert "min_occurrences" in required

    def test_get_required_parameters_master_list(self, client, master_list_config):
        """Test required parameters for master list subtype."""
        script = NegativeKeywordScript(client, master_list_config)
        required = script.get_required_parameters()

        assert "list_name" in required
        assert "apply_to_campaigns" in required

    def test_generate_performance_script(self, client, performance_config):
        """Test generating performance-based script."""
        script = NegativeKeywordScript(client, performance_config)
        generated_code = script.generate_script()

        assert "function main()" in generated_code
        assert "var costThreshold = 50" in generated_code
        assert "var conversionThreshold = 0" in generated_code
        assert "var lookbackDays = 30" in generated_code
        assert "SEARCH_TERM_PERFORMANCE_REPORT" in generated_code

    def test_generate_ngram_script(self, client, ngram_config):
        """Test generating n-gram analysis script."""
        script = NegativeKeywordScript(client, ngram_config)
        generated_code = script.generate_script()

        assert "function main()" in generated_code
        assert "var nGramLength = 2" in generated_code
        assert "var minOccurrences = 10" in generated_code
        assert "var minCost = 100" in generated_code
        assert "nGramMap" in generated_code

    def test_generate_master_list_script(self, client, master_list_config):
        """Test generating master list script."""
        script = NegativeKeywordScript(client, master_list_config)
        generated_code = script.generate_script()

        assert "function main()" in generated_code
        assert 'var listName = "Test Master List"' in generated_code
        assert '["Campaign 1", "Campaign 2"]' in generated_code
        assert "getNegativeKeywordList" in generated_code

    def test_generate_script_unknown_subtype(self, client):
        """Test generating script with unknown subtype."""
        config = ScriptConfig(
            name="Unknown",
            type=ScriptType.NEGATIVE_KEYWORD,
            description="Test",
            parameters={"subtype": "unknown"},
        )
        script = NegativeKeywordScript(client, config)

        with pytest.raises(ValueError, match="Unknown script subtype"):
            script.generate_script()

    def test_process_performance_results_success(self, client, performance_config):
        """Test processing successful performance script results."""
        script = NegativeKeywordScript(client, performance_config)

        results = {
            "success": True,
            "negativeKeywordsAdded": 15,
            "details": [
                {
                    "keyword": "bad keyword",
                    "campaign": "Campaign 1",
                    "adGroup": "Ad Group 1",
                    "cost": 100.0,
                    "conversions": 0,
                }
            ]
            * 15,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 15
        assert script_result["changes_made"] == 15
        assert script_result["errors"] == []
        assert script_result["details"]["negative_keywords_added"] == 15
        assert script_result["details"]["total_cost_saved"] == 1500.0

    def test_process_ngram_results_success(self, client, ngram_config):
        """Test processing successful n-gram script results."""
        script = NegativeKeywordScript(client, ngram_config)

        results = {
            "success": True,
            "nGramsAnalyzed": 1000,
            "negativeNGramsFound": 25,
            "nGrams": [
                {
                    "nGram": "free download",
                    "occurrences": 50,
                    "cost": 500.0,
                    "conversions": 0,
                }
            ]
            * 25,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 1000
        assert script_result["changes_made"] == 0  # N-gram doesn't make direct changes
        assert script_result["details"]["n_grams_analyzed"] == 1000
        assert script_result["details"]["negative_n_grams_found"] == 25

    def test_process_master_list_results_success(self, client, master_list_config):
        """Test processing successful master list script results."""
        script = NegativeKeywordScript(client, master_list_config)

        results = {
            "success": True,
            "listName": "Test Master List",
            "campaignsUpdated": 5,
            "keywordsInList": 100,
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.COMPLETED.value
        assert script_result["rows_processed"] == 5
        assert script_result["changes_made"] == 5
        assert script_result["details"]["list_name"] == "Test Master List"
        assert script_result["details"]["campaigns_updated"] == 5
        assert script_result["details"]["keywords_in_list"] == 100

    def test_process_results_failure(self, client, performance_config):
        """Test processing failed script results."""
        script = NegativeKeywordScript(client, performance_config)

        results = {
            "success": False,
            "errors": ["API Error: Rate limit exceeded"],
        }

        script_result = script.process_results(results)

        assert script_result["status"] == ScriptStatus.FAILED.value
        assert script_result["rows_processed"] == 0
        assert script_result["changes_made"] == 0
        assert "API Error: Rate limit exceeded" in script_result["errors"]

    def test_analyze_search_terms(self, client, performance_config):
        """Test analyzing search terms."""
        script = NegativeKeywordScript(client, performance_config)

        # Currently returns empty list (placeholder)
        suggestions = script.analyze_search_terms(["campaign_1", "campaign_2"])
        assert suggestions == []

    def test_apply_negative_keywords_auto_apply_disabled(
        self, client, performance_config
    ):
        """Test applying negative keywords with auto-apply disabled."""
        script = NegativeKeywordScript(client, performance_config)

        suggestions = [
            NegativeKeywordSuggestion(
                keyword="test keyword",
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 1",
                cost=100.0,
                conversions=0,
                clicks=50,
                impressions=1000,
                reason="No conversions",
                confidence_score=0.9,
            )
        ]

        result = script.apply_negative_keywords(suggestions, auto_apply=False)

        assert result["applied"] == 0
        assert result["suggestions"] == 1
        assert "Auto-apply disabled" in result["message"]

    def test_apply_negative_keywords_auto_apply_enabled(
        self, client, performance_config
    ):
        """Test applying negative keywords with auto-apply enabled."""
        script = NegativeKeywordScript(client, performance_config)

        suggestions = [
            NegativeKeywordSuggestion(
                keyword=f"keyword {i}",
                campaign_name="Campaign 1",
                ad_group_name="Ad Group 1",
                cost=100.0,
                conversions=0,
                clicks=50,
                impressions=1000,
                reason="No conversions",
                confidence_score=0.9,
            )
            for i in range(5)
        ]

        result = script.apply_negative_keywords(suggestions, auto_apply=True)

        assert result["applied"] == 5
        assert result["suggestions"] == 5
        assert "Applied 5 negative keywords" in result["message"]


class TestNegativeKeywordSuggestion:
    """Test NegativeKeywordSuggestion dataclass."""

    def test_suggestion_creation(self):
        """Test creating a negative keyword suggestion."""
        suggestion = NegativeKeywordSuggestion(
            keyword="free software",
            campaign_name="Main Campaign",
            ad_group_name="Software Ad Group",
            cost=150.0,
            conversions=0,
            clicks=75,
            impressions=2000,
            reason="High cost with no conversions",
            confidence_score=0.95,
        )

        assert suggestion.keyword == "free software"
        assert suggestion.campaign_name == "Main Campaign"
        assert suggestion.ad_group_name == "Software Ad Group"
        assert suggestion.cost == 150.0
        assert suggestion.conversions == 0
        assert suggestion.clicks == 75
        assert suggestion.impressions == 2000
        assert suggestion.reason == "High cost with no conversions"
        assert suggestion.confidence_score == 0.95
