"""Local reach and store visit metrics data models."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from paidsearchnav_mcp.models.analysis import AnalysisResult
from paidsearchnav_mcp.models.base import (
    EnhancedKeyMetrics,
    MetricPeriod,
    MetricWithContext,
)


class LocalReachEfficiencyLevel(Enum):
    """Local reach efficiency levels for categorization."""

    EXCELLENT = "excellent"
    GOOD = "good"
    AVERAGE = "average"
    POOR = "poor"


class LocalReachIssueType(Enum):
    """Types of issues that can be detected in local reach analysis."""

    LOW_STORE_VISIT_RATE = "low_store_visit_rate"
    HIGH_COST_PER_VISIT = "high_cost_per_visit"
    POOR_LOCAL_REACH = "poor_local_reach"
    INEFFICIENT_SPEND = "inefficient_spend"
    STORE_CANNIBALIZATION = "store_cannibalization"
    UNDERUTILIZED_LOCATION = "underutilized_location"


class StoreLocation(BaseModel):
    """Enhanced store location with geographic data."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country_code: str
    phone_number: Optional[str] = None
    latitude: Optional[float] = None
    longitude: Optional[float] = None
    market_area: Optional[str] = None

    @computed_field
    def display_name(self) -> str:
        """Generate a display name for the store."""
        return f"{self.store_name} - {self.city}, {self.state}"

    @computed_field
    def full_address(self) -> str:
        """Generate full address string."""
        address_parts = [self.address_line_1]
        if self.address_line_2:
            address_parts.append(self.address_line_2)
        address_parts.extend([self.city, self.state, self.postal_code])
        return ", ".join(address_parts)


class LocalReachMetrics(BaseModel):
    """Enhanced local reach performance metrics."""

    model_config = ConfigDict(str_strip_whitespace=True)

    local_impressions: int = 0
    store_visits: int = 0
    call_clicks: int = 0
    driving_directions: int = 0
    website_visits: int = 0
    cost: float = 0.0
    clicks: int = 0
    conversions: int = 0

    @field_validator(
        "local_impressions",
        "store_visits",
        "call_clicks",
        "driving_directions",
        "website_visits",
        "clicks",
        "conversions",
    )
    @classmethod
    def validate_non_negative_int(cls, v: int) -> int:
        """Validate that integer metrics are non-negative."""
        if v < 0:
            raise ValueError("Integer metrics must be non-negative")
        return v

    @field_validator("cost")
    @classmethod
    def validate_non_negative_float(cls, v: float) -> float:
        """Validate that cost is non-negative."""
        if v < 0:
            raise ValueError("Cost must be non-negative")
        return v

    @computed_field
    def total_local_actions(self) -> int:
        """Calculate total local action metrics."""
        return (
            self.store_visits
            + self.call_clicks
            + self.driving_directions
            + self.website_visits
        )

    @computed_field
    def store_visit_rate(self) -> float:
        """Calculate store visit rate as percentage of local impressions."""
        if self.local_impressions == 0:
            return 0.0
        return (self.store_visits / self.local_impressions) * 100

    @computed_field
    def local_engagement_rate(self) -> float:
        """Calculate local engagement rate as percentage of local impressions."""
        if self.local_impressions == 0:
            return 0.0
        return (self.total_local_actions / self.local_impressions) * 100

    @computed_field
    def cost_per_store_visit(self) -> float:
        """Calculate cost per store visit."""
        if self.store_visits == 0:
            return 0.0
        return self.cost / self.store_visits

    @computed_field
    def cost_per_local_action(self) -> float:
        """Calculate cost per local action."""
        if self.total_local_actions == 0:
            return 0.0
        return self.cost / self.total_local_actions

    @computed_field
    def local_click_through_rate(self) -> float:
        """Calculate local click through rate."""
        if self.local_impressions == 0:
            return 0.0
        return (self.clicks / self.local_impressions) * 100

    @computed_field
    def store_visit_conversion_rate(self) -> float:
        """Calculate store visit to conversion rate."""
        if self.store_visits == 0:
            return 0.0
        return (self.conversions / self.store_visits) * 100


