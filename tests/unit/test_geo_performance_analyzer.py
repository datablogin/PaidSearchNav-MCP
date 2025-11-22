"""Tests for geographic performance analyzer."""

from datetime import datetime, timedelta
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav.analyzers.geo_performance import GeoPerformanceAnalyzer
from paidsearchnav.core.models import (
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    GeoPerformanceSummary,
    LocationInsight,
)
from paidsearchnav.platforms.google.client import GoogleAdsAPIClient


@pytest.fixture
def mock_api_client():
    """Create a mock Google Ads API client."""
    client = MagicMock(spec=GoogleAdsAPIClient)
    return client


@pytest.fixture
def analyzer(mock_api_client):
    """Create a geo performance analyzer instance."""
    return GeoPerformanceAnalyzer(
        api_client=mock_api_client,
        min_impressions=100,
        min_clicks=10,
        performance_threshold=0.2,
        top_locations_count=10,
    )


@pytest.fixture
def sample_geo_data():
    """Sample geographic performance data from API."""
    return [
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "country_name": "United States",
            "region_name": "California",
            "city_name": "San Francisco",
            "metro_name": "San Francisco-Oakland-San Jose CA",
            "postal_code": "94102",
            "impressions": 1000,
            "clicks": 50,
            "conversions": 5.0,
            "cost_micros": 250000000,  # $250
            "conversion_value_micros": 500000000,  # $500
        },
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "country_name": "United States",
            "region_name": "California",
            "city_name": "Los Angeles",
            "metro_name": "Los Angeles-Long Beach CA",
            "postal_code": "90210",
            "impressions": 800,
            "clicks": 40,
            "conversions": 2.0,
            "cost_micros": 200000000,  # $200
            "conversion_value_micros": 300000000,  # $300
        },
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "country_name": "United States",
            "region_name": "New York",
            "city_name": "New York",
            "metro_name": "New York NY",
            "postal_code": "10001",
            "impressions": 500,
            "clicks": 25,
            "conversions": 1.0,
            "cost_micros": 150000000,  # $150
            "conversion_value_micros": 100000000,  # $100
        },
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "country_name": "United States",
            "region_name": "Texas",
            "city_name": "Houston",
            "metro_name": "Houston TX",
            "postal_code": "77001",
            "impressions": 50,  # Below threshold
            "clicks": 5,  # Below threshold
            "conversions": 0.5,
            "cost_micros": 50000000,  # $50
            "conversion_value_micros": 25000000,  # $25
        },
    ]


@pytest.fixture
def sample_distance_data():
    """Sample distance performance data from API."""
    return [
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "distance_bucket": "WITHIN_0_5_MILES",
            "impressions": 600,
            "clicks": 30,
            "conversions": 3.0,
            "cost_micros": 150000000,
            "conversion_value_micros": 300000000,
        },
        {
            "customer_id": "123456789",
            "campaign_id": "123/456",
            "campaign_name": "Test Campaign",
            "distance_bucket": "WITHIN_5_10_MILES",
            "impressions": 400,
            "clicks": 20,
            "conversions": 2.0,
            "cost_micros": 100000000,
            "conversion_value_micros": 200000000,
        },
    ]


@pytest.mark.asyncio
async def test_analyze_basic_functionality(analyzer, mock_api_client, sample_geo_data):
    """Test basic analyze functionality."""
    # Setup mock
    mock_api_client.get_geographic_performance = AsyncMock(return_value=sample_geo_data)
    mock_api_client.get_distance_performance = AsyncMock(return_value=[])

    # Test data
    customer_id = "123456789"
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    # Run analysis
    result = await analyzer.analyze(
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        geographic_level="CITY",
    )

    # Verify result type
    assert isinstance(result, GeoPerformanceAnalysisResult)
    assert result.customer_id == customer_id
    assert result.analyzer_name == "geo_performance"

    # Verify API was called correctly
    mock_api_client.get_geographic_performance.assert_called_once_with(
        customer_id=customer_id,
        start_date=start_date,
        end_date=end_date,
        geographic_level="CITY",
        campaign_ids=None,
    )


