"""Tests for shared negative list validator analyzer."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer
from paidsearchnav.core.models.analysis import (
    AnalysisResult,
    RecommendationPriority,
    RecommendationType,
)
from paidsearchnav.core.models.campaign import (
    BiddingStrategy,
    Campaign,
    CampaignStatus,
    CampaignType,
)
from paidsearchnav.core.models.keyword import Keyword, KeywordMatchType, KeywordStatus


@pytest.fixture
def mock_data_provider():
    """Create a mock data provider."""
    provider = MagicMock()
    provider.get_campaigns = AsyncMock()
    provider.get_keywords = AsyncMock()
    provider.get_shared_negative_lists = AsyncMock()
    provider.get_campaign_shared_sets = AsyncMock()
    provider.get_shared_set_negatives = AsyncMock()
    return provider


@pytest.fixture
def analyzer(mock_data_provider):
    """Create analyzer instance with mock provider."""
    return SharedNegativeValidatorAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=1000,
        conflict_threshold=0.1,
    )


@pytest.fixture
def sample_campaigns():
    """Create sample campaigns."""

    return [
        Campaign(
            campaign_id="1",
            customer_id="123456789",
            name="Search - Brand",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=200.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=50000,
            clicks=2500,
            conversions=100,
            cost=5000.0,
        ),
        Campaign(
            campaign_id="2",
            customer_id="123456789",
            name="PMax - All Products",
            status=CampaignStatus.ENABLED,
            type=CampaignType.PERFORMANCE_MAX,
            budget_amount=300.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.MAXIMIZE_CONVERSIONS,
            impressions=100000,
            clicks=3000,
            conversions=150,
            cost=7500.0,
        ),
        Campaign(
            campaign_id="3",
            customer_id="123456789",
            name="Local - Seattle",
            status=CampaignStatus.ENABLED,
            type=CampaignType.LOCAL,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=25000,
            clicks=1000,
            conversions=50,
            cost=2500.0,
        ),
        Campaign(
            campaign_id="4",
            customer_id="123456789",
            name="Shopping - Low Traffic",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SHOPPING,
            budget_amount=50.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_ROAS,
            impressions=500,  # Below threshold
            clicks=25,
            conversions=1,
            cost=50.0,
        ),
    ]


@pytest.fixture
def sample_shared_lists():
    """Create sample shared negative lists."""
    return [
        {"id": "list_1", "name": "Brand Protection", "negative_count": 50},
        {"id": "list_2", "name": "Competitor Terms", "negative_count": 30},
        {"id": "list_3", "name": "General Negatives", "negative_count": 100},
        {"id": "list_4", "name": "PMax Exclusions", "negative_count": 25},
        {"id": "list_5", "name": "Local Exclusions", "negative_count": 15},
    ]


@pytest.fixture
def sample_keywords():
    """Create sample keywords."""
    return [
        Keyword(
            keyword_id="kw_1",
            campaign_id="1",
            campaign_name="Search - Brand",
            ad_group_id="ag_1",
            ad_group_name="Brand Keywords",
            text="buy shoes online",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            impressions=10000,
            clicks=500,
            conversions=20,
            cost=1000.0,
            quality_score=7,
        ),
        Keyword(
            keyword_id="kw_2",
            campaign_id="1",
            campaign_name="Search - Brand",
            ad_group_id="ag_1",
            ad_group_name="Brand Keywords",
            text="nike shoes",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            impressions=5000,
            clicks=300,
            conversions=15,
            cost=750.0,
            quality_score=8,
        ),
        Keyword(
            keyword_id="kw_3",
            campaign_id="1",
            campaign_name="Search - Brand",
            ad_group_id="ag_2",
            ad_group_name="Product Keywords",
            text="adidas sneakers",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            impressions=3000,
            clicks=150,
            conversions=8,
            cost=400.0,
            quality_score=6,
        ),
    ]


@pytest.mark.asyncio
async def test_analyze_basic(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists
):
    """Test basic analysis functionality."""
    # Setup mock responses
    mock_data_provider.get_campaigns.return_value = sample_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists

    # Campaign 1 has all lists, Campaign 2 missing PMax list, Campaign 3 missing local list
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        sample_shared_lists[:3],  # Campaign 1 has general lists
        sample_shared_lists[:3],  # Campaign 2 missing PMax list
        sample_shared_lists[:3],  # Campaign 3 missing local list
    ]

    mock_data_provider.get_keywords.return_value = []
    mock_data_provider.get_shared_set_negatives.return_value = []

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    # Verify result
    assert isinstance(result, AnalysisResult)
    assert result.analyzer_name == "Shared Negative List Validator"
    assert result.customer_id == "123456789"

    # Check metrics
    assert result.metrics.total_campaigns_analyzed == 3  # Campaign 4 filtered out
    assert result.metrics.issues_found > 0  # Should find missing lists

    # Check summary
    assert "validation_status" in result.raw_data
    assert result.raw_data["campaigns_analyzed"] == 3
    assert result.raw_data["shared_lists_found"] == 5


@pytest.mark.asyncio
async def test_missing_shared_lists_detection(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists
):
    """Test detection of campaigns missing shared lists."""
    # Setup
    mock_data_provider.get_campaigns.return_value = sample_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists

    # Campaign 2 (PMax) has no shared lists
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        sample_shared_lists[:3],  # Campaign 1 has lists
        [],  # Campaign 2 has no lists
        sample_shared_lists[:2],  # Campaign 3 has some lists
    ]

    mock_data_provider.get_keywords.return_value = []
    mock_data_provider.get_shared_set_negatives.return_value = []

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    # Check missing lists
    missing_lists = result.raw_data["missing_list_campaigns"]
    assert len(missing_lists) > 0

    # Find PMax campaign in missing lists
    pmax_missing = next((m for m in missing_lists if m["campaign_id"] == "2"), None)
    assert pmax_missing is not None
    assert pmax_missing["campaign_type"] == "PERFORMANCE_MAX"
    assert len(pmax_missing["missing_lists"]) > 0
    assert pmax_missing["priority"] == "high"  # PMax should be high priority


@pytest.mark.asyncio
async def test_conflict_detection(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists, sample_keywords
):
    """Test detection of conflicts between keywords and shared negatives."""
    # Setup
    mock_data_provider.get_campaigns.return_value = sample_campaigns[
        :1
    ]  # Just search campaign
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists
    mock_data_provider.get_campaign_shared_sets.return_value = sample_shared_lists
    mock_data_provider.get_keywords.return_value = sample_keywords

    # Add conflicting negatives
    mock_data_provider.get_shared_set_negatives.return_value = [
        {"text": "nike"},  # Conflicts with "nike shoes"
        {"text": '"buy shoes"'},  # Conflicts with "buy shoes online"
        {"text": "[adidas sneakers]"},  # Exact match conflict
    ]

    # Run analysis with conflict checking
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        check_conflicts=True,
    )

    # Check conflicts
    conflicts = result.raw_data["conflict_campaigns"]
    assert len(conflicts) > 0

    conflict = conflicts[0]
    assert conflict["campaign_id"] == "1"
    assert conflict["total_conflicts"] > 0
    assert conflict["impact"]["impressions_blocked"] > 0


@pytest.mark.asyncio
async def test_recommendations_generation(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists
):
    """Test recommendation generation."""
    # Setup campaign missing lists
    mock_data_provider.get_campaigns.return_value = sample_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists

    # All campaigns missing some lists
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        [],  # Campaign 1 missing all
        [],  # Campaign 2 missing all
        [],  # Campaign 3 missing all
    ]

    mock_data_provider.get_keywords.return_value = []
    mock_data_provider.get_shared_set_negatives.return_value = []

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        auto_apply_suggestions=True,
    )

    # Check recommendations
    assert len(result.recommendations) > 0

    # Check for missing list recommendations
    add_negative_recs = [
        r for r in result.recommendations if r.type == RecommendationType.ADD_NEGATIVE
    ]
    assert len(add_negative_recs) > 0

    # Check auto-apply data
    rec = add_negative_recs[0]
    assert rec.priority in (RecommendationPriority.HIGH, RecommendationPriority.MEDIUM)
    assert "Apply shared negative lists" in rec.title
    assert "auto_apply" in rec.action_data
    assert rec.action_data["auto_apply"] is True
    assert "shared_list_ids" in rec.action_data


@pytest.mark.asyncio
async def test_coverage_statistics(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists
):
    """Test coverage statistics calculation."""
    # Setup
    mock_data_provider.get_campaigns.return_value = sample_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists

    # Varying coverage
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        sample_shared_lists[:3],  # Campaign 1: 3 lists
        sample_shared_lists[:1],  # Campaign 2: 1 list
        [],  # Campaign 3: no lists
    ]

    mock_data_provider.get_keywords.return_value = []
    mock_data_provider.get_shared_set_negatives.return_value = []

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    # Check coverage stats
    coverage_stats = result.raw_data["coverage_stats"]
    assert "coverage_percentage" in coverage_stats
    assert "avg_lists_per_campaign" in coverage_stats
    assert "most_used_list" in coverage_stats
    assert "list_usage_counts" in coverage_stats

    # Coverage should be 66.7% (2 out of 3 campaigns have lists)
    assert coverage_stats["coverage_percentage"] == pytest.approx(66.7, rel=0.1)
    assert coverage_stats["avg_lists_per_campaign"] > 0


@pytest.mark.asyncio
async def test_campaign_filtering(analyzer, mock_data_provider, sample_campaigns):
    """Test campaign filtering logic."""

    # Add more campaigns with various statuses
    all_campaigns = sample_campaigns + [
        Campaign(
            campaign_id="5",
            customer_id="123456789",
            name="Paused Campaign",
            status=CampaignStatus.PAUSED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=10000,
            clicks=500,
            conversions=20,
            cost=1000.0,
        ),
        Campaign(
            campaign_id="6",
            customer_id="123456789",
            name="Removed Campaign",
            status=CampaignStatus.REMOVED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=10000,
            clicks=500,
            conversions=20,
            cost=1000.0,
        ),
    ]

    mock_data_provider.get_campaigns.return_value = all_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = []
    mock_data_provider.get_campaign_shared_sets.return_value = []

    # Run analysis
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    # Should include enabled and paused, but not removed or low-impression campaigns
    assert (
        result.metrics.total_campaigns_analyzed == 4
    )  # Includes paused, excludes removed and low-impression


@pytest.mark.asyncio
async def test_target_campaigns_filter(
    analyzer, mock_data_provider, sample_campaigns, sample_shared_lists
):
    """Test filtering by target campaigns."""
    mock_data_provider.get_campaigns.return_value = sample_campaigns
    mock_data_provider.get_shared_negative_lists.return_value = sample_shared_lists
    mock_data_provider.get_campaign_shared_sets.return_value = []

    # Run analysis with specific campaigns
    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        target_campaigns=["1", "2"],  # Only analyze these campaigns
    )

    # Should only analyze the targeted campaigns
    assert result.metrics.total_campaigns_analyzed == 2
    assert result.raw_data["campaigns_analyzed"] == 2


@pytest.mark.asyncio
async def test_conflict_detection_match_types(analyzer, mock_data_provider):
    """Test conflict detection with different match types."""

    # Create test campaign and keywords
    campaign = Campaign(
        campaign_id="1",
        customer_id="123456789",
        name="Test Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SEARCH,
        budget_amount=100.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_CPA,
        impressions=10000,
        clicks=500,
        conversions=20,
        cost=1000.0,
    )

    keywords = [
        Keyword(
            keyword_id="kw_1",
            campaign_id="1",
            campaign_name="Test Campaign",
            ad_group_id="ag_1",
            ad_group_name="Test Ad Group",
            text="red running shoes",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            impressions=1000,
            clicks=50,
            conversions=2,
            cost=100.0,
            quality_score=7,
        ),
    ]

    mock_data_provider.get_campaigns.return_value = [campaign]
    mock_data_provider.get_shared_negative_lists.return_value = [
        {"id": "list_1", "name": "Test List", "negative_count": 3}
    ]
    mock_data_provider.get_campaign_shared_sets.return_value = [
        {"id": "list_1", "name": "Test List"}
    ]
    mock_data_provider.get_keywords.return_value = keywords

    # Test different negative match types
    test_cases = [
        # Broad match negative - all words must be present
        (["running"], True),  # Should conflict
        (["blue running"], False),  # Should not conflict (blue not in keyword)
        # Phrase match negative
        (['"running shoes"'], True),  # Should conflict
        (['"blue shoes"'], False),  # Should not conflict
        # Exact match negative
        (["[red running shoes]"], True),  # Should conflict
        (["[running shoes]"], False),  # Should not conflict (not exact match)
    ]

    for negatives, should_conflict in test_cases:
        mock_data_provider.get_shared_set_negatives.return_value = [
            {"text": neg} for neg in negatives
        ]

        result = await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
            check_conflicts=True,
        )

        conflicts = result.raw_data["conflict_campaigns"]
        if should_conflict:
            assert len(conflicts) > 0, f"Expected conflict for negatives: {negatives}"
        else:
            assert len(conflicts) == 0, (
                f"Unexpected conflict for negatives: {negatives}"
            )


@pytest.mark.asyncio
async def test_empty_data_handling(analyzer, mock_data_provider):
    """Test handling of empty data scenarios."""
    # No campaigns
    mock_data_provider.get_campaigns.return_value = []
    mock_data_provider.get_shared_negative_lists.return_value = []

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    assert result.metrics.total_campaigns_analyzed == 0
    assert result.metrics.issues_found == 0
    assert result.raw_data["validation_status"] == "EXCELLENT"
    assert result.raw_data["coverage_stats"]["coverage_percentage"] == 0.0


@pytest.mark.asyncio
async def test_determine_priority_edge_cases(analyzer, mock_data_provider):
    """Test priority determination for edge cases."""

    # High spend campaign (over $10k)
    high_spend_campaign = Campaign(
        campaign_id="1",
        customer_id="123456789",
        name="High Spend Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SHOPPING,
        budget_amount=500.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_ROAS,
        impressions=500000,
        clicks=25000,
        conversions=1000,
        cost=15000.0,  # Over $10k
    )

    # High conversion value campaign
    high_value_campaign = Campaign(
        campaign_id="2",
        customer_id="123456789",
        name="High Value Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SEARCH,
        budget_amount=200.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_CPA,
        impressions=50000,
        clicks=2500,
        conversions=250,
        cost=5000.0,
        revenue=30000.0,  # High revenue
    )

    # Low priority campaign
    low_priority_campaign = Campaign(
        campaign_id="3",
        customer_id="123456789",
        name="Display Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.DISPLAY,
        budget_amount=50.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.MAXIMIZE_CLICKS,
        impressions=100000,
        clicks=1000,
        conversions=10,
        cost=500.0,
    )

    campaigns = [high_spend_campaign, high_value_campaign, low_priority_campaign]
    mock_data_provider.get_campaigns.return_value = campaigns
    mock_data_provider.get_shared_negative_lists.return_value = [
        {"id": "list_1", "name": "General Brand Protection", "negative_count": 10},
        {"id": "list_2", "name": "Shopping Exclusions", "negative_count": 15},
        {"id": "list_3", "name": "Search Negatives", "negative_count": 20},
    ]

    # All campaigns missing lists
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        [],
        [],
        [],
    ]  # Return empty for each campaign

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    missing_lists = result.raw_data["missing_list_campaigns"]
    assert len(missing_lists) == 3  # All 3 campaigns should be analyzed

    # Verify priorities
    high_spend_missing = next(
        (m for m in missing_lists if m["campaign_id"] == "1"), None
    )
    assert high_spend_missing is not None
    assert high_spend_missing["priority"] == "high"  # High spend gets high priority

    high_value_missing = next(
        (m for m in missing_lists if m["campaign_id"] == "2"), None
    )
    assert high_value_missing is not None
    assert high_value_missing["priority"] == "medium"  # Search campaign gets medium

    low_priority_missing = next(
        (m for m in missing_lists if m["campaign_id"] == "3"), None
    )
    assert low_priority_missing is not None
    assert low_priority_missing["priority"] == "low"  # Display gets low priority


@pytest.mark.asyncio
async def test_conflict_detection_edge_cases(analyzer, mock_data_provider):
    """Test conflict detection with edge cases."""

    # Test campaign
    campaign = Campaign(
        campaign_id="1",
        customer_id="123456789",
        name="Test Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SEARCH,
        budget_amount=100.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_CPA,
        impressions=10000,
        clicks=500,
        conversions=20,
        cost=1000.0,
    )

    # Keywords with special characters and spaces
    keywords = [
        Keyword(
            keyword_id="kw_1",
            campaign_id="1",
            campaign_name="Test Campaign",
            ad_group_id="ag_1",
            ad_group_name="Test Ad Group",
            text="hotel near jfk airport",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            impressions=1000,
            clicks=50,
            conversions=2,
            cost=100.0,
            quality_score=7,
        ),
        Keyword(
            keyword_id="kw_2",
            campaign_id="1",
            campaign_name="Test Campaign",
            ad_group_id="ag_1",
            ad_group_name="Test Ad Group",
            text="best-price guarantee",
            match_type=KeywordMatchType.PHRASE,
            status=KeywordStatus.ENABLED,
            impressions=500,
            clicks=25,
            conversions=1,
            cost=50.0,
            quality_score=6,
        ),
        Keyword(
            keyword_id="kw_3",
            campaign_id="1",
            campaign_name="Test Campaign",
            ad_group_id="ag_1",
            ad_group_name="Test Ad Group",
            text="24/7 customer support",
            match_type=KeywordMatchType.EXACT,
            status=KeywordStatus.ENABLED,
            impressions=300,
            clicks=15,
            conversions=1,
            cost=30.0,
            quality_score=8,
        ),
    ]

    mock_data_provider.get_campaigns.return_value = [campaign]
    mock_data_provider.get_shared_negative_lists.return_value = [
        {"id": "list_1", "name": "Test List", "negative_count": 5}
    ]
    mock_data_provider.get_campaign_shared_sets.return_value = [
        {"id": "list_1", "name": "Test List"}
    ]
    mock_data_provider.get_keywords.return_value = keywords

    # Edge case negatives
    mock_data_provider.get_shared_set_negatives.return_value = [
        {"text": "airport"},  # Partial match
        {"text": '"best-price"'},  # Phrase with hyphen
        {"text": "[24/7 customer support]"},  # Exact with special chars
        {"text": "JFK AIRPORT"},  # Case sensitivity test
        {"text": ""},  # Empty negative (edge case)
    ]

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        check_conflicts=True,
    )

    conflicts = result.raw_data["conflict_campaigns"]
    assert len(conflicts) > 0

    # Verify conflicts detected correctly
    conflict = conflicts[0]
    conflict_keywords = [c["keyword"] for c in conflict["conflicts"]]

    assert "hotel near jfk airport" in conflict_keywords  # airport matches
    assert "best-price guarantee" in conflict_keywords  # phrase match works
    assert "24/7 customer support" in conflict_keywords  # exact match works


@pytest.mark.asyncio
async def test_coverage_stats_edge_cases(analyzer, mock_data_provider):
    """Test coverage statistics calculation with edge cases."""

    # Create campaigns
    campaigns = [
        Campaign(
            campaign_id=str(i),
            customer_id="123456789",
            name=f"Campaign {i}",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=10000,
            clicks=500,
            conversions=20,
            cost=1000.0,
        )
        for i in range(5)
    ]

    # Multiple shared lists
    shared_lists = [
        {"id": f"list_{i}", "name": f"List {i}", "negative_count": 10 * i}
        for i in range(1, 4)
    ]

    mock_data_provider.get_campaigns.return_value = campaigns
    mock_data_provider.get_shared_negative_lists.return_value = shared_lists

    # Uneven distribution of lists
    mock_data_provider.get_campaign_shared_sets.side_effect = [
        shared_lists,  # Campaign 0: all lists
        shared_lists[:2],  # Campaign 1: 2 lists
        shared_lists[:1],  # Campaign 2: 1 list
        shared_lists[:1],  # Campaign 3: 1 list (same as campaign 2)
        [],  # Campaign 4: no lists
    ]

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    coverage_stats = result.raw_data["coverage_stats"]

    # 4 out of 5 campaigns have lists = 80%
    assert coverage_stats["coverage_percentage"] == 80.0

    # Total lists: 3 + 2 + 1 + 1 + 0 = 7, avg = 7/5 = 1.4
    assert coverage_stats["avg_lists_per_campaign"] == 1.4

    # List 1 is used by 4 campaigns (most used)
    assert coverage_stats["most_used_list"] == "List 1"

    # List 3 is used by only 1 campaign (least used)
    assert coverage_stats["least_used_list"] == "List 3"

    # Verify usage counts
    assert coverage_stats["list_usage_counts"]["List 1"] == 4
    assert coverage_stats["list_usage_counts"]["List 2"] == 2
    assert coverage_stats["list_usage_counts"]["List 3"] == 1


@pytest.mark.asyncio
async def test_error_handling(analyzer, mock_data_provider):
    """Test error handling in various scenarios."""
    # Test API error during campaign fetch
    mock_data_provider.get_campaigns.side_effect = Exception("API Error")

    with pytest.raises(Exception, match="API Error"):
        await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        )

    # Reset for next test
    mock_data_provider.get_campaigns.side_effect = None
    mock_data_provider.get_campaigns.return_value = [
        Campaign(
            campaign_id="1",
            customer_id="123456789",
            name="Test Campaign",
            status=CampaignStatus.ENABLED,
            type=CampaignType.SEARCH,
            budget_amount=100.0,
            budget_currency="USD",
            bidding_strategy=BiddingStrategy.TARGET_CPA,
            impressions=10000,
            clicks=500,
            conversions=20,
            cost=1000.0,
        )
    ]

    # Test error during shared list fetch
    mock_data_provider.get_shared_negative_lists.side_effect = Exception(
        "List fetch error"
    )

    with pytest.raises(Exception, match="List fetch error"):
        await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
            end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        )


@pytest.mark.asyncio
async def test_configurable_parameters(mock_data_provider):
    """Test that configurable parameters work correctly."""
    # Create analyzer with custom parameters
    custom_analyzer = SharedNegativeValidatorAnalyzer(
        data_provider=mock_data_provider,
        min_impressions=500,
        wasted_spend_percentage=0.1,  # 10% instead of default 5%
        avg_conversion_value=100.0,  # $100 instead of default $50
        impressions_risk_percentage=0.2,  # 20% instead of default 10%
        conflict_recovery_estimate=0.15,  # 15% instead of default 10%
        high_priority_cost_threshold=5000.0,  # $5k instead of default $10k
    )

    # Setup test data
    test_campaign = Campaign(
        campaign_id="1",
        customer_id="123456789",
        name="Test Campaign",
        status=CampaignStatus.ENABLED,
        type=CampaignType.SEARCH,
        budget_amount=200.0,
        budget_currency="USD",
        bidding_strategy=BiddingStrategy.TARGET_CPA,
        impressions=10000,
        clicks=500,
        conversions=20,
        cost=6000.0,  # Between $5k and $10k
    )

    mock_data_provider.get_campaigns.return_value = [test_campaign]
    mock_data_provider.get_shared_negative_lists.return_value = [
        {"id": "list_1", "name": "General Brand Protection", "negative_count": 10}
    ]
    mock_data_provider.get_campaign_shared_sets.return_value = []  # Missing lists

    result = await custom_analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
    )

    missing_lists = result.raw_data["missing_list_campaigns"]
    assert len(missing_lists) == 1

    missing = missing_lists[0]
    # Check priority - with custom threshold of $5k, $6k campaign should be high priority
    assert missing["priority"] == "high"

    # Check estimated impact calculations use custom percentages
    assert missing["estimated_impact"]["wasted_spend_risk"] == 6000.0 * 0.1  # 600
    assert missing["estimated_impact"]["impressions_at_risk"] == 10000 * 0.2  # 2000

    # Test conflict recovery estimate
    mock_data_provider.get_keywords.return_value = [
        Keyword(
            keyword_id="kw_1",
            campaign_id="1",
            campaign_name="Test Campaign",
            ad_group_id="ag_1",
            ad_group_name="Test Ad Group",
            text="brand product",
            match_type=KeywordMatchType.BROAD,
            status=KeywordStatus.ENABLED,
            impressions=1000,
            clicks=50,
            conversions=5,
            cost=100.0,
            quality_score=7,
        )
    ]
    mock_data_provider.get_shared_set_negatives.return_value = [
        {"text": "brand"}  # Conflicts with keyword
    ]

    result_with_conflicts = await custom_analyzer.analyze(
        customer_id="123456789",
        start_date=datetime(2024, 1, 1, tzinfo=timezone.utc),
        end_date=datetime(2024, 3, 31, tzinfo=timezone.utc),
        check_conflicts=True,
    )

    # Check that savings calculation uses custom conversion value and recovery estimate
    # 5 conversions lost * $100 conversion value * 15% recovery = $75
    expected_conflict_savings = 5 * 100.0 * 0.15
    assert (
        result_with_conflicts.metrics.potential_cost_savings
        >= expected_conflict_savings
    )


def test_parameter_validation(mock_data_provider):
    """Test that parameter validation works correctly."""
    # Test invalid percentage values
    with pytest.raises(
        ValueError, match="wasted_spend_percentage must be between 0 and 1"
    ):
        SharedNegativeValidatorAnalyzer(
            data_provider=mock_data_provider,
            wasted_spend_percentage=1.5,  # > 1
        )

    with pytest.raises(
        ValueError, match="wasted_spend_percentage must be between 0 and 1"
    ):
        SharedNegativeValidatorAnalyzer(
            data_provider=mock_data_provider,
            wasted_spend_percentage=-0.1,  # < 0
        )

    # Test invalid positive values
    with pytest.raises(ValueError, match="avg_conversion_value must be positive"):
        SharedNegativeValidatorAnalyzer(
            data_provider=mock_data_provider,
            avg_conversion_value=0,  # <= 0
        )

    with pytest.raises(
        ValueError, match="high_priority_cost_threshold must be positive"
    ):
        SharedNegativeValidatorAnalyzer(
            data_provider=mock_data_provider,
            high_priority_cost_threshold=-100,  # < 0
        )

    # Test valid edge cases
    analyzer = SharedNegativeValidatorAnalyzer(
        data_provider=mock_data_provider,
        wasted_spend_percentage=0.0,  # Valid: 0
        impressions_risk_percentage=1.0,  # Valid: 1
        conflict_recovery_estimate=0.5,  # Valid: between 0 and 1
        min_impressions=0,  # Valid: 0
    )
    assert analyzer.wasted_spend_percentage == 0.0
    assert analyzer.impressions_risk_percentage == 1.0
    assert analyzer.conflict_recovery_estimate == 0.5
    assert analyzer.min_impressions == 0


def test_special_character_handling_in_conflicts():
    """Test handling of special characters in conflict detection."""
    from paidsearchnav.analyzers.shared_negatives import SharedNegativeValidatorAnalyzer

    analyzer = SharedNegativeValidatorAnalyzer(
        data_provider=None,  # Not needed for this test
        min_impressions=1000,
    )

    # Test various special character scenarios
    test_cases = [
        # (keyword, negative, match_type, expected_conflict)
        ("hotel & spa", "spa", "BROAD", True),  # Ampersand with spaces
        ("50% off sale", "sale", "BROAD", True),  # Percent sign
        ("email support online", "email", "BROAD", True),  # Simple word match
        ("product #1", "product", "BROAD", True),  # Hash symbol
        ("best-in-class", '"best-in-class"', "PHRASE", True),  # Hyphens in phrase
        ("$99 deal", "deal", "BROAD", True),  # Dollar sign
        ("5* hotel", "hotel", "BROAD", True),  # Asterisk
        ("(limited offer)", "offer)", "BROAD", True),  # Parentheses
        # Cases that should NOT conflict
        ("email@example.com", "email", "BROAD", False),  # @ makes it one word
        ("product#1", "product", "BROAD", False),  # No space, one word
    ]

    for keyword, negative, match_type, expected in test_cases:
        result = analyzer._is_conflict(keyword.lower(), negative.lower(), match_type)
        assert result == expected, (
            f"Failed for keyword='{keyword}', negative='{negative}', "
            f"expected={expected}, got={result}"
        )
