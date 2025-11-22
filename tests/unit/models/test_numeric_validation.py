"""Tests for numeric field validation in Pydantic models."""

import pytest
from pydantic import ValidationError

from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav.core.models.keyword import Keyword, KeywordMatchType, KeywordStatus
from paidsearchnav.core.models.search_term import SearchTerm, SearchTermMetrics


class TestKeywordNumericValidation:
    """Test numeric field validation in Keyword model."""

    def test_clean_comma_separated_numbers(self):
        """Test that comma-separated numbers are properly cleaned."""
        keyword_data = {
            "campaign_name": "Test Campaign",
            "ad_group_name": "Test Ad Group",
            "text": "test keyword",
            "match_type": KeywordMatchType.EXACT,
            "status": KeywordStatus.ENABLED,
            "impressions": "4,894",  # Comma-separated
            "clicks": "1,234",  # Comma-separated
            "cost": "$1,234.56",  # Currency format
            "conversions": "5.5",
            "quality_score": "8",
        }

        keyword = Keyword(**keyword_data)

        assert keyword.impressions == 4894
        assert keyword.clicks == 1234
        assert keyword.cost == 1234.56
        assert keyword.conversions == 5.5
        assert keyword.quality_score == 8

    def test_handle_invalid_quality_score(self):
        """Test that invalid quality scores are handled properly."""
        keyword_data = {
            "campaign_name": "Test Campaign",
            "ad_group_name": "Test Ad Group",
            "text": "test keyword",
            "match_type": KeywordMatchType.EXACT,
            "status": KeywordStatus.ENABLED,
            "quality_score": "15",  # Invalid (should be 1-10)
        }

        keyword = Keyword(**keyword_data)
        assert keyword.quality_score is None  # Should be None for invalid scores

    def test_handle_empty_numeric_values(self):
        """Test handling of empty/null numeric values."""
        keyword_data = {
            "campaign_name": "Test Campaign",
            "ad_group_name": "Test Ad Group",
            "text": "test keyword",
            "match_type": KeywordMatchType.EXACT,
            "status": KeywordStatus.ENABLED,
            "impressions": "",  # Empty string
            "clicks": "N/A",  # Invalid string
            "cost": None,  # None value
            "cpc_bid": "--",  # Invalid placeholder
        }

        keyword = Keyword(**keyword_data)

        assert keyword.impressions == 0  # Default for required int fields
        assert keyword.clicks == 0  # Default for required int fields
        assert keyword.cost == 0.0  # Default for required float fields
        assert keyword.cpc_bid is None  # None for optional float fields


class TestSearchTermMetricsValidation:
    """Test numeric field validation in SearchTermMetrics model."""

    def test_clean_metrics_values(self):
        """Test that search term metrics are properly cleaned."""
        metrics_data = {
            "impressions": "1,480",
            "clicks": "123",
            "cost": "$500.00",
            "conversions": "2.5",
            "conversion_value": "$1,000.00",
        }

        metrics = SearchTermMetrics(**metrics_data)

        assert metrics.impressions == 1480
        assert metrics.clicks == 123
        assert metrics.cost == 500.0
        assert metrics.conversions == 2.5
        assert metrics.conversion_value == 1000.0

    def test_computed_properties_work(self):
        """Test that computed properties still work after numeric cleaning."""
        metrics = SearchTermMetrics(
            impressions=1000,
            clicks=100,
            cost=50.0,
            conversions=5,
            conversion_value=250.0,
        )

        # CTR should be 10%
        assert metrics.ctr == 10.0
        # CPC should be $0.50
        assert metrics.cpc == 0.5
        # Conversion rate should be 5%
        assert metrics.conversion_rate == 5.0
        # ROAS should be 5.0
        assert metrics.roas == 5.0


