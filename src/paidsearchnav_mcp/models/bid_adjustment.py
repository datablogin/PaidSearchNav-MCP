"""Data models for Advanced Bid Adjustment Strategy Analyzer."""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional

from paidsearchnav_mcp.models.base import (
    EnhancedKeyMetrics,
    MetricPeriod,
    MetricWithContext,
)


class InteractionType(str, Enum):
    """Types of interaction for bid adjustments."""

    CALLS = "Calls"
    CLICKS = "Clicks"
    CONVERSIONS = "Conversions"
    VIEWS = "Views"
    ENGAGEMENTS = "Engagements"
    UNKNOWN = "Unknown"


class BidStrategyType(str, Enum):
    """Types of bid strategies."""

    MANUAL_CPC = "Manual CPC"
    ENHANCED_CPC = "Enhanced CPC"
    TARGET_CPA = "Target CPA"
    TARGET_ROAS = "Target ROAS"
    MAXIMIZE_CONVERSIONS = "Maximize Conversions"
    MAXIMIZE_CLICKS = "Maximize Clicks"
    TARGET_IMPRESSION_SHARE = "Target Impression Share"
    UNKNOWN = "Unknown"


class BidAdjustmentDimension(str, Enum):
    """Dimensions for bid adjustments."""

    DEVICE = "Device"
    LOCATION = "Location"
    AD_SCHEDULE = "Ad Schedule"
    AUDIENCE = "Audience"
    DEMOGRAPHICS = "Demographics"
    INTERACTION_TYPE = "Interaction Type"
    UNKNOWN = "Unknown"


class OptimizationStatus(str, Enum):
    """Optimization status for bid adjustments."""

    OPTIMAL = "Optimal"
    OVER_BIDDING = "Over-bidding"
    UNDER_BIDDING = "Under-bidding"
    NO_DATA = "No Data"
    NEEDS_REVIEW = "Needs Review"


@dataclass
class BidPerformanceMetrics:
    """Performance metrics for bid adjustments."""

    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    cost: float = 0.0
    interaction_rate: float = 0.0
    conversion_rate: float = 0.0
    cost_per_conversion: float = 0.0
    avg_cpm: float = 0.0
    avg_cpc: float = 0.0
    interaction_coverage: float = 0.0
    roi: Optional[float] = None
    revenue: Optional[float] = None


@dataclass
class BidAdjustment:
    """Individual bid adjustment with performance data."""

    adjustment_id: str
    campaign_name: str
    campaign_id: Optional[str] = None
    interaction_type: InteractionType = InteractionType.UNKNOWN
    dimension: BidAdjustmentDimension = BidAdjustmentDimension.UNKNOWN
    bid_modifier: Optional[float] = None
    performance: BidPerformanceMetrics = field(default_factory=BidPerformanceMetrics)
    optimization_status: OptimizationStatus = OptimizationStatus.NO_DATA
    created_at: Optional[datetime] = None
    updated_at: Optional[datetime] = None
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class BidStrategy:
    """Strategic bidding approach and effectiveness."""

    strategy_id: str
    strategy_type: BidStrategyType
    campaign_count: int = 0
    total_impressions: int = 0
    total_clicks: int = 0
    total_conversions: float = 0.0
    total_cost: float = 0.0
    avg_bid_modifier: float = 1.0
    effectiveness_score: float = 0.0
    optimization_opportunities: List[str] = field(default_factory=list)
    top_performing_campaigns: List[str] = field(default_factory=list)
    underperforming_campaigns: List[str] = field(default_factory=list)


@dataclass
class BidOptimization:
    """Bid adjustment recommendations."""

    adjustment_id: str
    campaign_name: str
    current_bid_modifier: Optional[float]
    recommended_bid_modifier: float
    expected_impact: str
    reasoning: str
    priority: str  # High, Medium, Low
    estimated_cost_savings: Optional[float] = None
    estimated_conversion_increase: Optional[float] = None
    confidence_score: float = 0.0


@dataclass
class CompetitiveInsight:
    """Competitive positioning insights."""

    market_position: str  # Leader, Competitive, Lagging
    avg_position: Optional[float] = None
    impression_share: Optional[float] = None
    lost_impression_share_budget: Optional[float] = None
    lost_impression_share_rank: Optional[float] = None
    competitive_metrics: Dict[str, Any] = field(default_factory=dict)
    recommendations: List[str] = field(default_factory=list)


