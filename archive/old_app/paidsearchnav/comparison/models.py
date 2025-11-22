"""Data models for audit comparison and trend analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


@dataclass
class AuditResult:
    """Represents the result of an audit analysis."""

    id: str
    customer_id: str
    status: str
    created_at: datetime
    summary: Dict[str, Any]
    details: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[Any] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class Recommendation:
    """Represents a recommendation from an audit."""

    id: str
    audit_id: str
    type: str
    priority: str
    description: str
    impact: Dict[str, Any]
    action: Dict[str, Any]
    created_at: datetime = field(default_factory=datetime.utcnow)


class MetricType(str, Enum):
    """Types of metrics that can be compared."""

    # Cost Efficiency
    TOTAL_SPEND = "total_spend"
    WASTED_SPEND = "wasted_spend"
    COST_PER_CONVERSION = "cost_per_conversion"
    ROAS = "roas"

    # Performance Metrics
    CTR = "ctr"
    CONVERSION_RATE = "conversion_rate"
    QUALITY_SCORE = "quality_score"
    IMPRESSIONS = "impressions"
    CLICKS = "clicks"
    CONVERSIONS = "conversions"

    # Optimization Progress
    RECOMMENDATIONS_COUNT = "recommendations_count"
    ISSUES_COUNT = "issues_count"
    NEGATIVE_KEYWORDS_COUNT = "negative_keywords_count"

    # Coverage Metrics
    KEYWORDS_ANALYZED = "keywords_analyzed"
    CAMPAIGNS_ANALYZED = "campaigns_analyzed"
    AD_GROUPS_ANALYZED = "ad_groups_analyzed"


class ComparisonPeriod(str, Enum):
    """Standard comparison periods."""

    DAY_OVER_DAY = "day_over_day"
    WEEK_OVER_WEEK = "week_over_week"
    MONTH_OVER_MONTH = "month_over_month"
    QUARTER_OVER_QUARTER = "quarter_over_quarter"
    YEAR_OVER_YEAR = "year_over_year"
    CUSTOM = "custom"


class TrendGranularity(str, Enum):
    """Granularity for trend analysis."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"


@dataclass
class ComparisonMetrics:
    """Metrics comparing two audit periods."""

    # Cost Efficiency
    total_spend_change: float
    total_spend_change_pct: float
    wasted_spend_reduction: float
    wasted_spend_reduction_pct: float
    cost_per_conversion_change: float
    cost_per_conversion_change_pct: float
    roas_change: float
    roas_change_pct: float

    # Performance Metrics
    ctr_improvement: float
    ctr_improvement_pct: float
    conversion_rate_change: float
    conversion_rate_change_pct: float
    quality_score_trend: float
    impressions_change: int
    impressions_change_pct: float
    clicks_change: int
    clicks_change_pct: float
    conversions_change: int
    conversions_change_pct: float

    # Optimization Progress
    recommendations_implemented: int
    recommendations_pending: int
    issues_resolved: int
    new_issues_found: int

    # Coverage Metrics
    keywords_analyzed_change: int
    negative_keywords_added: int
    match_type_optimizations: int

    # Statistical Significance
    is_statistically_significant: Dict[str, bool] = field(default_factory=dict)
    confidence_level: float = 0.95


@dataclass
class ComparisonOptions:
    """Options for configuring audit comparisons."""

    include_statistical_tests: bool = True
    confidence_level: float = 0.95
    minimum_sample_size: int = 30
    adjust_for_seasonality: bool = False
    exclude_anomalies: bool = False
    metrics_to_compare: List[MetricType] = field(default_factory=list)
    breakdown_by_campaign: bool = False
    breakdown_by_ad_group: bool = False
    include_recommendations: bool = True


@dataclass
class ComparisonResult:
    """Complete result of comparing two audits."""

    baseline_audit_id: str
    comparison_audit_id: str
    baseline_date: datetime
    comparison_date: datetime
    metrics: ComparisonMetrics
    insights: List[str]
    warnings: List[str]
    breakdown_by_campaign: Optional[Dict[str, ComparisonMetrics]] = None
    breakdown_by_ad_group: Optional[Dict[str, ComparisonMetrics]] = None
    recommendations_comparison: Optional[Dict[str, Any]] = None
    generated_at: datetime = field(default_factory=datetime.utcnow)


@dataclass
class TrendDataPoint:
    """Single data point in a trend analysis."""

    timestamp: datetime
    value: float
    metric_type: MetricType
    is_anomaly: bool = False
    anomaly_score: Optional[float] = None
    seasonality_adjusted: Optional[float] = None


@dataclass
class TrendAnalysis:
    """Complete trend analysis over a time period."""

    customer_id: str
    metric_type: MetricType
    start_date: datetime
    end_date: datetime
    granularity: TrendGranularity
    data_points: List[TrendDataPoint]
    trend_direction: str  # "increasing", "decreasing", "stable"
    trend_strength: float  # 0-1 scale
    forecast: Optional[List[TrendDataPoint]] = None
    seasonality_detected: bool = False
    anomalies_detected: int = 0
    insights: List[str] = field(default_factory=list)


@dataclass
class ImplementationStatus:
    """Track implementation of recommendations."""

    recommendation_id: str
    audit_id: str
    status: str  # "implemented", "partial", "pending", "rejected"
    implemented_at: Optional[datetime] = None
    impact_measured: Optional[Dict[str, float]] = None
    notes: Optional[str] = None


@dataclass
class AnomalyAlert:
    """Alert for detected anomalies in metrics."""

    metric_type: MetricType
    timestamp: datetime
    expected_value: float
    actual_value: float
    deviation_percentage: float
    severity: str  # "low", "medium", "high", "critical"
    possible_causes: List[str]
    recommended_actions: List[str]


class ComparisonRequest(BaseModel):
    """API request model for audit comparison."""

    baseline_audit_id: str = Field(..., description="ID of the baseline audit")
    comparison_audit_id: str = Field(..., description="ID of the comparison audit")
    options: Optional[ComparisonOptions] = Field(
        None, description="Options for comparison"
    )


class TrendRequest(BaseModel):
    """API request model for trend analysis."""

    customer_id: str = Field(..., description="Customer ID")
    metric_types: List[MetricType] = Field(
        ..., description="Metrics to analyze trends for"
    )
    start_date: datetime = Field(..., description="Start date for analysis")
    end_date: datetime = Field(..., description="End date for analysis")
    granularity: TrendGranularity = Field(
        TrendGranularity.MONTHLY, description="Granularity of data points"
    )
    include_forecast: bool = Field(
        False, description="Whether to include future forecast"
    )
    forecast_periods: int = Field(3, description="Number of periods to forecast")
