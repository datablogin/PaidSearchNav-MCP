"""Geographic performance data models."""

from datetime import datetime
from enum import Enum

from pydantic import Field

from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.core.models.base import BasePSNModel


class GeographicLevel(str, Enum):
    """Geographic aggregation levels."""

    COUNTRY = "COUNTRY"
    STATE = "STATE"
    CITY = "CITY"
    ZIP_CODE = "ZIP_CODE"
    RADIUS = "RADIUS"


class GeoPerformanceData(BasePSNModel):
    """Geographic performance metrics for a specific location."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    campaign_id: str = Field(..., description="Campaign ID")
    campaign_name: str = Field(..., description="Campaign name")

    # Geographic identifiers
    geographic_level: GeographicLevel = Field(
        ..., description="Level of geographic aggregation"
    )
    location_name: str = Field(..., description="Name of the geographic location")
    location_id: str | None = Field(None, description="Google location ID if available")
    country_code: str | None = Field(None, description="ISO country code")
    region_code: str | None = Field(None, description="State/region code")
    city: str | None = Field(None, description="City name")
    zip_code: str | None = Field(None, description="ZIP/postal code")

    # Distance-based data (for location extensions)
    distance_miles: float | None = Field(
        None, description="Distance from business location in miles"
    )
    business_location: str | None = Field(
        None, description="Business location reference"
    )

    # Performance metrics
    impressions: int = Field(0, description="Total impressions")
    clicks: int = Field(0, description="Total clicks")
    conversions: float = Field(0.0, description="Total conversions")
    cost_micros: int = Field(0, description="Total cost in micros")
    revenue_micros: int | None = Field(None, description="Total revenue in micros")

    # Time period
    start_date: datetime = Field(..., description="Start date of the data")
    end_date: datetime = Field(..., description="End date of the data")

    @property
    def cost(self) -> float:
        """Cost in currency units."""
        from paidsearchnav.core.validation import validate_cost_micros

        return validate_cost_micros(self.cost_micros)

    @property
    def revenue(self) -> float:
        """Revenue in currency units."""
        from paidsearchnav.core.validation import validate_revenue_micros

        return validate_revenue_micros(self.revenue_micros)

    @property
    def ctr(self) -> float:
        """Click-through rate."""
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @property
    def cpa(self) -> float:
        """Cost per acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        """Return on ad spend."""
        return self.revenue / self.cost if self.cost > 0 and self.revenue else 0.0

    @property
    def conversion_rate(self) -> float:
        """Conversion rate."""
        return self.conversions / self.clicks if self.clicks > 0 else 0.0


class LocationInsight(BasePSNModel):
    """Insight about a specific location's performance."""

    location_name: str = Field(..., description="Location name")
    geographic_level: GeographicLevel = Field(..., description="Geographic level")

    # Performance indicators
    performance_score: float = Field(
        ..., description="Overall performance score (0-100)"
    )
    cpa_vs_average: float = Field(
        ..., description="CPA compared to account average (ratio)"
    )
    roas_vs_average: float = Field(
        ..., description="ROAS compared to account average (ratio)"
    )
    conversion_rate_vs_average: float = Field(
        ..., description="Conversion rate vs average (ratio)"
    )

    # Volume indicators
    impression_share: float = Field(..., description="Share of total impressions")
    cost_share: float = Field(..., description="Share of total cost")
    conversion_share: float = Field(..., description="Share of total conversions")

    # Recommendations
    recommended_action: str = Field(
        ..., description="Recommended action for this location"
    )
    budget_recommendation: str | None = Field(
        None, description="Budget adjustment recommendation"
    )
    targeting_recommendation: str | None = Field(
        None, description="Targeting adjustment recommendation"
    )


class GeoPerformanceSummary(BasePSNModel):
    """Summary of geographic performance analysis."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    analysis_date: datetime = Field(..., description="When the analysis was performed")
    date_range_start: datetime = Field(..., description="Start of analyzed period")
    date_range_end: datetime = Field(..., description="End of analyzed period")

    # Overall metrics
    total_locations: int = Field(..., description="Total number of locations analyzed")
    total_cost: float = Field(..., description="Total cost across all locations")
    total_conversions: float = Field(
        ..., description="Total conversions across all locations"
    )
    average_cpa: float = Field(..., description="Average CPA across all locations")
    average_roas: float = Field(..., description="Average ROAS across all locations")

    # Top performers
    top_performing_locations: list[LocationInsight] = Field(
        default_factory=list, description="Top performing locations"
    )
    underperforming_locations: list[LocationInsight] = Field(
        default_factory=list, description="Underperforming locations"
    )

    # Geographic distribution
    location_distribution: dict[str, int] = Field(
        default_factory=dict,
        description="Distribution of performance by geographic level",
    )

    # Budget recommendations
    budget_reallocation_potential: float = Field(
        0.0, description="Potential improvement from budget reallocation"
    )
    expansion_opportunities: list[str] = Field(
        default_factory=list, description="Geographic areas for expansion"
    )


class DistancePerformanceData(BasePSNModel):
    """Performance data segmented by distance from business locations."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    business_name: str = Field(..., description="Business location name")
    business_address: str = Field(..., description="Business location address")

    # Distance segments
    distance_0_5_miles: GeoPerformanceData = Field(
        ..., description="0-5 miles performance"
    )
    distance_5_10_miles: GeoPerformanceData = Field(
        ..., description="5-10 miles performance"
    )
    distance_10_20_miles: GeoPerformanceData = Field(
        ..., description="10-20 miles performance"
    )
    distance_20_plus_miles: GeoPerformanceData = Field(
        ..., description="20+ miles performance"
    )

    # Analysis
    optimal_radius: float = Field(..., description="Optimal targeting radius in miles")
    efficiency_by_distance: dict[str, float] = Field(
        default_factory=dict, description="Efficiency metrics by distance range"
    )


class GeoPerformanceAnalysisResult(AnalysisResult):
    """Complete result of geographic performance analysis."""

    analysis_type: str = Field(
        default="geo_performance", description="Type of analysis"
    )

    # Data
    performance_data: list[GeoPerformanceData] = Field(
        default_factory=list, description="Raw geographic performance data"
    )
    summary: GeoPerformanceSummary = Field(..., description="Analysis summary")
    distance_analysis: list[DistancePerformanceData] | None = Field(
        None, description="Distance-based performance analysis"
    )

    # Insights and recommendations
    insights: list[LocationInsight] = Field(
        default_factory=list, description="Location-specific insights"
    )
    geo_recommendations: list[str] = Field(
        default_factory=list, description="Geographic-specific recommendations"
    )

    # Metrics for dashboard
    dashboard_metrics: dict[str, float] = Field(
        default_factory=dict, description="Key metrics for dashboard display"
    )
