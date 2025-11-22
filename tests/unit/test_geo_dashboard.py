"""Tests for geographic performance dashboard."""

from datetime import datetime, timedelta
from unittest.mock import MagicMock

import pytest

from paidsearchnav.core.models import (
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    GeoPerformanceSummary,
    LocationInsight,
)
from paidsearchnav.dashboards.geo_dashboard import GeoDashboard


@pytest.fixture
def sample_performance_data():
    """Create sample geographic performance data."""
    return [
        GeoPerformanceData(
            customer_id="123456789",
            campaign_id="campaign_1",
            campaign_name="Test Campaign 1",
            geographic_level=GeographicLevel.CITY,
            location_name="San Francisco",
            country_code="US",
            region_code="CA",
            city="San Francisco",
            zip_code="94102",
            impressions=1000,
            clicks=50,
            conversions=5.0,
            cost_micros=250000000,  # $250
            revenue_micros=500000000,  # $500
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123456789",
            campaign_id="campaign_1",
            campaign_name="Test Campaign 1",
            geographic_level=GeographicLevel.CITY,
            location_name="Los Angeles",
            country_code="US",
            region_code="CA",
            city="Los Angeles",
            zip_code="90210",
            impressions=800,
            clicks=40,
            conversions=2.0,
            cost_micros=200000000,  # $200
            revenue_micros=300000000,  # $300
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        ),
        GeoPerformanceData(
            customer_id="123456789",
            campaign_id="campaign_1",
            campaign_name="Test Campaign 1",
            geographic_level=GeographicLevel.CITY,
            location_name="New York",
            country_code="US",
            region_code="NY",
            city="New York",
            zip_code="10001",
            impressions=500,
            clicks=25,
            conversions=1.0,
            cost_micros=150000000,  # $150
            revenue_micros=100000000,  # $100
            start_date=datetime.now() - timedelta(days=30),
            end_date=datetime.now(),
        ),
    ]


@pytest.fixture
def sample_insights():
    """Create sample location insights."""
    return [
        LocationInsight(
            location_name="San Francisco",
            geographic_level=GeographicLevel.CITY,
            performance_score=85.0,
            cpa_vs_average=0.7,  # 30% better than average
            roas_vs_average=1.5,  # 50% better than average
            conversion_rate_vs_average=1.2,  # 20% better than average
            impression_share=0.4,  # 40% of impressions
            cost_share=0.35,  # 35% of cost
            conversion_share=0.5,  # 50% of conversions
            recommended_action="INCREASE_BUDGET",
            budget_recommendation="Increase budget by 20-50%",
            targeting_recommendation="Consider increasing bid modifiers for San Francisco",
        ),
        LocationInsight(
            location_name="Los Angeles",
            geographic_level=GeographicLevel.CITY,
            performance_score=65.0,
            cpa_vs_average=1.1,  # 10% worse than average
            roas_vs_average=0.9,  # 10% worse than average
            conversion_rate_vs_average=0.8,  # 20% worse than average
            impression_share=0.35,  # 35% of impressions
            cost_share=0.4,  # 40% of cost
            conversion_share=0.3,  # 30% of conversions
            recommended_action="MAINTAIN_CURRENT",
            budget_recommendation="Maintain current budget",
            targeting_recommendation="Monitor performance and adjust targeting as needed",
        ),
        LocationInsight(
            location_name="New York",
            geographic_level=GeographicLevel.CITY,
            performance_score=30.0,
            cpa_vs_average=2.0,  # 100% worse than average
            roas_vs_average=0.5,  # 50% worse than average
            conversion_rate_vs_average=0.6,  # 40% worse than average
            impression_share=0.25,  # 25% of impressions
            cost_share=0.25,  # 25% of cost
            conversion_share=0.2,  # 20% of conversions
            recommended_action="DECREASE_BUDGET",
            budget_recommendation="Decrease budget by 30-50%",
            targeting_recommendation="Consider excluding New York or adjusting bid modifiers",
        ),
    ]


