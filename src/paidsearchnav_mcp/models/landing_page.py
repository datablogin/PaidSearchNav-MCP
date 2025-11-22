"""Data models for Landing Page Performance and Conversion Analysis."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional


class PagePerformanceStatus(str, Enum):
    """Landing page performance status categories."""

    TOP_PERFORMER = "Top Performer"
    ABOVE_AVERAGE = "Above Average"
    AVERAGE = "Average"
    BELOW_AVERAGE = "Below Average"
    POOR_PERFORMER = "Poor Performer"
    INSUFFICIENT_DATA = "Insufficient Data"


class OptimizationType(str, Enum):
    """Types of landing page optimizations."""

    CONVERSION_RATE = "Conversion Rate"
    USER_EXPERIENCE = "User Experience"
    PAGE_SPEED = "Page Speed"
    MOBILE_OPTIMIZATION = "Mobile Optimization"
    CONTENT_RELEVANCE = "Content Relevance"
    TRAFFIC_ALLOCATION = "Traffic Allocation"
    AB_TESTING = "A/B Testing"


class TrafficSource(str, Enum):
    """Traffic source types for landing pages."""

    SEARCH = "Search"
    DISPLAY = "Display"
    VIDEO = "Video"
    SHOPPING = "Shopping"
    DEMAND_GEN = "Demand Gen"
    SMART = "Smart"
    UNKNOWN = "Unknown"


@dataclass
class LandingPageMetrics:
    """Performance metrics for a landing page."""

    url: str
    clicks: int = 0
    impressions: int = 0
    ctr: float = 0.0
    cost: float = 0.0
    avg_cpc: float = 0.0
    conversions: float = 0.0
    conversion_rate: float = 0.0
    cost_per_conversion: float = 0.0
    mobile_speed_score: Optional[int] = None
    mobile_friendly_click_rate: Optional[float] = None
    valid_amp_click_rate: Optional[float] = None
    bounce_rate: Optional[float] = None
    avg_session_duration: Optional[float] = None
    pages_per_session: Optional[float] = None
    engagement_rate: Optional[float] = None
    ga4_sessions: Optional[int] = None

    @property
    def has_sufficient_data(self) -> bool:
        """Check if page has sufficient data for analysis."""
        return self.clicks >= 50

    @property
    def efficiency_score(self) -> float:
        """Calculate overall efficiency score (0-100)."""
        if self.clicks == 0:
            return 0.0

        # Weighted score based on multiple factors
        conv_score = min(self.conversion_rate * 10, 50)  # Max 50 points
        cpc_score = max(0, 25 - (self.avg_cpc * 2))  # Max 25 points
        ctr_score = min(self.ctr * 250, 25)  # Max 25 points

        return conv_score + cpc_score + ctr_score


@dataclass
class ConversionFunnel:
    """Conversion funnel analysis for a landing page."""

    page_url: str
    impressions: int = 0
    clicks: int = 0
    page_views: int = 0
    engaged_sessions: int = 0
    form_starts: int = 0
    form_completions: int = 0
    conversions: float = 0.0

    @property
    def click_through_rate(self) -> float:
        """Calculate CTR from impressions to clicks."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def engagement_rate(self) -> float:
        """Calculate engagement rate from page views."""
        return (
            (self.engaged_sessions / self.page_views * 100)
            if self.page_views > 0
            else 0.0
        )

    @property
    def form_completion_rate(self) -> float:
        """Calculate form completion rate."""
        return (
            (self.form_completions / self.form_starts * 100)
            if self.form_starts > 0
            else 0.0
        )

    @property
    def overall_conversion_rate(self) -> float:
        """Calculate overall conversion rate from clicks."""
        return (self.conversions / self.clicks * 100) if self.clicks > 0 else 0.0