@pytest.mark.asyncio
async def test_data_filtering(analyzer, mock_api_client, sample_geo_data):
    """Test that data is filtered by minimum thresholds."""
    mock_api_client.get_geographic_performance = AsyncMock(return_value=sample_geo_data)
    mock_api_client.get_distance_performance = AsyncMock(return_value=[])

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )

    # Should filter out Houston (impressions=50, clicks=5, below thresholds)
    assert len(result.performance_data) == 3
    location_names = [d.location_name for d in result.performance_data]
    assert "Houston" not in location_names
    assert "San Francisco" in location_names
    assert "Los Angeles" in location_names
    assert "New York" in location_names


def test_convert_to_performance_data(analyzer, sample_geo_data):
    """Test conversion of raw API data to performance data models."""
    start_date = datetime.now() - timedelta(days=30)
    end_date = datetime.now()

    performance_data = analyzer._convert_to_performance_data(
        sample_geo_data, "CITY", start_date, end_date
    )

    assert len(performance_data) == 4

    # Test first location (San Francisco)
    sf_data = performance_data[0]
    assert isinstance(sf_data, GeoPerformanceData)
    assert sf_data.location_name == "San Francisco"
    assert sf_data.geographic_level == GeographicLevel.CITY
    assert sf_data.impressions == 1000
    assert sf_data.clicks == 50
    assert sf_data.conversions == 5.0
    assert sf_data.cost == 250.0  # Converted from micros
    assert sf_data.revenue == 500.0  # Converted from micros
    assert sf_data.ctr == 0.05  # 50/1000
    assert sf_data.cpa == 50.0  # 250/5
    assert sf_data.roas == 2.0  # 500/250


def test_filter_performance_data(analyzer):
    """Test filtering of performance data by thresholds."""
    # Create test data with some below thresholds
    test_data = [
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="Above Threshold",
            impressions=150,  # Above min_impressions (100)
            clicks=15,  # Above min_clicks (10)
            conversions=1.0,
            cost_micros=100000000,
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="Below Impressions",
            impressions=50,  # Below min_impressions (100)
            clicks=15,  # Above min_clicks (10)
            conversions=1.0,
            cost_micros=100000000,
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="Below Clicks",
            impressions=150,  # Above min_impressions (100)
            clicks=5,  # Below min_clicks (10)
            conversions=1.0,
            cost_micros=100000000,
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
    ]

    filtered_data = analyzer._filter_performance_data(test_data)

    assert len(filtered_data) == 1
    assert filtered_data[0].location_name == "Above Threshold"


def test_calculate_performance_score(analyzer):
    """Test performance score calculation."""
    # Perfect performance (equal to average)
    score = analyzer._calculate_performance_score(1.0, 1.0, 1.0)
    # CPA: 100 - (1-1)*50 = 100, ROAS: (1-1)*25+50 = 50, Conv: (1-1)*25+50 = 50
    # Score = 100*0.4 + 50*0.4 + 50*0.2 = 40 + 20 + 10 = 70
    assert score == 70.0

    # Excellent performance (better than average)
    score = analyzer._calculate_performance_score(
        0.5, 2.0, 1.5
    )  # Low CPA, high ROAS, high conv rate
    assert score > 70

    # Poor performance (worse than average)
    score = analyzer._calculate_performance_score(
        2.0, 0.5, 0.5
    )  # High CPA, low ROAS, low conv rate
    assert score < 50


def test_get_recommended_action(analyzer):
    """Test recommendation action logic."""
    # High performance should recommend budget increase
    action = analyzer._get_recommended_action(85, 0.5, 2.0)
    assert action == "INCREASE_BUDGET"

    # Average performance should maintain current
    action = analyzer._get_recommended_action(65, 1.0, 1.0)
    assert action == "MAINTAIN_CURRENT"

    # Poor performance should decrease budget
    action = analyzer._get_recommended_action(30, 2.0, 0.5)
    assert action == "DECREASE_BUDGET"


