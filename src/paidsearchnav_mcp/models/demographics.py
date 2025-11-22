"""Demographics performance data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any

from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.core.models.base import BasePSNModel


class DemographicType(str, Enum):
    """Types of demographic targeting."""

    AGE = "age"
    GENDER = "gender"
    HOUSEHOLD_INCOME = "household_income"
    PARENTAL_STATUS = "parental_status"


class AgeGroup(str, Enum):
    """Age demographic groups."""

    AGE_18_24 = "18-24"
    AGE_25_34 = "25-34"
    AGE_35_44 = "35-44"
    AGE_45_54 = "45-54"
    AGE_55_64 = "55-64"
    AGE_65_PLUS = "65+"
    UNKNOWN = "Unknown"


class GenderType(str, Enum):
    """Gender demographic types."""

    MALE = "Male"
    FEMALE = "Female"
    UNKNOWN = "Unknown"


class IncomePercentile(str, Enum):
    """Household income percentile ranges."""

    INCOME_0_10 = "0-10%"
    INCOME_11_20 = "11-20%"
    INCOME_21_30 = "21-30%"
    INCOME_31_40 = "31-40%"
    INCOME_41_50 = "41-50%"
    INCOME_51_60 = "51-60%"
    INCOME_61_70 = "61-70%"
    INCOME_71_80 = "71-80%"
    INCOME_81_90 = "81-90%"
    INCOME_91_100 = "91-100%"
    TOP_10 = "Top 10%"
    LOWER_50 = "Lower 50%"
    UPPER_50 = "Upper 50%"
    UNKNOWN = "Unknown"


class ParentalStatus(str, Enum):
    """Parental status types."""

    PARENT = "Parent"
    NOT_A_PARENT = "Not a parent"
    UNKNOWN = "Unknown"


class DemographicSegment(BasePSNModel):
    """Individual demographic data point."""

    customer_id: str
    campaign_id: str
    campaign_name: str
    ad_group_id: str | None = None
    ad_group_name: str | None = None
    demographic_type: DemographicType
    demographic_value: str  # The actual demographic value (e.g., "25-34", "Male")
    status: str = "Enabled"
    bid_adjustment: float = 0.0

    # Performance metrics
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    cost_micros: int = 0
    conversion_value_micros: int = 0

    # Analysis period
    start_date: datetime
    end_date: datetime

    @property
    def cost(self) -> float:
        """Cost in currency units."""
        return self.cost_micros / 1_000_000

    @property
    def conversion_value(self) -> float:
        """Conversion value in currency units."""
        return self.conversion_value_micros / 1_000_000

    @property
    def click_through_rate(self) -> float:
        """Click-through rate percentage."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def conversion_rate(self) -> float:
        """Conversion rate percentage."""
        return (self.conversions / self.clicks * 100) if self.clicks > 0 else 0.0

    @property
    def avg_cpc(self) -> float:
        """Average cost per click."""
        return self.cost / self.clicks if self.clicks > 0 else 0.0

    @property
    def cost_per_conversion(self) -> float:
        """Cost per conversion."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        """Return on ad spend."""
        return self.conversion_value / self.cost if self.cost > 0 else 0.0


class DemographicPerformance(BasePSNModel):
    """Performance metrics for a demographic segment."""

    demographic_type: DemographicType
    demographic_value: str
    segment_count: int  # Number of campaigns/ad groups using this demographic

    # Aggregated metrics
    total_impressions: int = 0
    total_clicks: int = 0
    total_conversions: float = 0.0
    total_cost: float = 0.0
    total_conversion_value: float = 0.0

    # Calculated metrics
    avg_ctr: float = 0.0
    avg_conversion_rate: float = 0.0
    avg_cpc: float = 0.0
    avg_cost_per_conversion: float = 0.0
    avg_roas: float = 0.0

    # Performance vs average
    ctr_vs_average: float = 1.0
    conversion_rate_vs_average: float = 1.0
    cpc_vs_average: float = 1.0
    roas_vs_average: float = 1.0

    # Shares
    impression_share: float = 0.0
    click_share: float = 0.0
    cost_share: float = 0.0
    conversion_share: float = 0.0

    # Performance score (0-100)
    performance_score: float = 0.0

    @property
    def is_high_performer(self) -> bool:
        """Check if this is a high-performing segment."""
        return self.performance_score >= 80.0

    @property
    def is_low_performer(self) -> bool:
        """Check if this is a low-performing segment."""
        return self.performance_score <= 40.0


class DemographicInsight(BasePSNModel):
    """Insight for a demographic segment."""

    demographic_type: DemographicType
    demographic_value: str
    insight_type: str  # "opportunity", "underperformer", "optimization"
    insight_message: str
    recommended_action: str
    bid_adjustment_recommendation: str
    impact_potential: str  # "high", "medium", "low"

    # Supporting metrics
    current_performance_score: float
    potential_improvement: float
    cost_impact_estimate: float


class DemographicsAnalysisSummary(BasePSNModel):
    """Summary of demographics analysis."""

    customer_id: str
    analysis_date: datetime
    date_range_start: datetime
    date_range_end: datetime

    # Data quality metrics
    total_segments_analyzed: int = 0
    segments_with_sufficient_data: int = 0
    data_completeness_score: float = 0.0
    coverage_percentage: float = 0.0

    # Overall performance metrics
    total_cost: float = 0.0
    total_conversions: float = 0.0
    total_clicks: int = 0
    total_impressions: int = 0

    average_ctr: float = 0.0
    average_conversion_rate: float = 0.0
    average_cpc: float = 0.0
    average_roas: float = 0.0

    # Performance variance
    ctr_variance_percentage: float = 0.0
    conversion_rate_variance_percentage: float = 0.0
    cpc_variance_percentage: float = 0.0
    roas_variance_percentage: float = 0.0

    # Analysis insights
    high_performing_segments_count: int = 0
    low_performing_segments_count: int = 0
    optimization_opportunities_count: int = 0
    optimization_potential_score: float = 0.0

    # Demographic distribution
    age_segments_analyzed: int = 0
    gender_segments_analyzed: int = 0
    income_segments_analyzed: int = 0
    parental_segments_analyzed: int = 0


class DemographicsAnalysisResult(AnalysisResult):
    """Complete demographics analysis result."""

    # Core data
    segments: list[DemographicSegment]
    performance_by_demographic: list[DemographicPerformance]
    summary: DemographicsAnalysisSummary
    insights: list[DemographicInsight]

    # Recommendations
    bid_adjustment_recommendations: dict[str, float]
    targeting_exclusion_recommendations: list[str]
    budget_reallocation_recommendations: list[str]
    optimization_recommendations: list[str]

    # Dashboard metrics
    dashboard_metrics: dict[str, Any]

    # KPI validation
    data_quality_kpis: dict[str, float]
    analysis_value_kpis: dict[str, float]
    business_impact_kpis: dict[str, float]

    def get_top_performers(self, limit: int = 3) -> list[DemographicPerformance]:
        """Get top performing demographic segments."""
        return sorted(
            self.performance_by_demographic,
            key=lambda x: x.performance_score,
            reverse=True,
        )[:limit]

    def get_bottom_performers(self, limit: int = 3) -> list[DemographicPerformance]:
        """Get bottom performing demographic segments."""
        return sorted(
            self.performance_by_demographic, key=lambda x: x.performance_score
        )[:limit]

    def get_segments_by_type(
        self, demographic_type: DemographicType
    ) -> list[DemographicPerformance]:
        """Get all segments for a specific demographic type."""
        return [
            perf
            for perf in self.performance_by_demographic
            if perf.demographic_type == demographic_type
        ]

    def get_reallocation_potential(self) -> float:
        """Calculate total budget reallocation potential percentage."""
        high_performers = [
            p for p in self.performance_by_demographic if p.is_high_performer
        ]
        low_performers = [
            p for p in self.performance_by_demographic if p.is_low_performer
        ]

        if not high_performers or not low_performers:
            return 0.0

        low_performer_cost_share = sum(p.cost_share for p in low_performers)
        return min(low_performer_cost_share * 100, 30.0)  # Cap at 30% reallocation
