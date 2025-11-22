"""Integration test for the advanced search term analyzer."""

from datetime import datetime
from unittest.mock import AsyncMock

import pytest

from paidsearchnav.analyzers.search_term_analyzer import SearchTermAnalyzer
from paidsearchnav.core.models import (
    Keyword,
    MatchType,
    RecommendationType,
    SearchTerm,
    SearchTermMetrics,
)


@pytest.fixture
def comprehensive_search_terms():
    """Create a comprehensive set of search terms for testing."""
    return [
        # Near me searches (local intent)
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="456",
            ad_group_name="Local Coffee",
            search_term="best coffee shop near me",
            metrics=SearchTermMetrics(
                impressions=1500,
                clicks=150,
                cost=225.0,
                conversions=15.0,
                conversion_value=750.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="456",
            ad_group_name="Local Coffee",
            search_term="coffee shop open now near me",
            metrics=SearchTermMetrics(
                impressions=800,
                clicks=80,
                cost=120.0,
                conversions=8.0,
                conversion_value=400.0,
            ),
        ),
        # Transactional queries
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="457",
            ad_group_name="Coffee Products",
            search_term="buy coffee beans online free shipping",
            metrics=SearchTermMetrics(
                impressions=600,
                clicks=60,
                cost=90.0,
                conversions=6.0,
                conversion_value=300.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="457",
            ad_group_name="Coffee Products",
            search_term="best coffee maker deals 2024",
            metrics=SearchTermMetrics(
                impressions=400,
                clicks=40,
                cost=60.0,
                conversions=4.0,
                conversion_value=400.0,
            ),
        ),
        # Informational queries
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="458",
            ad_group_name="Coffee Info",
            search_term="how to make cold brew coffee",
            metrics=SearchTermMetrics(
                impressions=2000,
                clicks=100,
                cost=50.0,
                conversions=1.0,
                conversion_value=50.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="458",
            ad_group_name="Coffee Info",
            search_term="what is the difference between latte and cappuccino",
            metrics=SearchTermMetrics(
                impressions=1000,
                clicks=50,
                cost=25.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
        # Wasteful/irrelevant queries
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="456",
            ad_group_name="Local Coffee",
            search_term="coffee shop jobs hiring near me",
            metrics=SearchTermMetrics(
                impressions=3000,
                clicks=300,
                cost=450.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="457",
            ad_group_name="Coffee Products",
            search_term="free coffee samples",
            metrics=SearchTermMetrics(
                impressions=5000,
                clicks=500,
                cost=250.0,
                conversions=0.0,
                conversion_value=0.0,
            ),
        ),
        # Long-tail queries
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="456",
            ad_group_name="Local Coffee",
            search_term="organic fair trade coffee shop downtown seattle",
            metrics=SearchTermMetrics(
                impressions=200,
                clicks=40,
                cost=60.0,
                conversions=8.0,
                conversion_value=400.0,
            ),
        ),
        # Question queries
        SearchTerm(
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            ad_group_id="458",
            ad_group_name="Coffee Info",
            search_term="where to buy green coffee beans",
            metrics=SearchTermMetrics(
                impressions=300,
                clicks=30,
                cost=45.0,
                conversions=3.0,
                conversion_value=150.0,
            ),
        ),
    ]


@pytest.fixture
def existing_keywords():
    """Create existing keywords."""
    return [
        Keyword(
            keyword_id="k1",
            ad_group_id="456",
            ad_group_name="Local Coffee",
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            text="coffee shop",
            match_type=MatchType.BROAD,
            status="ENABLED",
            impressions=10000,
            clicks=1000,
            cost=1500.0,
            conversions=50.0,
            conversion_value=2500.0,
        ),
        Keyword(
            keyword_id="k2",
            ad_group_id="457",
            ad_group_name="Coffee Products",
            campaign_id="123",
            campaign_name="Coffee Shop Campaign",
            text="coffee beans",
            match_type=MatchType.PHRASE,
            status="ENABLED",
            impressions=5000,
            clicks=500,
            cost=750.0,
            conversions=25.0,
            conversion_value=1250.0,
        ),
    ]


@pytest.mark.asyncio
async def test_search_term_analyzer_comprehensive(
    comprehensive_search_terms, existing_keywords
):
    """Test the search term analyzer with comprehensive data."""
    # Create mock data provider
    mock_provider = AsyncMock()
    mock_provider.get_search_terms.return_value = comprehensive_search_terms
    mock_provider.get_keywords.return_value = existing_keywords

    # Create analyzer
    analyzer = SearchTermAnalyzer(mock_provider)

    # Run analysis
    result = await analyzer.analyze(
        customer_id="12345",
        start_date=datetime(2024, 1, 1),
        end_date=datetime(2024, 1, 31),
        brand_terms=["starbucks", "dunkin"],
    )

    # Verify basic results
    assert result.customer_id == "12345"
    assert result.analysis_type == "advanced_search_terms"
    assert result.analyzer_name == "Advanced Search Term Analyzer"

    # Check metrics
    assert result.metrics.total_search_terms_analyzed == len(comprehensive_search_terms)
    assert result.metrics.issues_found > 0  # Should find negative keywords
    assert result.metrics.potential_cost_savings > 0  # From wasteful queries

    # Check intent analysis
    intent_analysis = result.raw_data["intent_analysis"]
    assert "LOCAL" in intent_analysis
    assert "TRANSACTIONAL" in intent_analysis
    assert "INFORMATIONAL" in intent_analysis

    # Check local intent terms
    local_terms = intent_analysis["LOCAL"]["terms"]
    assert len(local_terms) >= 2  # "near me" queries
    assert intent_analysis["LOCAL"]["conversions"] > 0

    # Check recommendations
    assert len(result.recommendations) > 0

    # Should have negative keyword recommendations
    negative_recs = [
        r for r in result.recommendations if r.type == RecommendationType.ADD_NEGATIVE
    ]
    assert len(negative_recs) > 0
    assert any("jobs" in str(r.action_data) for r in negative_recs)
    assert any("free" in str(r.action_data) for r in negative_recs)

    # Should have add keyword recommendations
    add_recs = [
        r for r in result.recommendations if r.type == RecommendationType.ADD_KEYWORD
    ]
    assert len(add_recs) > 0

    # Should have location optimization recommendations
    location_recs = [
        r
        for r in result.recommendations
        if r.type == RecommendationType.OPTIMIZE_LOCATION
    ]
    assert len(location_recs) > 0

    # Check n-gram analysis
    custom_metrics = result.metrics.custom_metrics
    assert "top_ngrams" in custom_metrics
    top_ngrams = custom_metrics["top_ngrams"]
    assert len(top_ngrams) > 0
    assert any("coffee" in ng["ngram"] for ng in top_ngrams)

    # Check local intent summary
    local_summary = custom_metrics["local_intent_summary"]
    assert local_summary["near_me_searches"] >= 2
    assert local_summary["store_searches"] >= 0

    # Verify opportunity analysis
    opportunity_analysis = result.raw_data.get("opportunity_analysis", {})
    assert len(opportunity_analysis) > 0

    # Verify negative analysis
    negative_analysis = result.raw_data.get("negative_analysis", {})
    assert "irrelevant" in negative_analysis
    assert "high_cost_no_conversion" in negative_analysis
    assert len(negative_analysis["irrelevant"]) > 0  # Should find job queries

    print("\n=== Search Term Analysis Summary ===")
    print(f"Total search terms analyzed: {result.metrics.total_search_terms_analyzed}")
    print(f"Issues found: {result.metrics.issues_found}")
    print(f"Potential cost savings: ${result.metrics.potential_cost_savings:.2f}")
    print(f"Total recommendations: {len(result.recommendations)}")
    print("\n=== Intent Breakdown ===")
    for intent, data in intent_analysis.items():
        if isinstance(data, dict) and "terms" in data:
            print(
                f"{intent}: {len(data['terms'])} terms, "
                f"{data.get('conversions', 0):.0f} conversions, "
                f"${data.get('cost', 0):.2f} cost"
            )
    print("\n=== Top Recommendations ===")
    for i, rec in enumerate(result.recommendations[:3], 1):
        print(f"{i}. [{rec.priority}] {rec.title}")
        print(f"   {rec.description[:100]}...")


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