def test_get_location_name(analyzer):
    """Test location name extraction by geographic level."""
    sample_row = {
        "country_name": "United States",
        "region_name": "California",
        "city_name": "San Francisco",
        "postal_code": "94102",
    }

    # Test different geographic levels
    assert analyzer._get_location_name(sample_row, "COUNTRY") == "United States"
    assert analyzer._get_location_name(sample_row, "STATE") == "California"
    assert analyzer._get_location_name(sample_row, "CITY") == "San Francisco"
    assert analyzer._get_location_name(sample_row, "ZIP_CODE") == "94102"

    # Test default (unknown level should default to city)
    assert analyzer._get_location_name(sample_row, "UNKNOWN") == "San Francisco"


@pytest.mark.asyncio
async def test_analyze_with_campaign_filter(analyzer, mock_api_client, sample_geo_data):
    """Test analysis with campaign ID filter."""
    mock_api_client.get_geographic_performance = AsyncMock(return_value=sample_geo_data)
    mock_api_client.get_distance_performance = AsyncMock(return_value=[])

    campaign_ids = ["123456", "789012"]

    await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
        campaign_ids=campaign_ids,
    )

    # Verify campaign filter was passed to API
    mock_api_client.get_geographic_performance.assert_called_once()
    call_args = mock_api_client.get_geographic_performance.call_args
    assert call_args.kwargs["campaign_ids"] == campaign_ids


@pytest.mark.asyncio
async def test_analyze_empty_data(analyzer, mock_api_client):
    """Test analysis behavior with empty data."""
    mock_api_client.get_geographic_performance = AsyncMock(return_value=[])
    mock_api_client.get_distance_performance = AsyncMock(return_value=[])

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )

    assert isinstance(result, GeoPerformanceAnalysisResult)
    assert len(result.performance_data) == 0
    assert len(result.insights) == 0
    assert result.summary.total_locations == 0
    assert result.summary.total_cost == 0.0


@pytest.mark.asyncio
async def test_api_error_handling(analyzer, mock_api_client):
    """Test handling of API errors."""
    # Mock API to raise an exception
    mock_api_client.get_geographic_performance = AsyncMock(
        side_effect=Exception("API Error")
    )

    with pytest.raises(Exception, match="API Error"):
        await analyzer.analyze(
            customer_id="123456789",
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        )


def test_calculate_reallocation_potential(analyzer):
    """Test budget reallocation potential calculation."""
    # Create test data with varying CPAs
    test_data = [
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="Low CPA",
            impressions=100,
            clicks=10,
            conversions=2.0,
            cost_micros=100000000,  # $100, CPA = $50
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="High CPA",
            impressions=100,
            clicks=10,
            conversions=1.0,
            cost_micros=200000000,  # $200, CPA = $200
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
    ]

    potential = analyzer._calculate_reallocation_potential(test_data)

    # Should be (200-50)/50 * 100 = 300%, but capped at 50%
    assert potential == 50.0


def test_identify_expansion_opportunities(analyzer):
    """Test identification of expansion opportunities."""
    test_data = [
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="High ROAS Location",
            impressions=100,
            clicks=10,
            conversions=5.0,  # 5 conversions (above threshold)
            cost_micros=100000000,  # $100
            revenue_micros=400000000,  # $400, ROAS = 4.0 (above 3.0)
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123",
            campaign_id="456",
            campaign_name="Test",
            geographic_level=GeographicLevel.CITY,
            location_name="Low ROAS Location",
            impressions=100,
            clicks=10,
            conversions=1.0,  # Only 1 conversion
            cost_micros=100000000,  # $100
            revenue_micros=150000000,  # $150, ROAS = 1.5 (below 3.0)
            start_date=datetime.now(),
            end_date=datetime.now(),
        ),
    ]

    opportunities = analyzer._identify_expansion_opportunities(test_data)

    assert len(opportunities) == 1
    assert "High ROAS Location" in opportunities
    assert "Low ROAS Location" not in opportunities


