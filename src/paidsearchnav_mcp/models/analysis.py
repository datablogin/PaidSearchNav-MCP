"""Analysis result models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from paidsearchnav_mcp.models.base import (
    BasePSNModel,
    EnhancedKeyMetrics,
    MetricPeriod,
    MetricWithContext,
)
from paidsearchnav_mcp.models.search_term import (
    SearchTerm,
    SearchTermClassification,
)


class RecommendationPriority(str, Enum):
    """Priority levels for recommendations."""

    CRITICAL = "CRITICAL"  # Must fix immediately
    HIGH = "HIGH"  # Should fix soon
    MEDIUM = "MEDIUM"  # Important but not urgent
    LOW = "LOW"  # Nice to have


class RecommendationType(str, Enum):
    """Types of recommendations."""

    ADD_KEYWORD = "ADD_KEYWORD"
    ADD_NEGATIVE = "ADD_NEGATIVE"
    PAUSE_KEYWORD = "PAUSE_KEYWORD"
    PAUSE_KEYWORDS = "PAUSE_KEYWORDS"
    CHANGE_MATCH_TYPE = "CHANGE_MATCH_TYPE"
    ADJUST_BID = "ADJUST_BID"
    FIX_CONFLICT = "FIX_CONFLICT"
    OPTIMIZE_LOCATION = "OPTIMIZE_LOCATION"
    OPTIMIZE_KEYWORDS = "OPTIMIZE_KEYWORDS"
    IMPROVE_QUALITY = "IMPROVE_QUALITY"
    IMPROVE_QUALITY_SCORE = "IMPROVE_QUALITY_SCORE"
    CONSOLIDATE_KEYWORDS = "CONSOLIDATE_KEYWORDS"
    OPTIMIZE_BIDDING = "OPTIMIZE_BIDDING"
    ADD_NEGATIVE_KEYWORDS = "ADD_NEGATIVE_KEYWORDS"
    RESOLVE_CONFLICTS = "RESOLVE_CONFLICTS"
    BUDGET_OPTIMIZATION = "BUDGET_OPTIMIZATION"
    OPTIMIZE_ASSETS = "OPTIMIZE_ASSETS"
    OTHER = "OTHER"


class Recommendation(BasePSNModel):
    """A specific recommendation from analysis."""

    type: RecommendationType = Field(..., description="Type of recommendation")
    priority: RecommendationPriority = Field(..., description="Priority level")
    title: str = Field(..., description="Short title")
    description: str = Field(..., description="Detailed description")

    # Affected entities
    campaign_id: str | None = Field(None, description="Affected campaign")
    ad_group_id: str | None = Field(None, description="Affected ad group")
    keyword_id: str | None = Field(None, description="Affected keyword")

    # Expected impact
    estimated_impact: str | None = Field(
        None, description="Expected impact if implemented"
    )
    estimated_cost_savings: float | None = Field(
        None, description="Estimated monthly cost savings"
    )
    estimated_conversion_increase: float | None = Field(
        None, description="Estimated conversion increase %"
    )

    # Implementation details
    action_data: dict[str, Any] = Field(
        default_factory=dict, description="Data needed for implementation"
    )


class AnalysisMetrics(BasePSNModel):
    """Metrics from analysis."""

    total_keywords_analyzed: int = Field(default=0)
    total_search_terms_analyzed: int = Field(default=0)
    total_campaigns_analyzed: int = Field(default=0)

    # Issues found
    issues_found: int = Field(default=0)
    critical_issues: int = Field(default=0)

    # Potential impact
    potential_cost_savings: float = Field(
        default=0.0, description="Monthly cost savings"
    )
    potential_conversion_increase: float = Field(
        default=0.0, description="Conversion increase %"
    )

    # Custom metrics per analyzer
    custom_metrics: dict[str, Any] = Field(default_factory=dict)


class AnalysisResult(BasePSNModel):
    """Result from an analyzer."""

    # Identification
    analysis_id: str | None = Field(None, description="Unique analysis ID")
    customer_id: str = Field(..., description="Google Ads customer ID")
    analysis_type: str = Field(..., description="Type of analysis performed")
    analyzer_name: str = Field(..., description="Name of analyzer used")

    # Time range
    start_date: datetime = Field(..., description="Analysis period start")
    end_date: datetime = Field(..., description="Analysis period end")

    # Results
    status: str = Field(default="completed", description="Analysis status")
    metrics: AnalysisMetrics = Field(
        default_factory=lambda: AnalysisMetrics(), description="Analysis metrics"
    )
    recommendations: list[Recommendation] = Field(
        default_factory=list, description="List of recommendations"
    )

    # Raw data for detailed review
    raw_data: dict[str, Any] = Field(
        default_factory=dict, description="Raw analysis data"
    )

    # Errors if any
    errors: list[str] = Field(
        default_factory=list, description="Any errors encountered"
    )

    @property
    def has_critical_issues(self) -> bool:
        """Check if analysis found critical issues."""
        return any(
            r.priority == RecommendationPriority.CRITICAL for r in self.recommendations
        )

    @property
    def total_recommendations(self) -> int:
        """Get total number of recommendations."""
        return len(self.recommendations)

    def get_recommendations_by_priority(
        self, priority: RecommendationPriority
    ) -> list[Recommendation]:
        """Get recommendations filtered by priority."""
        return [r for r in self.recommendations if r.priority == priority]

    def get_recommendations_by_type(
        self, rec_type: RecommendationType
    ) -> list[Recommendation]:
        """Get recommendations filtered by type."""
        return [r for r in self.recommendations if r.type == rec_type]

    @property
    def key_metrics(self) -> EnhancedKeyMetrics:
        """Get enhanced key metrics with time period context.

        Returns:
            EnhancedKeyMetrics object with contextual information
        """
        # Calculate reporting period description
        days_diff = (self.end_date - self.start_date).days + 1
        reporting_period = f"{self.start_date.strftime('%Y-%m-%d')} to {self.end_date.strftime('%Y-%m-%d')} ({days_diff} days)"

        # Create contextual metrics based on analyzer type
        metrics = {
            "total_analyzed": MetricWithContext(
                value=getattr(self.metrics, "total_keywords_analyzed", 0)
                or getattr(self.metrics, "total_search_terms_analyzed", 0)
                or getattr(self.metrics, "total_campaigns_analyzed", 0),
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total items analyzed in reporting period",
                calculation_method="Count of items included in analysis",
            ),
            "issues_found": MetricWithContext(
                value=self.metrics.issues_found,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total issues discovered during analysis",
                calculation_method="Count of issues found in reporting period data",
            ),
            "critical_issues": MetricWithContext(
                value=self.metrics.critical_issues,
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Critical issues requiring immediate attention",
                calculation_method="Count of critical priority issues",
            ),
            "potential_cost_savings": MetricWithContext(
                value=self.metrics.potential_cost_savings,
                period=MetricPeriod.MONTHLY_PROJECTION,
                unit="USD",
                description="Estimated monthly cost savings from implementing recommendations",
                calculation_method="Projected monthly savings based on reporting period analysis",
            ),
            "total_recommendations": MetricWithContext(
                value=len(self.recommendations),
                period=MetricPeriod.REPORTING_PERIOD,
                unit="count",
                description="Total recommendations generated",
                calculation_method="Count of actionable recommendations from analysis",
            ),
        }

        # Add analyzer-specific metrics from custom_metrics
        if hasattr(self.metrics, "custom_metrics"):
            for key, value in self.metrics.custom_metrics.items():
                if key.endswith("_analyzed") or key.endswith("_count"):
                    period = MetricPeriod.REPORTING_PERIOD
                    description = (
                        f"{key.replace('_', ' ').title()} from reporting period"
                    )
                elif key.endswith("_blocked") or key.startswith("waste_"):
                    period = MetricPeriod.MONTHLY_CURRENT
                    description = (
                        f"{key.replace('_', ' ').title()} at current monthly rate"
                    )
                elif key.endswith("_savings") or key.endswith("_loss"):
                    period = MetricPeriod.MONTHLY_PROJECTION
                    description = (
                        f"{key.replace('_', ' ').title()} projected monthly impact"
                    )
                else:
                    period = MetricPeriod.REPORTING_PERIOD
                    description = f"{key.replace('_', ' ').title()}"

                metrics[key] = MetricWithContext(
                    value=value,
                    period=period,
                    unit="count"
                    if isinstance(value, int)
                    else "USD"
                    if "savings" in key
                    or "cost" in key
                    or "blocked" in key
                    or "loss" in key
                    else "various",
                    description=description,
                    calculation_method=f"Calculated from {self.analyzer_name} analysis",
                )

        return EnhancedKeyMetrics(reporting_period=reporting_period, metrics=metrics)


class SearchTermAnalysisResult(AnalysisResult):
    """Result of search terms analysis."""

    analysis_type: str = Field(default="search_terms", description="Type of analysis")

    # Search terms by classification
    add_candidates: list[SearchTerm] = Field(
        default_factory=list, description="Search terms to add as keywords"
    )
    negative_candidates: list[SearchTerm] = Field(
        default_factory=list, description="Search terms to add as negatives"
    )
    already_covered: list[SearchTerm] = Field(
        default_factory=list, description="Search terms already covered by keywords"
    )
    review_needed: list[SearchTerm] = Field(
        default_factory=list, description="Search terms needing manual review"
    )

    # Summary statistics
    total_search_terms: int = Field(..., description="Total unique search terms")
    total_impressions: int = Field(..., description="Total impressions analyzed")
    total_clicks: int = Field(..., description="Total clicks analyzed")
    total_cost: float = Field(..., description="Total cost analyzed")
    total_conversions: float = Field(..., description="Total conversions analyzed")

    # Classification counts
    classification_summary: dict[SearchTermClassification, int] = Field(
        default_factory=dict, description="Count by classification"
    )

    # Local intent summary (for retail focus)
    local_intent_terms: int = Field(
        default=0, description="Count of terms with local intent"
    )
    near_me_terms: int = Field(default=0, description="Count of 'near me' searches")

    # Cost savings potential
    potential_savings: float = Field(
        default=0.0, description="Potential cost savings from negative keywords"
    )
    potential_revenue: float = Field(
        default=0.0, description="Potential revenue from new keywords"
    )

    @property
    def overall_ctr(self) -> float:
        """Calculate overall CTR."""
        return (
            (self.total_clicks / self.total_impressions * 100)
            if self.total_impressions > 0
            else 0.0
        )

    @property
    def overall_cpc(self) -> float:
        """Calculate overall CPC."""
        return self.total_cost / self.total_clicks if self.total_clicks > 0 else 0.0

    @property
    def overall_cpa(self) -> float:
        """Calculate overall CPA."""
        return (
            self.total_cost / self.total_conversions
            if self.total_conversions > 0
            else 0.0
        )

    def get_top_opportunities(self, limit: int = 10) -> list[SearchTerm]:
        """Get top keyword opportunities sorted by potential value."""
        # Sort by conversion value or conversions
        return sorted(
            self.add_candidates, key=lambda x: x.metrics.conversion_value, reverse=True
        )[:limit]

    def get_top_negatives(self, limit: int = 10) -> list[SearchTerm]:
        """Get top negative keyword candidates sorted by wasted spend."""
        # Sort by cost (wasted spend)
        return sorted(
            self.negative_candidates, key=lambda x: x.metrics.cost, reverse=True
        )[:limit]

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate a summary dictionary for reporting."""
        return {
            "analysis_date": self.created_at.isoformat(),
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "account": self.customer_id,
            "summary": {
                "total_search_terms": self.total_search_terms,
                "total_cost": round(self.total_cost, 2),
                "total_conversions": round(self.total_conversions, 2),
                "overall_cpa": round(self.overall_cpa, 2),
            },
            "classifications": {
                "add_candidates": len(self.add_candidates),
                "negative_candidates": len(self.negative_candidates),
                "already_covered": len(self.already_covered),
                "review_needed": len(self.review_needed),
            },
            "local_intent": {
                "local_intent_terms": self.local_intent_terms,
                "near_me_terms": self.near_me_terms,
            },
            "potential_impact": {
                "savings": round(self.potential_savings, 2),
                "revenue": round(self.potential_revenue, 2),
            },
            "top_recommendations": [r.title for r in self.recommendations[:5]],
        }


