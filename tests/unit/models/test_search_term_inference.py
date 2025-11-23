"""Unit tests for SearchTerm model smart field inference and validation."""

import pandas as pd
import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.models.search_term import SearchTerm, SearchTermMetrics


class TestSearchTermSmartDefaults:
    """Test suite for SearchTerm model smart defaults and validation."""

    def test_create_search_term_with_all_fields(self):
        """Test creating SearchTerm with all required fields present."""
        search_term = SearchTerm(
            search_term="cotton patch cafe",
            campaign_name="Restaurant Campaign",
            ad_group_name="Main Ad Group",
            metrics=SearchTermMetrics(impressions=100, clicks=10, cost=50.0),
        )

        assert search_term.search_term == "cotton patch cafe"
        assert search_term.campaign_name == "Restaurant Campaign"
        assert search_term.ad_group_name == "Main Ad Group"
        assert search_term.metrics.impressions == 100

    def test_create_search_term_missing_ad_group_name(self):
        """Test creating SearchTerm with missing ad_group_name - should infer from campaign."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Restaurant Campaign",
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.search_term == "cotton patch cafe"
        assert search_term.campaign_name == "Restaurant Campaign"
        assert search_term.ad_group_name == "Restaurant Campaign - Default Ad Group"

    def test_create_search_term_missing_campaign_name(self):
        """Test creating SearchTerm with missing campaign_name - should infer from search term."""
        data = {
            "search_term": "cotton patch cafe near me",
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.search_term == "cotton patch cafe near me"
        assert search_term.campaign_name == "Inferred Campaign - cotton patch cafe ne"
        assert search_term.ad_group_name == "Inferred - cotton patch cafe near me"

    def test_create_search_term_missing_both_names(self):
        """Test creating SearchTerm with both names missing - should use defaults."""
        data = {
            "search_term": "cotton patch cafe",
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.search_term == "cotton patch cafe"
        # Campaign name should be inferred from search term
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe" == search_term.ad_group_name

    def test_create_search_term_with_na_values(self):
        """Test creating SearchTerm with pandas NA values."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": pd.NA,
            "ad_group_name": pd.NA,
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.search_term == "cotton patch cafe"
        # Should infer both fields
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe" == search_term.ad_group_name

    def test_create_search_term_long_search_term(self):
        """Test inference with very long search terms."""
        long_term = "cotton patch cafe restaurant with the best chicken fried steak and sides in all of texas"
        data = {
            "search_term": long_term,
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.search_term == long_term
        # Should truncate for inferred names using constants
        # MAX_CAMPAIGN_NAME_LENGTH=20, MAX_AD_GROUP_NAME_LENGTH=30
        assert len(search_term.campaign_name) <= 41  # "Inferred Campaign - " + 20 chars
        assert len(search_term.ad_group_name) <= 41  # "Inferred - " + 30 chars
        assert "cotton patch cafe restaurant" in search_term.ad_group_name

    def test_create_search_term_preserve_existing_values(self):
        """Test that existing non-empty values are preserved."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Existing Campaign",
            "ad_group_name": "Existing Ad Group",
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        assert search_term.campaign_name == "Existing Campaign"
        assert search_term.ad_group_name == "Existing Ad Group"

    def test_create_search_term_empty_string_values(self):
        """Test that empty string values trigger inference."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "",
            "ad_group_name": "",
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        # Empty strings should trigger inference
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe" == search_term.ad_group_name

    def test_create_search_term_none_values(self):
        """Test that None values trigger inference."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": None,
            "ad_group_name": None,
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        # None values should trigger inference
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe" == search_term.ad_group_name

    def test_create_search_term_inference_priority(self):
        """Test that ad_group inference prioritizes campaign_name over search_term."""
        data = {
            "search_term": "cotton patch cafe",
            "campaign_name": "Priority Campaign",
            "ad_group_name": pd.NA,
            "metrics": {"impressions": 100, "clicks": 10, "cost": 50.0},
        }

        search_term = SearchTerm(**data)

        # Should use campaign name for ad group inference, not search term
        assert search_term.ad_group_name == "Priority Campaign - Default Ad Group"
        assert search_term.campaign_name == "Priority Campaign"

    def test_model_validator_integration(self):
        """Test that the model validator integrates with field validators properly."""
        # Test with raw dictionary that would come from CSV parsing
        raw_data = {
            "search_term": "cotton patch cafe near me",
            "impressions": 100,
            "clicks": 10,
            "cost": 50.0,
            "conversions": 2.0,
            "conversion_value": 100.0,
        }

        search_term = SearchTerm(**raw_data)

        # Should infer missing fields and create metrics properly
        assert search_term.search_term == "cotton patch cafe near me"
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe near me" == search_term.ad_group_name
        assert search_term.metrics.impressions == 100
        assert search_term.metrics.clicks == 10
        assert search_term.metrics.cost == 50.0

    def test_search_term_validation_still_requires_search_term(self):
        """Test that search_term field is still required."""
        with pytest.raises(ValidationError) as exc_info:
            SearchTerm(campaign_name="Test Campaign", ad_group_name="Test Ad Group")

        # Should fail because search_term is required
        error_details = str(exc_info.value)
        assert "search_term" in error_details.lower()
        assert (
            "field required" in error_details.lower()
            or "missing" in error_details.lower()
        )

    def test_search_term_with_minimal_data(self):
        """Test creating SearchTerm with only the required search_term field."""
        search_term = SearchTerm(search_term="cotton patch cafe")

        # Should have smart defaults for everything else
        assert search_term.search_term == "cotton patch cafe"
        assert "Inferred Campaign" in search_term.campaign_name
        assert "Inferred - cotton patch cafe" == search_term.ad_group_name
        assert search_term.metrics.impressions == 0  # Default metrics
        assert search_term.metrics.clicks == 0
        assert search_term.metrics.cost == 0.0

    def test_field_validation_with_info_context(self):
        """Test that field validators receive proper context from info.data."""
        # This tests the internal mechanism but is important for the feature
        data = {
            "search_term": "test query",
            "campaign_name": "Test Campaign",
            # ad_group_name missing, should use campaign_name in validation
        }

        search_term = SearchTerm(**data)

        # Validator should have access to campaign_name via info.data
        assert search_term.ad_group_name == "Test Campaign - Default Ad Group"