def test_analyzer_name_and_description(analyzer):
    """Test analyzer name and description methods."""
    assert analyzer.get_name() == "geo_performance"
    assert "geographic performance" in analyzer.get_description().lower()
    assert "location-based" in analyzer.get_description().lower()


def test_get_budget_recommendation(analyzer):
    """Test budget recommendation logic."""
    # High score, low cost share - should recommend increase
    rec = analyzer._get_budget_recommendation(85, 0.15)
    assert "Increase budget by 20-50%" in rec

    # Low score, high cost share - should recommend decrease
    rec = analyzer._get_budget_recommendation(35, 0.15)
    assert "Decrease budget by 30-50%" in rec

    # Medium-high score - should maintain
    rec = analyzer._get_budget_recommendation(65, 0.1)
    assert "Maintain current budget" in rec

    # Low score, low cost share - should recommend redistribution
    rec = analyzer._get_budget_recommendation(45, 0.05)
    assert "redistributing budget" in rec


def test_get_targeting_recommendation(analyzer):
    """Test targeting recommendation logic."""
    test_data = GeoPerformanceData(
        customer_id="123",
        campaign_id="456",
        campaign_name="Test",
        geographic_level=GeographicLevel.CITY,
        location_name="Test City",
        impressions=100,
        clicks=10,
        conversions=1.0,
        cost_micros=100000000,
        start_date=datetime.now(),
        end_date=datetime.now(),
    )

    # Low score - should recommend exclusion
    rec = analyzer._get_targeting_recommendation(35, test_data)
    assert "excluding Test City" in rec

    # High score - should recommend bid increase
    rec = analyzer._get_targeting_recommendation(85, test_data)
    assert "increasing bid modifiers for Test City" in rec

    # Medium score - should recommend monitoring
    rec = analyzer._get_targeting_recommendation(65, test_data)
    assert "Monitor performance" in rec


def test_create_dashboard_metrics(analyzer):
    """Test dashboard metrics creation."""
    # Create test summary
    summary = GeoPerformanceSummary(
        customer_id="123",
        analysis_date=datetime.now(),
        date_range_start=datetime.now() - timedelta(days=30),
        date_range_end=datetime.now(),
        total_locations=5,
        total_cost=1000.0,
        total_conversions=10.0,
        average_cpa=100.0,
        average_roas=2.5,
        budget_reallocation_potential=25.0,
    )

    # Create test insights
    insights = [
        LocationInsight(
            location_name="Top Location",
            geographic_level=GeographicLevel.CITY,
            performance_score=90.0,
            cpa_vs_average=0.8,
            roas_vs_average=1.3,
            conversion_rate_vs_average=1.2,
            impression_share=0.25,
            cost_share=0.2,
            conversion_share=0.3,
            recommended_action="INCREASE_BUDGET",
            budget_recommendation="Increase budget",
            targeting_recommendation="Increase bids",
        ),
        LocationInsight(
            location_name="Mid Location",
            geographic_level=GeographicLevel.CITY,
            performance_score=60.0,
            cpa_vs_average=1.0,
            roas_vs_average=1.0,
            conversion_rate_vs_average=1.0,
            impression_share=0.2,
            cost_share=0.2,
            conversion_share=0.2,
            recommended_action="MAINTAIN_CURRENT",
            budget_recommendation="Maintain budget",
            targeting_recommendation="Monitor",
        ),
        LocationInsight(
            location_name="Bottom Location",
            geographic_level=GeographicLevel.CITY,
            performance_score=30.0,
            cpa_vs_average=1.5,
            roas_vs_average=0.7,
            conversion_rate_vs_average=0.8,
            impression_share=0.15,
            cost_share=0.25,
            conversion_share=0.1,
            recommended_action="DECREASE_BUDGET",
            budget_recommendation="Decrease budget",
            targeting_recommendation="Exclude location",
        ),
    ]

    metrics = analyzer._create_dashboard_metrics(summary, insights)

    assert metrics["total_locations"] == 5.0
    assert metrics["average_cpa"] == 100.0
    assert metrics["average_roas"] == 2.5
    assert metrics["budget_reallocation_potential"] == 25.0
    assert metrics["top_performer_score"] == 90.0
    assert metrics["bottom_performer_score"] == 30.0
    assert metrics["performance_spread"] == 60.0
    assert metrics["high_performers_count"] == 1.0
    assert metrics["underperformers_count"] == 1.0