class KeywordMatchAnalysisResult(AnalysisResult):
    """Result of keyword match type analysis."""

    analysis_type: str = Field(default="keyword_match", description="Type of analysis")

    # Match type statistics
    match_type_stats: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Performance statistics by match type"
    )

    # Problematic keywords
    high_cost_broad_keywords: list[Any] = Field(
        default_factory=list, description="High-cost, low-ROI broad match keywords"
    )
    low_quality_keywords: list[Any] = Field(
        default_factory=list, description="Keywords with quality score < 7"
    )
    duplicate_opportunities: list[dict[str, Any]] = Field(
        default_factory=list,
        description="Opportunities to consolidate duplicate keywords",
    )

    # Summary statistics
    total_keywords: int = Field(..., description="Total keywords analyzed")
    potential_savings: float = Field(
        default=0.0, description="Potential monthly cost savings"
    )

    def get_match_type_summary(self) -> dict[str, Any]:
        """Get summary of match type performance."""
        summary = {}

        for match_type, stats in self.match_type_stats.items():
            summary[match_type] = {
                "count": stats.get("count", 0),
                "cost": round(stats.get("cost", 0), 2),
                "conversions": round(stats.get("conversions", 0), 2),
                "cpa": round(stats.get("cpa", 0), 2),
                "roas": round(stats.get("roas", 0), 2),
            }

        return summary

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate a summary dictionary for reporting."""
        return {
            "analysis_date": self.created_at.isoformat(),
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "account": self.customer_id,
            "summary": {
                "total_keywords": self.total_keywords,
                "match_type_distribution": self.get_match_type_summary(),
                "potential_savings": round(self.potential_savings, 2),
            },
            "issues": {
                "high_cost_broad": len(self.high_cost_broad_keywords),
                "low_quality": len(self.low_quality_keywords),
                "duplicate_opportunities": len(self.duplicate_opportunities),
            },
            "top_recommendations": [r.title for r in self.recommendations[:5]],
        }


class PerformanceMaxAnalysisResult(AnalysisResult):
    """Result of Performance Max campaign analysis."""

    analysis_type: str = Field(
        default="performance_max", description="Type of analysis"
    )

    # Performance Max specific data
    pmax_campaigns: list[Any] = Field(
        default_factory=list, description="Performance Max campaigns analyzed"
    )
    search_term_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Performance Max search term insights"
    )
    overlap_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Search/PMax overlap analysis"
    )
    asset_performance: dict[str, Any] = Field(
        default_factory=dict, description="Asset performance analysis"
    )
    budget_allocation: dict[str, Any] = Field(
        default_factory=dict, description="Budget allocation transparency analysis"
    )
    channel_performance: dict[str, Any] = Field(
        default_factory=dict, description="Channel-level performance breakdown"
    )

    # Summary fields
    total_pmax_campaigns: int = Field(default=0, description="Total PMax campaigns")
    total_pmax_spend: float = Field(default=0.0, description="Total PMax spend")
    total_pmax_conversions: float = Field(
        default=0.0, description="Total PMax conversions"
    )
    avg_pmax_roas: float = Field(default=0.0, description="Average PMax ROAS")
    overlap_percentage: float = Field(
        default=0.0, description="Search term overlap percentage"
    )

    # Findings
    findings: list[dict[str, Any]] = Field(
        default_factory=list, description="Analysis findings"
    )

    # Summary dictionary for compatibility
    summary: dict[str, Any] = Field(
        default_factory=dict, description="Analysis summary"
    )

    # Additional metrics dictionary for compatibility
    additional_metrics: dict[str, float] = Field(
        default_factory=dict, description="Additional key metrics"
    )

    def get_high_priority_issues(self) -> list[dict[str, Any]]:
        """Get high priority findings."""
        return [f for f in self.findings if f.get("severity") == "HIGH"]

    def get_optimization_opportunities(self) -> int:
        """Get count of optimization opportunities."""
        return len(
            [
                r
                for r in self.recommendations
                if r.priority
                in [RecommendationPriority.HIGH, RecommendationPriority.CRITICAL]
            ]
        )

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate a summary dictionary for reporting."""
        return {
            "analysis_date": self.created_at.isoformat(),
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "account": self.customer_id,
            "summary": {
                "total_campaigns": self.total_pmax_campaigns,
                "total_spend": round(self.total_pmax_spend, 2),
                "total_conversions": round(self.total_pmax_conversions, 2),
                "average_roas": round(self.avg_pmax_roas, 2),
                "overlap_percentage": round(self.overlap_percentage, 1),
            },
            "findings": {
                "total_findings": len(self.findings),
                "high_priority": len(self.get_high_priority_issues()),
                "optimization_opportunities": self.get_optimization_opportunities(),
            },
            "top_recommendations": [r.title for r in self.recommendations[:5]],
        }