@pytest.fixture
def sample_summary():
    """Create sample performance summary."""
    return GeoPerformanceSummary(
        customer_id="123456789",
        analysis_date=datetime.now(),
        date_range_start=datetime.now() - timedelta(days=30),
        date_range_end=datetime.now(),
        total_locations=3,
        total_cost=600.0,  # $250 + $200 + $150
        total_conversions=8.0,  # 5 + 2 + 1
        average_cpa=75.0,  # $600 / 8 conversions
        average_roas=1.5,  # Average of 2.0, 1.5, 0.67
        location_distribution={"CITY": 3},
        budget_reallocation_potential=25.0,
        expansion_opportunities=["San Francisco"],
    )


@pytest.fixture
def sample_analysis_result(sample_performance_data, sample_insights, sample_summary):
    """Create sample analysis result."""
    return GeoPerformanceAnalysisResult(
        customer_id="123456789",
        analyzer_name="geo_performance",
        start_date=datetime.now() - timedelta(days=30),
        end_date=datetime.now(),
        performance_data=sample_performance_data,
        summary=sample_summary,
        insights=sample_insights,
        geo_recommendations=[
            "Increase budget allocation to top-performing locations: San Francisco"
        ],
        dashboard_metrics={
            "total_locations": 3.0,
            "average_cpa": 75.0,
            "average_roas": 1.5,
            "budget_reallocation_potential": 25.0,
            "top_performer_score": 85.0,
            "bottom_performer_score": 30.0,
            "performance_spread": 55.0,
            "high_performers_count": 1.0,
            "underperformers_count": 1.0,
        },
    )


@pytest.fixture
def dashboard():
    """Create a dashboard instance."""
    return GeoDashboard()


def test_dashboard_initialization(dashboard):
    """Test dashboard initialization."""
    assert dashboard.analysis_result is None


def test_load_analysis(dashboard, sample_analysis_result):
    """Test loading analysis into dashboard."""
    dashboard.load_analysis(sample_analysis_result)

    assert dashboard.analysis_result == sample_analysis_result


def test_get_overview_metrics_empty(dashboard):
    """Test getting overview metrics with no data loaded."""
    metrics = dashboard.get_overview_metrics()
    assert metrics == {}


def test_get_overview_metrics_with_data(dashboard, sample_analysis_result):
    """Test getting overview metrics with data loaded."""
    dashboard.load_analysis(sample_analysis_result)

    metrics = dashboard.get_overview_metrics()

    assert metrics["total_locations"] == 3
    assert metrics["total_cost"] == 600.0
    assert metrics["total_conversions"] == 8.0
    assert metrics["average_cpa"] == 75.0
    assert metrics["average_roas"] == 1.5
    assert metrics["budget_reallocation_potential"] == 25.0
    assert "analysis_date" in metrics
    assert "date_range" in metrics
    assert "start" in metrics["date_range"]
    assert "end" in metrics["date_range"]


def test_get_performance_map_data(dashboard, sample_analysis_result):
    """Test getting performance map data."""
    dashboard.load_analysis(sample_analysis_result)

    map_data = dashboard.get_performance_map_data()

    assert len(map_data) == 3

    # Test first location (San Francisco)
    sf_data = map_data[0]
    assert sf_data["location_name"] == "San Francisco"
    assert sf_data["geographic_level"] == "CITY"
    assert sf_data["country"] == "US"
    assert sf_data["region"] == "CA"
    assert sf_data["city"] == "San Francisco"
    assert sf_data["zip_code"] == "94102"
    assert sf_data["latitude"] is None  # Would need geocoding
    assert sf_data["longitude"] is None  # Would need geocoding

    # Test metrics
    metrics = sf_data["metrics"]
    assert metrics["impressions"] == 1000
    assert metrics["clicks"] == 50
    assert metrics["conversions"] == 5.0
    assert metrics["cost"] == 250.0
    assert metrics["revenue"] == 500.0
    assert metrics["ctr"] == 0.05  # 50/1000
    assert metrics["cpa"] == 50.0  # 250/5
    assert metrics["roas"] == 2.0  # 500/250