@dataclass
class PageOptimization:
    """Optimization recommendation for a landing page."""

    page_url: str
    optimization_type: OptimizationType
    priority: str  # High, Medium, Low
    current_performance: str
    recommended_action: str
    expected_impact: str
    reasoning: str
    estimated_improvement: Optional[float] = None  # Percentage improvement
    estimated_revenue_impact: Optional[float] = None
    confidence_score: float = 0.0
    implementation_complexity: str = "Medium"  # Low, Medium, High

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "page_url": self.page_url,
            "optimization_type": self.optimization_type.value,
            "priority": self.priority,
            "current_performance": self.current_performance,
            "recommended_action": self.recommended_action,
            "expected_impact": self.expected_impact,
            "reasoning": self.reasoning,
            "estimated_improvement": self.estimated_improvement,
            "estimated_revenue_impact": self.estimated_revenue_impact,
            "confidence_score": self.confidence_score,
            "implementation_complexity": self.implementation_complexity,
        }


@dataclass
class TrafficSourcePerformance:
    """Performance metrics by traffic source."""

    source: TrafficSource
    pages: List[str] = field(default_factory=list)
    total_clicks: int = 0
    total_impressions: int = 0
    total_cost: float = 0.0
    total_conversions: float = 0.0
    avg_ctr: float = 0.0
    avg_conversion_rate: float = 0.0
    avg_cpc: float = 0.0
    top_performing_page: Optional[str] = None
    worst_performing_page: Optional[str] = None


@dataclass
class ABTestOpportunity:
    """A/B testing opportunity for landing pages."""

    control_page: str
    variant_suggestions: List[str]
    test_hypothesis: str
    success_metrics: List[str]
    expected_duration_days: int
    minimum_sample_size: int
    potential_uplift: float  # Percentage
    priority: str  # High, Medium, Low
    reasoning: str


@dataclass
class LandingPageAnalysisSummary:
    """Summary of landing page analysis."""

    total_pages_analyzed: int
    pages_with_sufficient_data: int
    total_clicks: int
    total_impressions: int
    total_cost: float
    total_conversions: float
    avg_conversion_rate: float
    avg_ctr: float
    avg_cpc: float
    top_performing_pages: List[str] = field(default_factory=list)
    bottom_performing_pages: List[str] = field(default_factory=list)
    optimization_opportunities: int = 0
    potential_cost_savings: float = 0.0
    potential_conversion_increase: float = 0.0
    key_insights: List[str] = field(default_factory=list)
    data_quality_score: float = 0.0
    analysis_confidence: float = 0.0


@dataclass
class LandingPageAnalysisResult:
    """Complete landing page analysis result."""

    customer_id: str
    analysis_date: datetime
    start_date: datetime
    end_date: datetime
    landing_pages: List[LandingPageMetrics] = field(default_factory=list)
    conversion_funnels: List[ConversionFunnel] = field(default_factory=list)
    optimizations: List[PageOptimization] = field(default_factory=list)
    traffic_source_performance: List[TrafficSourcePerformance] = field(
        default_factory=list
    )
    ab_test_opportunities: List[ABTestOpportunity] = field(default_factory=list)
    summary: Optional[LandingPageAnalysisSummary] = None
    metadata: Dict[str, Any] = field(default_factory=dict)

    def to_dict(self) -> Dict[str, Any]:
        """Convert to dictionary representation."""
        return {
            "customer_id": self.customer_id,
            "analysis_date": self.analysis_date.isoformat(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "landing_pages": [
                {
                    "url": lp.url,
                    "clicks": lp.clicks,
                    "conversions": lp.conversions,
                    "conversion_rate": lp.conversion_rate,
                    "cost": lp.cost,
                    "efficiency_score": lp.efficiency_score,
                }
                for lp in sorted(
                    self.landing_pages[:10],
                    key=lambda x: x.efficiency_score,
                    reverse=True,
                )
            ],
            "optimizations": [opt.to_dict() for opt in self.optimizations[:5]],
            "ab_test_opportunities": [
                {
                    "control_page": test.control_page,
                    "test_hypothesis": test.test_hypothesis,
                    "potential_uplift": test.potential_uplift,
                    "priority": test.priority,
                }
                for test in self.ab_test_opportunities[:3]
            ],
            "summary": {
                "total_pages_analyzed": self.summary.total_pages_analyzed,
                "total_conversions": self.summary.total_conversions,
                "avg_conversion_rate": self.summary.avg_conversion_rate,
                "optimization_opportunities": self.summary.optimization_opportunities,
                "key_insights": self.summary.key_insights,
            }
            if self.summary
            else {},
            "metadata": self.metadata,
        }