class CampaignOverlapAnalysisResult(AnalysisResult):
    """Result of campaign overlap analysis."""

    analysis_type: str = Field(
        default="campaign_overlap", description="Type of analysis"
    )

    # Campaign overlap specific data
    channel_performance: dict[str, Any] = Field(
        default_factory=dict, description="Channel-level performance breakdown"
    )
    overlap_analysis: dict[str, Any] = Field(
        default_factory=dict, description="Campaign overlap detection results"
    )
    brand_conflicts: dict[str, Any] = Field(
        default_factory=dict, description="Brand exclusion conflict analysis"
    )
    budget_optimization: dict[str, Any] = Field(
        default_factory=dict, description="Budget optimization opportunities"
    )

    # Summary fields
    total_campaigns: int = Field(default=0, description="Total campaigns analyzed")
    total_spend: float = Field(
        default=0.0, description="Total spend across all campaigns"
    )
    total_conversions: float = Field(default=0.0, description="Total conversions")
    avg_roas: float = Field(default=0.0, description="Average ROAS across campaigns")
    overlap_count: int = Field(
        default=0, description="Number of overlapping campaign pairs"
    )
    total_overlap_cost: float = Field(
        default=0.0, description="Total cost from overlapping campaigns"
    )

    def get_high_priority_overlaps(self) -> list[dict[str, Any]]:
        """Get high priority overlapping campaigns."""
        return self.overlap_analysis.get("high_conflict_overlaps", [])

    def get_optimization_opportunities(self) -> list[dict[str, Any]]:
        """Get budget optimization opportunities."""
        return self.budget_optimization.get("opportunities", [])

    def get_channel_insights(self) -> list[dict[str, Any]]:
        """Get channel-level insights."""
        return self.channel_performance.get("insights", [])

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate a summary dictionary for reporting."""
        return {
            "analysis_date": self.created_at.isoformat(),
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "account": self.customer_id,
            "summary": {
                "total_campaigns": self.total_campaigns,
                "total_spend": round(self.total_spend, 2),
                "total_conversions": round(self.total_conversions, 2),
                "average_roas": round(self.avg_roas, 2),
                "overlap_count": self.overlap_count,
                "total_overlap_cost": round(self.total_overlap_cost, 2),
            },
            "insights": {
                "channel_count": len(self.channel_performance.get("channels", [])),
                "high_priority_overlaps": len(self.get_high_priority_overlaps()),
                "optimization_opportunities": len(
                    self.get_optimization_opportunities()
                ),
                "potential_savings": round(
                    self.budget_optimization.get("total_potential_savings", 0), 2
                ),
            },
            "top_recommendations": [r.title for r in self.recommendations[:5]],
        }


class PlacementCategory(str, Enum):
    """Categories for placement classification."""

    NEWS = "NEWS"
    ENTERTAINMENT = "ENTERTAINMENT"
    RETAIL = "RETAIL"
    HEALTH = "HEALTH"
    FINANCE = "FINANCE"
    TECHNOLOGY = "TECHNOLOGY"
    TRAVEL = "TRAVEL"
    SPORTS = "SPORTS"
    EDUCATION = "EDUCATION"
    FOOD = "FOOD"
    AUTOMOTIVE = "AUTOMOTIVE"
    REAL_ESTATE = "REAL_ESTATE"
    GAMING = "GAMING"
    SOCIAL = "SOCIAL"
    OTHER = "OTHER"
    UNKNOWN = "UNKNOWN"


class PlacementQualityScore(str, Enum):
    """Quality score ratings for placements."""

    EXCELLENT = "EXCELLENT"  # 90-100
    GOOD = "GOOD"  # 75-89
    FAIR = "FAIR"  # 60-74
    POOR = "POOR"  # 40-59
    VERY_POOR = "VERY_POOR"  # 0-39


class PlacementType(str, Enum):
    """Types of placements."""

    WEBSITE = "WEBSITE"
    MOBILE_APP = "MOBILE_APP"
    VIDEO = "VIDEO"
    YOUTUBE_VIDEO = "YOUTUBE_VIDEO"
    YOUTUBE_CHANNEL = "YOUTUBE_CHANNEL"
    UNKNOWN = "UNKNOWN"


class PlacementMetrics(BasePSNModel):
    """Performance metrics for a placement."""

    impressions: int = Field(default=0, description="Total impressions")
    clicks: int = Field(default=0, description="Total clicks")
    cost: float = Field(default=0.0, description="Total cost")
    conversions: float = Field(default=0.0, description="Total conversions")
    conversion_value: float = Field(default=0.0, description="Total conversion value")
    ctr: float = Field(default=0.0, description="Click-through rate")
    cpc: float = Field(default=0.0, description="Cost per click")
    cpa: float = Field(default=0.0, description="Cost per acquisition")
    roas: float = Field(default=0.0, description="Return on ad spend")


class Placement(BasePSNModel):
    """A placement where ads are shown."""

    # Identification
    placement_id: str = Field(..., description="Placement identifier")
    placement_name: str = Field(..., description="Placement name or URL")
    display_name: str = Field(..., description="Display name for the placement")

    # Classification
    placement_type: PlacementType = Field(..., description="Type of placement")
    category: PlacementCategory = Field(..., description="Content category")
    quality_score: PlacementQualityScore = Field(..., description="Quality rating")

    # Characteristics
    is_brand_safe: bool = Field(default=True, description="Brand safety status")
    is_relevant: bool = Field(default=True, description="Relevance to campaign")
    character_set: str | None = Field(None, description="Character set (language)")
    country_code: str | None = Field(None, description="Country code")

    # Performance
    metrics: PlacementMetrics = Field(..., description="Performance metrics")

    # Associated campaigns
    campaign_ids: list[str] = Field(
        default_factory=list, description="Associated campaigns"
    )
    ad_group_ids: list[str] = Field(
        default_factory=list, description="Associated ad groups"
    )

    # Flags
    is_excluded: bool = Field(default=False, description="Currently excluded")
    exclusion_reason: str | None = Field(None, description="Reason for exclusion")

    @property
    def is_underperforming(self) -> bool:
        """Check if placement is underperforming."""
        # Consider underperforming if CTR < 0.5% or CPA > 3x average
        return self.metrics.ctr < 0.5 or self.quality_score in [
            PlacementQualityScore.POOR,
            PlacementQualityScore.VERY_POOR,
        ]

    @property
    def is_high_cost(self) -> bool:
        """Check if placement has high cost with poor performance."""
        return self.metrics.cost > 100.0 and self.metrics.cpa > 50.0

    @property
    def spam_risk_score(self) -> float:
        """Calculate spam risk score (0-100)."""
        score = 0.0

        # High volume, low quality indicators
        if self.metrics.impressions > 10000 and self.metrics.ctr < 0.1:
            score += 30.0

        # Poor quality score
        if self.quality_score == PlacementQualityScore.VERY_POOR:
            score += 40.0
        elif self.quality_score == PlacementQualityScore.POOR:
            score += 20.0

        # High cost, no conversions
        if self.metrics.cost > 50.0 and self.metrics.conversions == 0:
            score += 30.0

        return min(score, 100.0)


class PlacementAuditAnalysisResult(AnalysisResult):
    """Result of placement audit analysis."""

    analysis_type: str = Field(
        default="placement_audit", description="Type of analysis"
    )

    # Placement analysis data
    all_placements: list[Placement] = Field(
        default_factory=list, description="All placements analyzed"
    )
    underperforming_placements: list[Placement] = Field(
        default_factory=list, description="Underperforming placements"
    )
    high_cost_placements: list[Placement] = Field(
        default_factory=list, description="High-cost, poor-performing placements"
    )
    spam_placements: list[Placement] = Field(
        default_factory=list, description="Suspected spam placements"
    )
    exclusion_recommendations: list[Placement] = Field(
        default_factory=list, description="Placements recommended for exclusion"
    )

    # Category analysis
    category_performance: dict[PlacementCategory, dict[str, Any]] = Field(
        default_factory=dict, description="Performance by category"
    )

    # Quality analysis
    quality_distribution: dict[PlacementQualityScore, int] = Field(
        default_factory=dict, description="Distribution of quality scores"
    )

    # Character set analysis
    character_set_analysis: dict[str, dict[str, Any]] = Field(
        default_factory=dict, description="Performance by character set"
    )

    # Summary statistics
    total_placements: int = Field(default=0, description="Total placements analyzed")
    total_placement_cost: float = Field(
        default=0.0, description="Total cost across all placements"
    )
    total_placement_conversions: float = Field(
        default=0.0, description="Total conversions from placements"
    )
    avg_placement_ctr: float = Field(default=0.0, description="Average placement CTR")
    avg_placement_cpa: float = Field(default=0.0, description="Average placement CPA")

    # Potential savings
    potential_cost_savings: float = Field(
        default=0.0, description="Potential monthly savings from exclusions"
    )
    wasted_spend_percentage: float = Field(
        default=0.0, description="Percentage of spend on poor placements"
    )

    def get_top_exclusion_candidates(self, limit: int = 20) -> list[Placement]:
        """Get top placement exclusion candidates by cost impact."""
        return sorted(
            self.exclusion_recommendations, key=lambda x: x.metrics.cost, reverse=True
        )[:limit]

    def get_placements_by_category(
        self, category: PlacementCategory
    ) -> list[Placement]:
        """Get placements filtered by category."""
        return [p for p in self.all_placements if p.category == category]

    def get_placements_by_quality(
        self, quality: PlacementQualityScore
    ) -> list[Placement]:
        """Get placements filtered by quality score."""
        return [p for p in self.all_placements if p.quality_score == quality]

    def get_non_english_placements(self) -> list[Placement]:
        """Get placements with non-English character sets."""
        return [
            p
            for p in self.all_placements
            if p.character_set
            and p.character_set.lower() not in ["latin", "english", "en"]
        ]

    def to_summary_dict(self) -> dict[str, Any]:
        """Generate a summary dictionary for reporting."""
        return {
            "analysis_date": self.created_at.isoformat(),
            "date_range": f"{self.start_date.date()} to {self.end_date.date()}",
            "account": self.customer_id,
            "summary": {
                "total_placements": self.total_placements,
                "total_cost": round(self.total_placement_cost, 2),
                "total_conversions": round(self.total_placement_conversions, 2),
                "average_ctr": round(self.avg_placement_ctr, 2),
                "average_cpa": round(self.avg_placement_cpa, 2),
                "wasted_spend_percentage": round(self.wasted_spend_percentage, 1),
            },
            "issues": {
                "underperforming_placements": len(self.underperforming_placements),
                "high_cost_placements": len(self.high_cost_placements),
                "spam_placements": len(self.spam_placements),
                "exclusion_recommendations": len(self.exclusion_recommendations),
            },
            "potential_impact": {
                "cost_savings": round(self.potential_cost_savings, 2),
                "placements_to_exclude": len(self.get_top_exclusion_candidates()),
            },
            "quality_distribution": {
                str(quality): count
                for quality, count in self.quality_distribution.items()
            },
            "top_recommendations": [r.title for r in self.recommendations[:5]],
        }
