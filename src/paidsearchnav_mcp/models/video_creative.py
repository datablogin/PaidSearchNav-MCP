"""Video and creative asset performance data models."""

from __future__ import annotations

from datetime import datetime
from enum import Enum
from typing import Any, Optional

from paidsearchnav.core.models.analysis import AnalysisResult
from paidsearchnav.core.models.base import BasePSNModel


class AssetType(str, Enum):
    """Types of creative assets."""

    BUSINESS_LOGO = "Business logo"
    VIDEO = "Video"
    IMAGE = "Image"
    HEADLINE = "Headline"
    DESCRIPTION = "Description"
    UNKNOWN = "Unknown"


class AssetSource(str, Enum):
    """Source of creative asset creation."""

    AUTOMATIC = "Automatically created"
    MANUAL = "Manually created"
    UNKNOWN = "Unknown"


class AssetStatus(str, Enum):
    """Status of creative assets."""

    ENABLED = "Enabled"
    PAUSED = "Paused"
    REMOVED = "Removed"
    UNKNOWN = "Unknown"


class ChannelLinkedStatus(str, Enum):
    """YouTube channel linking status."""

    LINKED = "Linked"
    NOT_LINKED = "Not Linked"
    UNKNOWN = "Unknown"


class VideoPerformance(BasePSNModel):
    """Performance metrics for video content."""

    video_title: str
    video_url: Optional[str] = None
    duration: Optional[str] = None  # Format like "0:15"
    duration_seconds: Optional[int] = None
    channel_name: Optional[str] = None
    channel_linked_status: ChannelLinkedStatus = ChannelLinkedStatus.UNKNOWN
    video_enhancements: Optional[int] = None
    impressions: int = 0
    views: int = 0
    currency_code: str = "USD"
    avg_cpm: float = 0.0
    cost: float = 0.0
    conversions: float = 0.0
    cost_per_conversion: float = 0.0
    conv_value_cost_ratio: float = 0.0

    # Calculated metrics
    view_rate: float = 0.0
    cost_per_view: float = 0.0
    is_shorts: bool = False

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._calculate_derived_metrics()
        self._parse_duration()
        self._detect_shorts()

    def _calculate_derived_metrics(self) -> None:
        """Calculate derived performance metrics."""
        # View rate
        if self.impressions > 0:
            self.view_rate = (self.views / self.impressions) * 100

        # Cost per view
        if self.views > 0:
            self.cost_per_view = self.cost / self.views

    def _parse_duration(self) -> None:
        """Parse duration string to seconds."""
        if self.duration:
            try:
                # Parse format like "0:15" or "1:30"
                parts = self.duration.split(":")
                if len(parts) == 2:
                    minutes = int(parts[0])
                    seconds = int(parts[1])
                    self.duration_seconds = minutes * 60 + seconds
                elif len(parts) == 3:
                    hours = int(parts[0])
                    minutes = int(parts[1])
                    seconds = int(parts[2])
                    self.duration_seconds = hours * 3600 + minutes * 60 + seconds
            except (ValueError, IndexError):
                self.duration_seconds = None

    def _detect_shorts(self) -> None:
        """Detect if video is a YouTube Short."""
        if self.video_title:
            self.is_shorts = (
                "shorts" in self.video_title.lower()
                or "short" in self.video_title.lower()
            )

        # Also check duration (Shorts are typically ≤60 seconds)
        if self.duration_seconds and self.duration_seconds <= 60:
            self.is_shorts = True


class CreativeAsset(BasePSNModel):
    """Performance metrics for creative assets."""

    asset_url: str
    asset_type: AssetType = AssetType.UNKNOWN
    asset_status: AssetStatus = AssetStatus.UNKNOWN
    level: str = ""
    status_reason: Optional[str] = None
    source: AssetSource = AssetSource.UNKNOWN
    last_updated: Optional[datetime] = None
    currency_code: str = "USD"
    avg_cpm: float = 0.0
    impressions: int = 0
    interactions: int = 0
    interaction_rate: float = 0.0
    avg_cost: float = 0.0
    cost: float = 0.0
    clicks: int = 0
    conversions: float = 0.0
    conv_value: float = 0.0

    # Calculated metrics
    cost_per_click: float = 0.0
    cost_per_conversion: float = 0.0
    conversion_rate: float = 0.0
    roas: float = 0.0  # Return on Ad Spend

    def __init__(self, **data: Any):
        super().__init__(**data)
        self._calculate_derived_metrics()

    def _calculate_derived_metrics(self) -> None:
        """Calculate derived performance metrics."""
        # Cost per click
        if self.clicks > 0:
            self.cost_per_click = self.cost / self.clicks

        # Cost per conversion
        if self.conversions > 0:
            self.cost_per_conversion = self.cost / self.conversions

        # Conversion rate
        if self.clicks > 0:
            self.conversion_rate = (self.conversions / self.clicks) * 100

        # Return on Ad Spend
        if self.cost > 0:
            self.roas = self.conv_value / self.cost


class VideoCreativeMetrics(BasePSNModel):
    """Combined video and creative asset performance metrics."""

    video_count: int = 0
    asset_count: int = 0
    total_impressions: int = 0
    total_views: int = 0
    total_cost: float = 0.0
    total_conversions: float = 0.0
    total_conv_value: float = 0.0

    # Aggregated performance metrics
    avg_view_rate: float = 0.0
    avg_cost_per_view: float = 0.0
    avg_cost_per_conversion: float = 0.0
    total_roas: float = 0.0

    # Content insights
    shorts_performance_ratio: float = 0.0  # Shorts vs regular video performance
    auto_vs_manual_asset_ratio: float = 0.0  # Auto vs manual asset performance
    top_performing_duration_range: Optional[str] = None


class CreativeRecommendation(BasePSNModel):
    """Optimization recommendation for creative assets."""

    recommendation_type: str
    priority: str  # "high", "medium", "low"
    title: str
    description: str
    impact_potential: float  # Estimated percentage improvement
    current_performance: float
    target_performance: float
    affected_assets: list[str]
    action_items: list[str]


class VideoCreativeInsight(BasePSNModel):
    """Insights from video and creative analysis."""

    insight_type: str
    category: str  # "performance", "optimization", "trend", "opportunity"
    title: str
    description: str
    supporting_data: dict[str, Any]
    confidence_score: float  # 0-100
    business_impact: str  # "high", "medium", "low"


class VideoCreativeAnalysisSummary(BasePSNModel):
    """Summary of video and creative asset analysis."""

    analysis_period: str
    total_videos_analyzed: int
    total_assets_analyzed: int
    top_performing_videos: list[str]
    bottom_performing_videos: list[str]
    top_performing_assets: list[str]
    bottom_performing_assets: list[str]
    key_insights_count: int
    recommendations_count: int
    overall_performance_score: float  # 0-100


class VideoCreativeAnalysisResult(AnalysisResult):
    """Complete result of video and creative asset analysis."""

    video_performances: list[VideoPerformance]
    creative_assets: list[CreativeAsset]
    combined_metrics: VideoCreativeMetrics
    insights: list[VideoCreativeInsight]
    video_creative_recommendations: list[
        CreativeRecommendation
    ]  # Renamed to avoid conflict
    summary: VideoCreativeAnalysisSummary

    # Data quality metrics
    video_coverage_percentage: float = 0.0
    asset_coverage_percentage: float = 0.0
    data_quality_score: float = 0.0

    # Business KPIs
    performance_variance_detected: bool = False
    optimization_opportunities_count: int = 0
    estimated_budget_reallocation_potential: float = 0.0