class TestSearchTermValidation:
    """Test numeric field validation in SearchTerm model."""

    def test_search_term_with_cleaned_metrics(self):
        """Test SearchTerm creation with comma-separated metrics."""
        search_term_data = {
            "campaign_name": "Test Campaign",
            "ad_group_name": "Test Ad Group",
            "search_term": "cotton patch cafe near me",
            "metrics": {
                "impressions": "1,480",  # Comma-separated
                "clicks": "50",
                "cost": "$25.00",  # Currency format
                "conversions": "1.0",
            },
        }

        search_term = SearchTerm(**search_term_data)

        assert search_term.metrics.impressions == 1480
        assert search_term.metrics.clicks == 50
        assert search_term.metrics.cost == 25.0
        assert search_term.metrics.conversions == 1.0

        # Test backward compatibility properties
        assert search_term.impressions == 1480
        assert search_term.clicks == 50
        assert search_term.cost == 25.0
        assert search_term.conversions == 1.0


class TestCampaignNumericValidation:
    """Test numeric field validation in Campaign model."""

    def test_campaign_with_cleaned_metrics(self):
        """Test Campaign creation with comma-separated metrics."""
        campaign_data = {
            "campaign_id": "test-123",
            "customer_id": "customer-456",
            "name": "Test Campaign",
            "status": CampaignStatus.ENABLED,
            "type": CampaignType.SEARCH,
            "budget_amount": "$100.00",  # Currency format
            "budget_currency": "USD",
            "bidding_strategy": BiddingStrategy.TARGET_CPA,
            "target_cpa": "$50.00",  # Currency format
            "impressions": "10,000",  # Comma-separated
            "clicks": "1,000",  # Comma-separated
            "cost": "$500.00",  # Currency format
            "conversions": "25.5",
        }

        campaign = Campaign(**campaign_data)

        assert campaign.budget_amount == 100.0
        assert campaign.target_cpa == 50.0
        assert campaign.impressions == 10000
        assert campaign.clicks == 1000
        assert campaign.cost == 500.0
        assert campaign.conversions == 25.5


class TestRealWorldValidationScenarios:
    """Test real-world scenarios from Cotton Patch Cafe data."""

    def test_problematic_keyword_data(self):
        """Test keyword data that was causing validation errors."""
        # These values were causing the original validation errors
        problematic_data = {
            "campaign_name": "Search - Cotton Patch",
            "ad_group_name": "Restaurant Keywords",
            "text": "cotton patch cafe",
            "match_type": KeywordMatchType.PHRASE,
            "status": KeywordStatus.ENABLED,
            "impressions": "4,894",  # This was causing the error
            "clicks": "3,099",  # This was causing the error
            "cost": "4,628",  # This was causing the error
            "conversions": "9,848",  # This was causing the error
        }

        # This should not raise a ValidationError anymore
        keyword = Keyword(**problematic_data)

        assert keyword.impressions == 4894
        assert keyword.clicks == 3099
        assert keyword.cost == 4628
        assert keyword.conversions == 9848

    def test_search_term_missing_ad_group(self):
        """Test search term with missing ad_group_name (will be handled in issue #469)."""
        # This test documents the current behavior - missing required fields still fail
        search_term_data = {
            "campaign_name": "Test Campaign",
            "search_term": "cotton patch cafe",
            # Missing ad_group_name - this will still fail until issue #469
            "metrics": {"impressions": "1,480", "clicks": "50"},
        }

        # This should still raise ValidationError for missing required field
        with pytest.raises(ValidationError) as exc_info:
            SearchTerm(**search_term_data)

        assert "ad_group_name" in str(exc_info.value)

    def test_performance_after_cleaning(self):
        """Test that performance calculations work correctly after numeric cleaning."""
        keyword = Keyword(
            campaign_name="Test Campaign",
            ad_group_name="Test Ad Group",
            text="test keyword",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            impressions="10,000",  # Comma-separated
            clicks="1,000",  # Comma-separated
            cost="$500.00",  # Currency format
            conversions="50.0",  # String float
        )

        # Test calculated properties work correctly
        assert keyword.ctr == 10.0  # (1000/10000) * 100
        assert keyword.avg_cpc == 0.5  # 500/1000
        assert keyword.conversion_rate == 5.0  # (50/1000) * 100
        assert keyword.cpa == 10.0  # 500/50