def test_get_top_performers(dashboard, sample_analysis_result):
    """Test getting top performing locations."""
    dashboard.load_analysis(sample_analysis_result)

    top_performers = dashboard.get_top_performers(limit=5)

    assert len(top_performers) >= 1

    # Should be sorted by performance score (highest first)
    if len(top_performers) > 1:
        for i in range(len(top_performers) - 1):
            assert (
                top_performers[i]["performance_score"]
                >= top_performers[i + 1]["performance_score"]
            )

    # Check first performer (should be San Francisco)
    top_performer = top_performers[0]
    assert top_performer["location_name"] == "San Francisco"
    assert top_performer["performance_score"] == 85.0
    assert top_performer["geographic_level"] == "CITY"
    assert "shares" in top_performer
    assert "recommendations" in top_performer


def test_get_underperformers(dashboard, sample_analysis_result):
    """Test getting underperforming locations."""
    dashboard.load_analysis(sample_analysis_result)

    underperformers = dashboard.get_underperformers(limit=5)

    assert len(underperformers) >= 1

    # Should be sorted by performance score (lowest first)
    if len(underperformers) > 1:
        for i in range(len(underperformers) - 1):
            assert (
                underperformers[i]["performance_score"]
                <= underperformers[i + 1]["performance_score"]
            )

    # Check first underperformer (should be New York)
    underperformer = underperformers[0]
    assert underperformer["location_name"] == "New York"
    assert underperformer["performance_score"] == 30.0


def test_get_performance_distribution(dashboard, sample_analysis_result):
    """Test getting performance distribution data."""
    dashboard.load_analysis(sample_analysis_result)

    distribution = dashboard.get_performance_distribution()

    assert "buckets" in distribution
    assert "total_locations" in distribution
    assert "average_score" in distribution
    assert "median_score" in distribution

    buckets = distribution["buckets"]
    assert buckets["excellent"] == 1  # San Francisco (85)
    assert buckets["good"] == 1  # Los Angeles (65)
    assert buckets["average"] == 0  # None between 40-60
    assert buckets["poor"] == 1  # New York (30)

    assert distribution["total_locations"] == 3
    assert abs(distribution["average_score"] - 60.0) < 1.0  # (85 + 65 + 30) / 3


def test_get_cost_efficiency_chart_data(dashboard, sample_analysis_result):
    """Test getting cost efficiency chart data."""
    dashboard.load_analysis(sample_analysis_result)

    chart_data = dashboard.get_cost_efficiency_chart_data()

    assert len(chart_data) == 3

    # Should be sorted by cost (highest first)
    assert chart_data[0]["cost"] >= chart_data[1]["cost"] >= chart_data[2]["cost"]

    # Test data structure
    for item in chart_data:
        assert "location" in item
        assert "cost" in item
        assert "cpa" in item
        assert "roas" in item
        assert "conversions" in item
        assert "performance_score" in item


def test_get_recommendations_summary(dashboard, sample_analysis_result):
    """Test getting recommendations summary."""
    dashboard.load_analysis(sample_analysis_result)

    recommendations = dashboard.get_recommendations_summary()

    assert "total_recommendations" in recommendations
    assert "action_breakdown" in recommendations
    assert "top_recommendations" in recommendations
    assert "expansion_opportunities" in recommendations

    assert recommendations["total_recommendations"] == 1
    assert len(recommendations["top_recommendations"]) <= 5

    # Check action breakdown
    action_breakdown = recommendations["action_breakdown"]
    assert "INCREASE_BUDGET" in action_breakdown
    assert "MAINTAIN_CURRENT" in action_breakdown
    assert "DECREASE_BUDGET" in action_breakdown


def test_get_budget_allocation_data(dashboard, sample_analysis_result):
    """Test getting budget allocation data."""
    dashboard.load_analysis(sample_analysis_result)

    allocation_data = dashboard.get_budget_allocation_data()

    assert len(allocation_data) == 3

    # Should be sorted by current cost (highest first)
    assert (
        allocation_data[0]["current_cost"]
        >= allocation_data[1]["current_cost"]
        >= allocation_data[2]["current_cost"]
    )

    # Test data structure
    for item in allocation_data:
        assert "location" in item
        assert "current_share" in item
        assert "recommended_share" in item
        assert "performance_score" in item
        assert "current_cost" in item

    # Test recommendations logic
    # San Francisco (score 85) should get budget increase
    sf_item = next(
        item for item in allocation_data if item["location"] == "San Francisco"
    )
    assert sf_item["recommended_share"] > sf_item["current_share"]

    # New York (score 30) should get budget decrease
    ny_item = next(item for item in allocation_data if item["location"] == "New York")
    assert ny_item["recommended_share"] < ny_item["current_share"]


