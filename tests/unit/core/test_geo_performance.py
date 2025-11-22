"""Tests for geographic performance data models."""

from datetime import datetime, timezone

import pytest
from pydantic import ValidationError

from paidsearchnav_mcp.models.geo_performance import (
    DistancePerformanceData,
    GeographicLevel,
    GeoPerformanceAnalysisResult,
    GeoPerformanceData,
    GeoPerformanceSummary,
    LocationInsight,
)


@pytest.fixture
def sample_geo_data():
    """Fixture for common geo performance data."""
    return {
        "customer_id": "1234567890",
        "campaign_id": "789012",
        "campaign_name": "Test Campaign",
        "geographic_level": GeographicLevel.CITY,
        "location_name": "New York, NY",
        "start_date": datetime.now(timezone.utc),
        "end_date": datetime.now(timezone.utc),
    }


@pytest.fixture
def sample_location_insight():
    """Fixture for common location insight data."""
    return {
        "location_name": "New York, NY",
        "geographic_level": GeographicLevel.CITY,
        "performance_score": 85.0,
        "cpa_vs_average": 0.8,
        "roas_vs_average": 1.2,
        "conversion_rate_vs_average": 1.1,
        "impression_share": 0.15,
        "cost_share": 0.12,
        "conversion_share": 0.18,
        "recommended_action": "Increase budget allocation",
    }


class TestGeographicLevel:
    """Test GeographicLevel enum."""

    def test_all_geographic_levels(self) -> None:
        """Test all geographic levels are defined."""
        expected_levels = ["COUNTRY", "STATE", "CITY", "ZIP_CODE", "RADIUS"]

        for level in expected_levels:
            assert GeographicLevel(level) == level

    def test_invalid_geographic_level(self) -> None:
        """Test invalid geographic level raises error."""
        with pytest.raises(ValueError):
            GeographicLevel("INVALID_LEVEL")