class StoreVisitData(BaseModel):
    """Store visit attribution and performance data."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_visits: int = 0
    attributed_revenue: Optional[float] = None
    visit_duration_avg: Optional[float] = None
    repeat_visit_rate: Optional[float] = None
    conversion_rate: Optional[float] = None

    @computed_field
    def revenue_per_visit(self) -> float:
        """Calculate revenue per store visit."""
        if self.store_visits == 0 or self.attributed_revenue is None:
            return 0.0
        return self.attributed_revenue / self.store_visits


class LocationPerformance(BaseModel):
    """Geographic performance summary for a store location."""

    model_config = ConfigDict(str_strip_whitespace=True)

    location: StoreLocation
    metrics: LocalReachMetrics
    visit_data: Optional[StoreVisitData] = None
    efficiency_level: LocalReachEfficiencyLevel = LocalReachEfficiencyLevel.AVERAGE
    market_rank: Optional[int] = None
    competitive_index: Optional[float] = None

    @computed_field
    def performance_score(self) -> float:
        """Calculate overall performance score (0-100) using weighted multi-factor algorithm.

        The scoring algorithm combines three key performance dimensions:

        1. **Store Visit Rate Score (0-50 points, 50% weight)**:
           - Measures conversion from local impressions to actual store visits
           - Formula: min(store_visit_rate * 10, 50)
           - Example: 2.5% visit rate = 25 points, 5%+ visit rate = 50 points (max)

        2. **Local Engagement Score (0-30 points, 30% weight)**:
           - Measures overall local engagement (visits + calls + directions + web)
           - Formula: min(local_engagement_rate * 5, 30)
           - Example: 4% engagement = 20 points, 6%+ engagement = 30 points (max)

        3. **Cost Efficiency Score (0-20 points, 20% weight)**:
           - Measures cost effectiveness of store visit generation
           - Uses inverse relationship: lower cost per visit = higher score
           - Formula: max(0, min(50 - cost_per_visit, 40)) / 2
           - Example: $10/visit = 20 points, $25/visit = 12.5 points, $50+/visit = 0 points

        **Score Interpretation**:
        - 85-100: Exceptional performance (top tier)
        - 70-84: High performance (above average)
        - 50-69: Average performance (meeting benchmarks)
        - 30-49: Below average (needs optimization)
        - 0-29: Poor performance (requires immediate attention)

        Returns:
            float: Overall performance score from 0-100
        """
        # Weighted performance score based on multiple factors
        visit_rate_score = min(self.metrics.store_visit_rate * 10, 50)  # Max 50 points
        engagement_score = min(
            self.metrics.local_engagement_rate * 5, 30
        )  # Max 30 points
        efficiency_score = (
            20 if self.metrics.cost_per_store_visit > 0 else 0
        )  # Max 20 points

        # Adjust efficiency score based on cost efficiency
        if self.metrics.cost_per_store_visit > 0:
            # Lower cost per visit = higher score (inverse relationship)
            # Normalize to reasonable range (assuming $10-50 per visit is typical)
            normalized_cost = max(0, min(50 - self.metrics.cost_per_store_visit, 40))
            efficiency_score = normalized_cost / 2  # Convert to 0-20 scale

        return visit_rate_score + engagement_score + efficiency_score

    @computed_field
    def is_high_performer(self) -> bool:
        """Check if location is a high performer."""
        return (
            self.metrics.store_visit_rate >= 2.0
            and self.metrics.local_engagement_rate >= 4.0
            and self.performance_score >= 65
        )

    @computed_field
    def is_underperformer(self) -> bool:
        """Check if location is an underperformer."""
        return (
            self.metrics.store_visit_rate < 0.5
            or self.metrics.local_engagement_rate < 1.5
            or self.performance_score < 30
        )

    @computed_field
    def needs_optimization(self) -> bool:
        """Check if location needs optimization."""
        return (
            self.metrics.cost_per_store_visit > 25.0
            or self.metrics.store_visit_rate < 1.0
            or self.is_underperformer
        )


class LocalReachInsight(BaseModel):
    """Insight about local reach performance issues or opportunities."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str
    issue_type: LocalReachIssueType
    description: str
    impact: str
    recommendation: str
    priority: str  # "critical", "high", "medium", "low"
    potential_improvement: Optional[str] = None
    estimated_impact: Optional[str] = None