@dataclass
class BidAdjustmentAnalysisSummary:
    """Summary of bid adjustment analysis."""

    total_campaigns_analyzed: int
    total_bid_adjustments: int
    total_impressions: int
    total_clicks: int
    total_conversions: float
    total_cost: float
    avg_roi: float
    optimal_adjustments_count: int
    over_bidding_count: int
    under_bidding_count: int
    top_optimization_opportunities: List[BidOptimization]
    key_insights: List[str]
    data_quality_score: float
    analysis_confidence: float

    def get_key_metrics(
        self, start_date: datetime, end_date: datetime
    ) -> EnhancedKeyMetrics:
        """Get enhanced key metrics with time period context.

        Args:
            start_date: Analysis start date
            end_date: Analysis end date

        Returns:
            EnhancedKeyMetrics object with contextual information
        """
        # Calculate reporting period description
        days_diff = (end_date - start_date).days + 1
        reporting_period = f"{start_date.strftime('%Y-%m-%d')} to {end_date.strftime('%Y-%m-%d')} ({days_diff} days)"

        # Calculate potential savings from optimizations
        potential_monthly_savings = sum(
            opt.estimated_cost_savings or 0
            for opt in self.top_optimization_opportunities
            if opt.estimated_cost_savings
        )

        # Create contextual metrics
        metrics = {
            "device_adjustments": MetricWithContext(
                value=self.total_bid_adjustments,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Active bid adjustments found in data",
                calculation_method="Count of all bid adjustments in reporting period",
            ),
            "campaigns_analyzed": MetricWithContext(
                value=self.total_campaigns_analyzed,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total campaigns included in analysis",
                calculation_method="Unique campaigns with bid adjustment data",
            ),
            "total_impressions": MetricWithContext(
                value=self.total_impressions,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total impressions across all bid adjustments",
                calculation_method="Sum of impressions for reporting period",
            ),
            "total_cost": MetricWithContext(
                value=self.total_cost,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="USD",
                description="Total spend across all bid adjustments",
                calculation_method="Sum of cost for reporting period",
            ),
            "potential_savings": MetricWithContext(
                value=potential_monthly_savings,
                period=MetricPeriod.MONTHLY_PROJECTION,
                unit="USD",
                description="Estimated monthly cost savings from bid optimizations",
                calculation_method=f"Sum of estimated savings from top {len(self.top_optimization_opportunities)} optimization opportunities",
            ),
            "optimization_status": MetricWithContext(
                value={
                    "optimal": self.optimal_adjustments_count,
                    "over_bidding": self.over_bidding_count,
                    "under_bidding": self.under_bidding_count,
                },
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Distribution of bid adjustment optimization status",
                calculation_method="Count of adjustments by optimization status",
            ),
            "data_quality_score": MetricWithContext(
                value=self.data_quality_score,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="percentage",
                description="Data quality score for the analysis",
                calculation_method="Percentage of campaigns with sufficient data for analysis",
            ),
        }

        return EnhancedKeyMetrics(reporting_period=reporting_period, metrics=metrics)


@dataclass
class BidAdjustmentAnalysisResult:
    """Complete bidding strategy analysis result."""

    customer_id: str
    analysis_date: datetime
    start_date: datetime
    end_date: datetime
    bid_adjustments: List[BidAdjustment]
    bid_strategies: List[BidStrategy]
    optimizations: List[BidOptimization]
    competitive_insights: CompetitiveInsight
    summary: BidAdjustmentAnalysisSummary
    metadata: Dict[str, Any] = field(default_factory=dict)

    @property
    def key_metrics(self) -> EnhancedKeyMetrics:
        """Get enhanced key metrics with time period context."""
        return self.summary.get_key_metrics(self.start_date, self.end_date)

    def to_dict(self) -> Dict[str, Any]:
        """Convert analysis result to dictionary."""
        return {
            "customer_id": self.customer_id,
            "analysis_date": self.analysis_date.isoformat(),
            "start_date": self.start_date.isoformat(),
            "end_date": self.end_date.isoformat(),
            "bid_adjustments": [
                {
                    "adjustment_id": adj.adjustment_id,
                    "campaign_name": adj.campaign_name,
                    "interaction_type": adj.interaction_type.value,
                    "bid_modifier": adj.bid_modifier,
                    "optimization_status": adj.optimization_status.value,
                    "performance": {
                        "impressions": adj.performance.impressions,
                        "conversions": adj.performance.conversions,
                        "cost": adj.performance.cost,
                        "cost_per_conversion": adj.performance.cost_per_conversion,
                        "roi": adj.performance.roi,
                    },
                }
                for adj in self.bid_adjustments[:10]  # Top 10 for summary
            ],
            "optimizations": [
                {
                    "campaign_name": opt.campaign_name,
                    "current_bid": opt.current_bid_modifier,
                    "recommended_bid": opt.recommended_bid_modifier,
                    "reasoning": opt.reasoning,
                    "priority": opt.priority,
                }
                for opt in self.optimizations[:5]  # Top 5 recommendations
            ],
            "summary": {
                "total_campaigns": self.summary.total_campaigns_analyzed,
                "total_adjustments": self.summary.total_bid_adjustments,
                "total_cost": self.summary.total_cost,
                "total_conversions": self.summary.total_conversions,
                "avg_roi": self.summary.avg_roi,
                "optimization_status": {
                    "optimal": self.summary.optimal_adjustments_count,
                    "over_bidding": self.summary.over_bidding_count,
                    "under_bidding": self.summary.under_bidding_count,
                },
                "key_insights": self.summary.key_insights,
            },
            "competitive_insights": {
                "market_position": self.competitive_insights.market_position,
                "recommendations": self.competitive_insights.recommendations,
            },
            "metadata": self.metadata,
        }