def test_generate_recommendations_comprehensive(analyzer):
    """Test comprehensive recommendation generation."""
    # Create insights with various performance levels
    insights = [
        LocationInsight(
            location_name=f"High Performer {i}",
            geographic_level=GeographicLevel.CITY,
            performance_score=85.0 + i,
            cpa_vs_average=0.7,
            roas_vs_average=1.5,
            conversion_rate_vs_average=1.3,
            impression_share=0.15,
            cost_share=0.1,
            conversion_share=0.2,
            recommended_action="INCREASE_BUDGET",
            budget_recommendation="Increase budget",
            targeting_recommendation="Increase bids",
        )
        for i in range(3)
    ] + [
        LocationInsight(
            location_name=f"Low Performer {i}",
            geographic_level=GeographicLevel.CITY,
            performance_score=30.0 - i,
            cpa_vs_average=1.8,
            roas_vs_average=0.6,
            conversion_rate_vs_average=0.7,
            impression_share=0.1,
            cost_share=0.15,
            conversion_share=0.05,
            recommended_action="DECREASE_BUDGET",
            budget_recommendation="Decrease budget",
            targeting_recommendation="Exclude location",
        )
        for i in range(3)
    ]

    summary = GeoPerformanceSummary(
        customer_id="123",
        analysis_date=datetime.now(),
        date_range_start=datetime.now() - timedelta(days=30),
        date_range_end=datetime.now(),
        total_locations=6,
        total_cost=2000.0,
        total_conversions=20.0,
        average_cpa=100.0,
        average_roas=2.0,
        budget_reallocation_potential=35.0,
        expansion_opportunities=["New York", "Los Angeles", "Chicago"],
    )

    recommendations = analyzer._generate_recommendations(insights, summary)

    # Should have recommendations for all scenarios
    assert len(recommendations) == 4
    assert any("top-performing locations" in r for r in recommendations)
    assert any("underperforming locations" in r for r in recommendations)
    assert any("35.0% improvement" in r for r in recommendations)
    assert any("expanding to high-performing locations" in r for r in recommendations)


@pytest.mark.asyncio
async def test_analyze_with_distance_performance(
    analyzer, mock_api_client, sample_geo_data, sample_distance_data
):
    """Test analysis including distance performance data."""
    mock_api_client.get_geographic_performance = AsyncMock(return_value=sample_geo_data)
    mock_api_client.get_distance_performance = AsyncMock(
        return_value=sample_distance_data
    )

    result = await analyzer.analyze(
        customer_id="123456789",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
    )

    # Currently returns None for distance analysis, but API should be called
    mock_api_client.get_distance_performance.assert_called_once()
    assert result.distance_analysis is None


def test_empty_insights_dashboard_metrics(analyzer):
    """Test dashboard metrics with empty insights."""
    summary = GeoPerformanceSummary(
        customer_id="123",
        analysis_date=datetime.now(),
        date_range_start=datetime.now() - timedelta(days=30),
        date_range_end=datetime.now(),
        total_locations=0,
        total_cost=0.0,
        total_conversions=0.0,
        average_cpa=0.0,
        average_roas=0.0,
    )

    metrics = analyzer._create_dashboard_metrics(summary, [])

    assert metrics["total_locations"] == 0.0
    assert metrics["top_performer_score"] == 0.0
    assert metrics["bottom_performer_score"] == 0.0
    assert metrics["performance_spread"] == 0.0
    assert metrics["high_performers_count"] == 0.0
    assert metrics["underperformers_count"] == 0.0