class LocalReachSummary(BaseModel):
    """Summary of local reach analysis across all locations."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total_locations: int = 0
    total_local_impressions: int = 0
    total_store_visits: int = 0
    total_cost: float = 0.0
    avg_store_visit_rate: float = 0.0
    avg_cost_per_visit: float = 0.0
    high_performers: int = 0
    underperformers: int = 0
    locations_needing_optimization: int = 0
    local_revenue_opportunity: float = 0.0  # Additional local revenue opportunity

    @computed_field
    def overall_store_visit_rate(self) -> float:
        """Calculate overall store visit rate across all locations."""
        if self.total_local_impressions == 0:
            return 0.0
        return (self.total_store_visits / self.total_local_impressions) * 100

    @computed_field
    def overall_cost_per_visit(self) -> float:
        """Calculate overall cost per store visit."""
        if self.total_store_visits == 0:
            return 0.0
        return self.total_cost / self.total_store_visits

    @computed_field
    def performance_distribution(self) -> dict:
        """Get performance distribution across locations."""
        if self.total_locations == 0:
            return {"high": 0.0, "average": 0.0, "low": 0.0}

        average_performers = (
            self.total_locations - self.high_performers - self.underperformers
        )
        return {
            "high": (self.high_performers / self.total_locations) * 100,
            "average": (average_performers / self.total_locations) * 100,
            "low": (self.underperformers / self.total_locations) * 100,
        }


class LocalReachAnalysisResult(AnalysisResult):
    """Results from local reach store performance analysis."""

    summary: LocalReachSummary
    location_performance: List[LocationPerformance] = []
    insights: List[LocalReachInsight] = []
    top_performers: List[LocationPerformance] = []
    underperformers: List[LocationPerformance] = []
    optimization_opportunities: List[LocationPerformance] = []

    @property
    def key_metrics(self) -> EnhancedKeyMetrics:
        """Get enhanced key metrics with time period context for local reach analysis.

        Returns:
            EnhancedKeyMetrics object with contextual information specific to local reach
        """
        # Calculate reporting period description
        days_diff = (self.end_date - self.start_date).days + 1
        reporting_period = f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')} ({days_diff} days)"

        # Create local reach specific metrics
        metrics = {
            "total_locations": MetricWithContext(
                value=self.summary.total_locations,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total store locations analyzed",
                calculation_method="Count of unique store locations with performance data",
            ),
            "total_local_impressions": MetricWithContext(
                value=self.summary.total_local_impressions,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total local impressions across all locations",
                calculation_method="Sum of impressions for all locations in reporting period",
            ),
            "total_store_visits": MetricWithContext(
                value=self.summary.total_store_visits,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total store visits generated",
                calculation_method="Sum of store visits across all locations",
            ),
            "total_cost": MetricWithContext(
                value=self.summary.total_cost,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="USD",
                description="Total ad spend for local campaigns",
                calculation_method="Sum of costs across all locations in reporting period",
            ),
            "local_revenue": MetricWithContext(
                value=self.summary.local_revenue_opportunity,
                period=MetricPeriod.MONTHLY_PROJECTION,
                unit="USD",
                description="Additional local revenue opportunity",
                calculation_method="Projected monthly revenue opportunity based on optimization potential",
            ),
            "overall_store_visit_rate": MetricWithContext(
                value=self.summary.overall_store_visit_rate,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="percentage",
                description="Overall store visit rate across all locations",
                calculation_method="Total store visits / total local impressions * 100",
            ),
            "avg_cost_per_visit": MetricWithContext(
                value=self.summary.avg_cost_per_visit,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="USD",
                description="Average cost per store visit",
                calculation_method="Total cost / total store visits",
            ),
            "performance_distribution": MetricWithContext(
                value={
                    "high_performers": self.summary.high_performers,
                    "underperformers": self.summary.underperformers,
                    "needs_optimization": self.summary.locations_needing_optimization,
                },
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Distribution of location performance levels",
                calculation_method="Count of locations by performance category",
            ),
        }

        return EnhancedKeyMetrics(reporting_period=reporting_period, metrics=metrics)