class TestGeoPerformanceData:
    """Test GeoPerformanceData model."""

    def test_basic_geo_performance_data(self, sample_geo_data) -> None:
        """Test creating basic geo performance data."""
        geo_data = GeoPerformanceData(**sample_geo_data)

        assert geo_data.customer_id == "1234567890"
        assert geo_data.campaign_id == "789012"
        assert geo_data.campaign_name == "Test Campaign"
        assert geo_data.geographic_level == GeographicLevel.CITY
        assert geo_data.location_name == "New York, NY"
        assert geo_data.location_id is None
        assert geo_data.impressions == 0
        assert geo_data.clicks == 0
        assert geo_data.conversions == 0.0
        assert geo_data.cost_micros == 0
        assert geo_data.revenue_micros is None

    def test_geo_data_with_location_details(self) -> None:
        """Test geo data with full location details."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="San Francisco, CA",
            location_id="1014221",
            country_code="US",
            region_code="CA",
            city="San Francisco",
            zip_code="94105",
            start_date=now,
            end_date=now,
        )

        assert geo_data.location_id == "1014221"
        assert geo_data.country_code == "US"
        assert geo_data.region_code == "CA"
        assert geo_data.city == "San Francisco"
        assert geo_data.zip_code == "94105"

    def test_geo_data_with_distance_metrics(self) -> None:
        """Test geo data with distance-based metrics."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="5 miles from Store #123",
            distance_miles=5.0,
            business_location="Store #123 - Main St",
            start_date=now,
            end_date=now,
        )

        assert geo_data.distance_miles == 5.0
        assert geo_data.business_location == "Store #123 - Main St"

    def test_geo_data_with_performance_metrics(self) -> None:
        """Test geo data with performance metrics."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.STATE,
            location_name="California",
            impressions=100000,
            clicks=5000,
            conversions=250.0,
            cost_micros=500000000,  # $500
            revenue_micros=25000000000,  # $25,000
            start_date=now,
            end_date=now,
        )

        assert geo_data.impressions == 100000
        assert geo_data.clicks == 5000
        assert geo_data.conversions == 250.0
        assert geo_data.cost_micros == 500000000
        assert geo_data.revenue_micros == 25000000000

    def test_cost_property(self) -> None:
        """Test cost property conversion from micros."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=1234567890,  # $1,234.56789
            start_date=now,
            end_date=now,
        )

        assert geo_data.cost == 1234.56789

    def test_revenue_property(self) -> None:
        """Test revenue property conversion from micros."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            revenue_micros=9876543210,  # $9,876.54321
            start_date=now,
            end_date=now,
        )

        assert geo_data.revenue == 9876.54321

    def test_revenue_property_none(self) -> None:
        """Test revenue property when revenue_micros is None."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            revenue_micros=None,
            start_date=now,
            end_date=now,
        )

        assert geo_data.revenue == 0.0

    def test_ctr_calculation(self) -> None:
        """Test CTR calculation."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            impressions=10000,
            clicks=500,
            start_date=now,
            end_date=now,
        )

        assert geo_data.ctr == 0.05  # 5%

    def test_ctr_zero_impressions(self) -> None:
        """Test CTR calculation with zero impressions."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            impressions=0,
            clicks=0,
            start_date=now,
            end_date=now,
        )

        assert geo_data.ctr == 0.0

    def test_cpa_calculation(self) -> None:
        """Test CPA calculation."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=100000000,  # $100
            conversions=10.0,
            start_date=now,
            end_date=now,
        )

        assert geo_data.cpa == 10.0  # $10 per conversion

    def test_cpa_zero_conversions(self) -> None:
        """Test CPA calculation with zero conversions."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=100000000,
            conversions=0.0,
            start_date=now,
            end_date=now,
        )

        assert geo_data.cpa == 0.0

    def test_roas_calculation(self) -> None:
        """Test ROAS calculation."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=100000000,  # $100
            revenue_micros=500000000,  # $500
            start_date=now,
            end_date=now,
        )

        assert geo_data.roas == 5.0  # 5:1 ROAS

    def test_roas_zero_cost(self) -> None:
        """Test ROAS calculation with zero cost."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=0,
            revenue_micros=500000000,
            start_date=now,
            end_date=now,
        )

        assert geo_data.roas == 0.0

    def test_roas_no_revenue(self) -> None:
        """Test ROAS calculation with no revenue."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            cost_micros=100000000,
            revenue_micros=None,
            start_date=now,
            end_date=now,
        )

        assert geo_data.roas == 0.0

    def test_conversion_rate_calculation(self) -> None:
        """Test conversion rate calculation."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            clicks=1000,
            conversions=50.0,
            start_date=now,
            end_date=now,
        )

        assert geo_data.conversion_rate == 0.05  # 5%

    def test_conversion_rate_zero_clicks(self) -> None:
        """Test conversion rate calculation with zero clicks."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            clicks=0,
            conversions=0.0,
            start_date=now,
            end_date=now,
        )

        assert geo_data.conversion_rate == 0.0

    def test_different_geographic_levels(self) -> None:
        """Test different geographic level configurations."""
        now = datetime.now(timezone.utc)

        # Country level
        country_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.COUNTRY,
            location_name="United States",
            country_code="US",
            start_date=now,
            end_date=now,
        )
        assert country_data.geographic_level == GeographicLevel.COUNTRY

        # State level
        state_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.STATE,
            location_name="Texas",
            country_code="US",
            region_code="TX",
            start_date=now,
            end_date=now,
        )
        assert state_data.geographic_level == GeographicLevel.STATE

        # ZIP code level
        zip_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.ZIP_CODE,
            location_name="10001",
            zip_code="10001",
            start_date=now,
            end_date=now,
        )
        assert zip_data.geographic_level == GeographicLevel.ZIP_CODE


class TestLocationInsight:
    """Test LocationInsight model."""

    def test_basic_location_insight(self) -> None:
        """Test creating basic location insight."""
        insight = LocationInsight(
            location_name="New York, NY",
            geographic_level=GeographicLevel.CITY,
            performance_score=85.5,
            cpa_vs_average=0.8,  # 20% better than average
            roas_vs_average=1.2,  # 20% better than average
            conversion_rate_vs_average=1.1,  # 10% better than average
            impression_share=0.15,  # 15% of impressions
            cost_share=0.12,  # 12% of cost
            conversion_share=0.18,  # 18% of conversions
            recommended_action="Increase budget allocation",
        )

        assert insight.location_name == "New York, NY"
        assert insight.geographic_level == GeographicLevel.CITY
        assert insight.performance_score == 85.5
        assert insight.cpa_vs_average == 0.8
        assert insight.roas_vs_average == 1.2
        assert insight.conversion_rate_vs_average == 1.1
        assert insight.impression_share == 0.15
        assert insight.cost_share == 0.12
        assert insight.conversion_share == 0.18
        assert insight.recommended_action == "Increase budget allocation"
        assert insight.budget_recommendation is None
        assert insight.targeting_recommendation is None

    def test_location_insight_with_recommendations(self) -> None:
        """Test location insight with detailed recommendations."""
        insight = LocationInsight(
            location_name="Los Angeles, CA",
            geographic_level=GeographicLevel.CITY,
            performance_score=45.0,
            cpa_vs_average=1.5,  # 50% worse than average
            roas_vs_average=0.7,  # 30% worse than average
            conversion_rate_vs_average=0.8,  # 20% worse than average
            impression_share=0.25,
            cost_share=0.30,
            conversion_share=0.20,
            recommended_action="Review targeting and messaging",
            budget_recommendation="Reduce budget by 20%",
            targeting_recommendation="Exclude low-performing ZIP codes",
        )

        assert insight.budget_recommendation == "Reduce budget by 20%"
        assert insight.targeting_recommendation == "Exclude low-performing ZIP codes"

    def test_perfect_performance_insight(self) -> None:
        """Test location insight with perfect performance."""
        insight = LocationInsight(
            location_name="Chicago, IL",
            geographic_level=GeographicLevel.CITY,
            performance_score=100.0,
            cpa_vs_average=0.5,  # 50% better than average
            roas_vs_average=2.0,  # 100% better than average
            conversion_rate_vs_average=1.5,  # 50% better than average
            impression_share=0.10,
            cost_share=0.05,
            conversion_share=0.15,
            recommended_action="Maintain current strategy",
        )

        assert insight.performance_score == 100.0
        assert insight.cpa_vs_average == 0.5

    def test_underperforming_location_insight(self) -> None:
        """Test location insight for underperforming location."""
        insight = LocationInsight(
            location_name="Rural Areas",
            geographic_level=GeographicLevel.STATE,
            performance_score=25.0,
            cpa_vs_average=3.0,  # 3x worse than average
            roas_vs_average=0.3,  # 70% worse than average
            conversion_rate_vs_average=0.4,  # 60% worse than average
            impression_share=0.05,
            cost_share=0.10,
            conversion_share=0.02,
            recommended_action="Consider excluding from targeting",
            budget_recommendation="Reallocate budget to better performing areas",
        )

        assert insight.performance_score == 25.0
        assert insight.cpa_vs_average == 3.0
        assert insight.recommended_action == "Consider excluding from targeting"


class TestGeoPerformanceSummary:
    """Test GeoPerformanceSummary model."""

    def test_basic_summary(self) -> None:
        """Test creating basic geo performance summary."""
        now = datetime.now(timezone.utc)
        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=50,
            total_cost=10000.0,
            total_conversions=500.0,
            average_cpa=20.0,
            average_roas=5.0,
        )

        assert summary.customer_id == "1234567890"
        assert summary.analysis_date == now
        assert summary.total_locations == 50
        assert summary.total_cost == 10000.0
        assert summary.total_conversions == 500.0
        assert summary.average_cpa == 20.0
        assert summary.average_roas == 5.0
        assert summary.top_performing_locations == []
        assert summary.underperforming_locations == []
        assert summary.location_distribution == {}
        assert summary.budget_reallocation_potential == 0.0
        assert summary.expansion_opportunities == []

    def test_summary_with_insights(self) -> None:
        """Test summary with location insights."""
        now = datetime.now(timezone.utc)

        top_location = LocationInsight(
            location_name="New York, NY",
            geographic_level=GeographicLevel.CITY,
            performance_score=90.0,
            cpa_vs_average=0.7,
            roas_vs_average=1.3,
            conversion_rate_vs_average=1.2,
            impression_share=0.20,
            cost_share=0.15,
            conversion_share=0.25,
            recommended_action="Increase investment",
        )

        underperforming_location = LocationInsight(
            location_name="Rural Texas",
            geographic_level=GeographicLevel.STATE,
            performance_score=30.0,
            cpa_vs_average=2.5,
            roas_vs_average=0.4,
            conversion_rate_vs_average=0.5,
            impression_share=0.10,
            cost_share=0.15,
            conversion_share=0.05,
            recommended_action="Reduce or exclude",
        )

        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=50,
            total_cost=10000.0,
            total_conversions=500.0,
            average_cpa=20.0,
            average_roas=5.0,
            top_performing_locations=[top_location],
            underperforming_locations=[underperforming_location],
        )

        assert len(summary.top_performing_locations) == 1
        assert summary.top_performing_locations[0].location_name == "New York, NY"
        assert len(summary.underperforming_locations) == 1
        assert summary.underperforming_locations[0].location_name == "Rural Texas"

    def test_summary_with_distribution(self) -> None:
        """Test summary with location distribution."""
        now = datetime.now(timezone.utc)
        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=50,
            total_cost=10000.0,
            total_conversions=500.0,
            average_cpa=20.0,
            average_roas=5.0,
            location_distribution={
                "CITY": 30,
                "STATE": 10,
                "ZIP_CODE": 8,
                "COUNTRY": 2,
            },
        )

        assert summary.location_distribution["CITY"] == 30
        assert summary.location_distribution["STATE"] == 10
        assert summary.location_distribution["ZIP_CODE"] == 8
        assert summary.location_distribution["COUNTRY"] == 2

    def test_summary_with_opportunities(self) -> None:
        """Test summary with expansion opportunities."""
        now = datetime.now(timezone.utc)
        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=50,
            total_cost=10000.0,
            total_conversions=500.0,
            average_cpa=20.0,
            average_roas=5.0,
            budget_reallocation_potential=0.25,  # 25% improvement possible
            expansion_opportunities=[
                "Boston, MA - Similar to NYC performance",
                "Seattle, WA - High income demographics",
                "Miami, FL - Growing market presence",
            ],
        )

        assert summary.budget_reallocation_potential == 0.25
        assert len(summary.expansion_opportunities) == 3
        assert "Boston, MA" in summary.expansion_opportunities[0]


class TestDistancePerformanceData:
    """Test DistancePerformanceData model."""

    def test_distance_performance_data(self) -> None:
        """Test creating distance performance data."""
        now = datetime.now(timezone.utc)

        # Create performance data for each distance range
        perf_0_5 = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="0-5 miles",
            distance_miles=2.5,
            impressions=10000,
            clicks=1000,
            conversions=100.0,
            cost_micros=200000000,  # $200
            start_date=now,
            end_date=now,
        )

        perf_5_10 = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="5-10 miles",
            distance_miles=7.5,
            impressions=8000,
            clicks=600,
            conversions=50.0,
            cost_micros=150000000,  # $150
            start_date=now,
            end_date=now,
        )

        perf_10_20 = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="10-20 miles",
            distance_miles=15.0,
            impressions=5000,
            clicks=250,
            conversions=20.0,
            cost_micros=100000000,  # $100
            start_date=now,
            end_date=now,
        )

        perf_20_plus = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="20+ miles",
            distance_miles=30.0,
            impressions=2000,
            clicks=50,
            conversions=5.0,
            cost_micros=50000000,  # $50
            start_date=now,
            end_date=now,
        )

        distance_data = DistancePerformanceData(
            customer_id="1234567890",
            business_name="Main Store",
            business_address="123 Main St, New York, NY 10001",
            distance_0_5_miles=perf_0_5,
            distance_5_10_miles=perf_5_10,
            distance_10_20_miles=perf_10_20,
            distance_20_plus_miles=perf_20_plus,
            optimal_radius=7.5,
            efficiency_by_distance={
                "0-5": 0.5,  # $2 CPA
                "5-10": 0.33,  # $3 CPA
                "10-20": 0.2,  # $5 CPA
                "20+": 0.1,  # $10 CPA
            },
        )

        assert distance_data.customer_id == "1234567890"
        assert distance_data.business_name == "Main Store"
        assert distance_data.business_address == "123 Main St, New York, NY 10001"
        assert distance_data.optimal_radius == 7.5
        assert distance_data.distance_0_5_miles.conversions == 100.0
        assert distance_data.distance_5_10_miles.conversions == 50.0
        assert distance_data.distance_10_20_miles.conversions == 20.0
        assert distance_data.distance_20_plus_miles.conversions == 5.0
        assert distance_data.efficiency_by_distance["0-5"] == 0.5

    def test_distance_data_efficiency_metrics(self) -> None:
        """Test distance data with detailed efficiency metrics."""
        now = datetime.now(timezone.utc)

        # Create dummy performance data for required fields
        dummy_perf = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="dummy",
            start_date=now,
            end_date=now,
        )

        distance_data = DistancePerformanceData(
            customer_id="1234567890",
            business_name="Downtown Store",
            business_address="456 Broadway, New York, NY 10013",
            distance_0_5_miles=dummy_perf,
            distance_5_10_miles=dummy_perf,
            distance_10_20_miles=dummy_perf,
            distance_20_plus_miles=dummy_perf,
            optimal_radius=5.0,
            efficiency_by_distance={
                "0-5": 0.8,  # Very efficient
                "5-10": 0.5,  # Moderately efficient
                "10-20": 0.2,  # Less efficient
                "20+": 0.05,  # Inefficient
            },
        )

        assert distance_data.optimal_radius == 5.0
        assert distance_data.efficiency_by_distance["0-5"] == 0.8
        assert distance_data.efficiency_by_distance["20+"] == 0.05


class TestGeoPerformanceAnalysisResult:
    """Test GeoPerformanceAnalysisResult model."""

    def test_basic_analysis_result(self) -> None:
        """Test creating basic analysis result."""
        now = datetime.now(timezone.utc)

        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=25,
            total_cost=5000.0,
            total_conversions=250.0,
            average_cpa=20.0,
            average_roas=5.0,
        )

        result = GeoPerformanceAnalysisResult(
            customer_id="1234567890",
            analyzer_name="GeoPerformanceAnalyzer",
            start_date=now,
            end_date=now,
            summary=summary,
        )

        assert result.analysis_type == "geo_performance"
        assert result.customer_id == "1234567890"
        assert result.summary.total_locations == 25
        assert result.performance_data == []
        assert result.distance_analysis is None
        assert result.insights == []
        assert result.geo_recommendations == []
        assert result.dashboard_metrics == {}

    def test_complete_analysis_result(self) -> None:
        """Test complete analysis result with all data."""
        now = datetime.now(timezone.utc)

        # Create performance data
        perf_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            impressions=50000,
            clicks=2500,
            conversions=125.0,
            cost_micros=2500000000,  # $2,500
            start_date=now,
            end_date=now,
        )

        # Create location insight
        insight = LocationInsight(
            location_name="New York, NY",
            geographic_level=GeographicLevel.CITY,
            performance_score=85.0,
            cpa_vs_average=0.8,
            roas_vs_average=1.2,
            conversion_rate_vs_average=1.1,
            impression_share=0.25,
            cost_share=0.20,
            conversion_share=0.30,
            recommended_action="Increase budget",
        )

        # Create summary
        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=25,
            total_cost=12500.0,
            total_conversions=625.0,
            average_cpa=20.0,
            average_roas=5.0,
            top_performing_locations=[insight],
        )

        # Create distance analysis (simplified)
        dummy_perf = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.RADIUS,
            location_name="dummy",
            start_date=now,
            end_date=now,
        )

        distance_data = DistancePerformanceData(
            customer_id="1234567890",
            business_name="Main Store",
            business_address="123 Main St",
            distance_0_5_miles=dummy_perf,
            distance_5_10_miles=dummy_perf,
            distance_10_20_miles=dummy_perf,
            distance_20_plus_miles=dummy_perf,
            optimal_radius=10.0,
        )

        # Create complete result
        result = GeoPerformanceAnalysisResult(
            customer_id="1234567890",
            analyzer_name="GeoPerformanceAnalyzer",
            start_date=now,
            end_date=now,
            summary=summary,
            performance_data=[perf_data],
            distance_analysis=[distance_data],
            insights=[insight],
            geo_recommendations=[
                "Focus budget on top performing cities",
                "Expand radius targeting to 10 miles for urban stores",
                "Exclude underperforming rural areas",
            ],
            dashboard_metrics={
                "top_location_cpa": 16.0,
                "worst_location_cpa": 50.0,
                "location_efficiency_score": 0.75,
                "optimal_radius_miles": 10.0,
            },
        )

        assert len(result.performance_data) == 1
        assert result.performance_data[0].location_name == "New York, NY"
        assert len(result.distance_analysis) == 1
        assert result.distance_analysis[0].optimal_radius == 10.0
        assert len(result.insights) == 1
        assert result.insights[0].performance_score == 85.0
        assert len(result.geo_recommendations) == 3
        assert result.dashboard_metrics["location_efficiency_score"] == 0.75

    def test_missing_required_fields(self) -> None:
        """Test that required fields are enforced."""
        now = datetime.now(timezone.utc)

        with pytest.raises(ValidationError) as exc_info:
            GeoPerformanceAnalysisResult(
                customer_id="1234567890",
                analyzer_name="GeoPerformanceAnalyzer",
                start_date=now,
                end_date=now,
                # Missing required 'summary' field
            )

        errors = exc_info.value.errors()
        assert any(e["loc"] == ("summary",) for e in errors)


class TestEdgeCases:
    """Test edge cases and boundary conditions."""

    def test_zero_metrics_handling(self) -> None:
        """Test handling of all zero metrics."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="Ghost Town",
            impressions=0,
            clicks=0,
            conversions=0.0,
            cost_micros=0,
            revenue_micros=0,
            start_date=now,
            end_date=now,
        )

        # All calculated properties should handle zeros gracefully
        assert geo_data.cost == 0.0
        assert geo_data.revenue == 0.0
        assert geo_data.ctr == 0.0
        assert geo_data.cpa == 0.0
        assert geo_data.roas == 0.0
        assert geo_data.conversion_rate == 0.0

    def test_very_large_numbers(self) -> None:
        """Test handling of very large numbers."""
        now = datetime.now(timezone.utc)
        # Use a large but reasonable value (under validation limit)
        large_micros = 1000000000000  # $1 million

        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.COUNTRY,
            location_name="United States",
            impressions=1000000000,  # 1 billion
            clicks=50000000,  # 50 million
            conversions=1000000.0,  # 1 million
            cost_micros=large_micros,
            revenue_micros=large_micros,
            start_date=now,
            end_date=now,
        )

        assert geo_data.cost_micros == large_micros
        assert geo_data.revenue_micros == large_micros
        # Verify conversions don't overflow
        assert geo_data.cost == large_micros / 1_000_000
        assert geo_data.revenue == large_micros / 1_000_000

    def test_unicode_location_names(self) -> None:
        """Test handling of unicode in location names."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="São Paulo, Brasil",
            city="São Paulo",
            country_code="BR",
            start_date=now,
            end_date=now,
        )

        assert geo_data.location_name == "São Paulo, Brasil"
        assert geo_data.city == "São Paulo"

        # Test with Asian characters
        geo_data2 = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="東京都",
            city="Tokyo",
            country_code="JP",
            start_date=now,
            end_date=now,
        )

        assert geo_data2.location_name == "東京都"

    def test_fractional_conversions(self) -> None:
        """Test handling of fractional conversions."""
        now = datetime.now(timezone.utc)
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            conversions=10.5,  # Fractional conversions from attribution
            clicks=100,
            cost_micros=50000000,  # $50
            start_date=now,
            end_date=now,
        )

        assert geo_data.conversions == 10.5
        assert geo_data.cpa == pytest.approx(4.76, abs=0.01)  # $50 / 10.5
        assert geo_data.conversion_rate == 0.105  # 10.5 / 100

    def test_negative_metrics(self) -> None:
        """Test that negative metrics are handled (data quality issues)."""
        now = datetime.now(timezone.utc)
        # Sometimes adjustments can result in negative values
        geo_data = GeoPerformanceData(
            customer_id="1234567890",
            campaign_id="789012",
            campaign_name="Test Campaign",
            geographic_level=GeographicLevel.CITY,
            location_name="New York, NY",
            impressions=-100,  # Data adjustment issue
            clicks=0,
            conversions=0.0,
            cost_micros=0,  # Validation prevents negative cost
            start_date=now,
            end_date=now,
        )

        assert geo_data.impressions == -100
        # Negative cost would raise validation error, so we test with 0
        assert geo_data.cost == 0.0

    def test_performance_score_boundaries(self) -> None:
        """Test performance score boundaries."""
        # Test 0 score
        insight_zero = LocationInsight(
            location_name="Poor Location",
            geographic_level=GeographicLevel.CITY,
            performance_score=0.0,
            cpa_vs_average=10.0,
            roas_vs_average=0.1,
            conversion_rate_vs_average=0.1,
            impression_share=0.01,
            cost_share=0.05,
            conversion_share=0.001,
            recommended_action="Exclude from targeting",
        )
        assert insight_zero.performance_score == 0.0

        # Test 100 score
        insight_perfect = LocationInsight(
            location_name="Perfect Location",
            geographic_level=GeographicLevel.CITY,
            performance_score=100.0,
            cpa_vs_average=0.1,
            roas_vs_average=10.0,
            conversion_rate_vs_average=5.0,
            impression_share=0.30,
            cost_share=0.10,
            conversion_share=0.50,
            recommended_action="Maximize investment",
        )
        assert insight_perfect.performance_score == 100.0

    def test_empty_collections(self) -> None:
        """Test models with empty collections."""
        now = datetime.now(timezone.utc)
        summary = GeoPerformanceSummary(
            customer_id="1234567890",
            analysis_date=now,
            date_range_start=now,
            date_range_end=now,
            total_locations=0,
            total_cost=0.0,
            total_conversions=0.0,
            average_cpa=0.0,
            average_roas=0.0,
            top_performing_locations=[],
            underperforming_locations=[],
            location_distribution={},
            expansion_opportunities=[],
        )

        assert summary.total_locations == 0
        assert len(summary.top_performing_locations) == 0
        assert len(summary.underperforming_locations) == 0
        assert len(summary.location_distribution) == 0
        assert len(summary.expansion_opportunities) == 0