def test_export_dashboard_data(dashboard, sample_analysis_result):
    """Test exporting complete dashboard data."""
    dashboard.load_analysis(sample_analysis_result)

    export_data = dashboard.export_dashboard_data()

    # Check all expected sections are present
    expected_sections = [
        "overview",
        "map_data",
        "top_performers",
        "underperformers",
        "performance_distribution",
        "cost_efficiency",
        "recommendations",
        "budget_allocation",
        "metadata",
    ]

    for section in expected_sections:
        assert section in export_data

    # Check metadata
    metadata = export_data["metadata"]
    assert metadata["customer_id"] == "123456789"
    assert metadata["analyzer_name"] == "geo_performance"
    assert "generated_at" in metadata


def test_format_insight_for_dashboard(dashboard, sample_insights):
    """Test formatting insight for dashboard display."""
    insight = sample_insights[0]  # San Francisco

    formatted = dashboard._format_insight_for_dashboard(insight)

    assert formatted["location_name"] == "San Francisco"
    assert formatted["geographic_level"] == "CITY"
    assert formatted["performance_score"] == 85.0
    assert formatted["cpa_vs_average"] == 0.7
    assert formatted["roas_vs_average"] == 1.5

    # Check shares are converted to percentages
    shares = formatted["shares"]
    assert shares["impression"] == 40.0  # 0.4 * 100
    assert shares["cost"] == 35.0  # 0.35 * 100
    assert shares["conversion"] == 50.0  # 0.5 * 100

    # Check recommendations
    recommendations = formatted["recommendations"]
    assert recommendations["action"] == "INCREASE_BUDGET"
    assert "budget" in recommendations
    assert "targeting" in recommendations


def test_generate_html_dashboard_empty(dashboard):
    """Test HTML generation with no data."""
    html = dashboard.generate_html_dashboard()
    assert "No analysis data loaded" in html


def test_generate_html_dashboard_with_data(dashboard, sample_analysis_result):
    """Test HTML generation with data."""
    dashboard.load_analysis(sample_analysis_result)

    html = dashboard.generate_html_dashboard()

    # Check basic HTML structure
    assert "<!DOCTYPE html>" in html
    assert "<html" in html
    assert "</html>" in html
    assert "Geographic Performance Dashboard" in html

    # Check customer ID is displayed
    assert "123456789" in html

    # Check key metrics are displayed
    assert "Total Locations" in html
    assert "Total Cost" in html
    assert "Total Conversions" in html
    assert "Average CPA" in html

    # Check location names are displayed
    assert "San Francisco" in html
    assert "Los Angeles" in html
    assert "New York" in html


def test_generate_location_list_html(dashboard, sample_insights):
    """Test HTML generation for location lists."""
    dashboard.analysis_result = MagicMock()  # Mock to enable method call

    formatted_insights = [
        dashboard._format_insight_for_dashboard(insight) for insight in sample_insights
    ]

    html = dashboard._generate_location_list_html(formatted_insights)

    # Check that all locations are included
    assert "San Francisco" in html
    assert "Los Angeles" in html
    assert "New York" in html

    # Check performance scores are displayed
    assert "85.0" in html  # San Francisco score
    assert "65.0" in html  # Los Angeles score
    assert "30.0" in html  # New York score

    # Check CSS classes for score colors
    assert "score-excellent" in html  # For San Francisco (85)
    assert "score-good" in html  # For Los Angeles (65)
    assert "score-poor" in html  # For New York (30)


def test_generate_recommendations_html(dashboard):
    """Test HTML generation for recommendations."""
    recommendations = [
        "Increase budget allocation to top-performing locations: San Francisco",
        "Consider reducing spend or excluding underperforming locations: New York",
        "Potential 25.0% improvement through budget reallocation",
    ]

    html = dashboard._generate_recommendations_html(recommendations)

    # Check all recommendations are included as list items
    assert html.count("<li>") == 3
    assert html.count("</li>") == 3

    for rec in recommendations:
        assert rec in html
