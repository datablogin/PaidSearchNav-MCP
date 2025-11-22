"""Device performance data models."""

from datetime import datetime
from enum import Enum
from typing import Optional

from pydantic import BaseModel, ConfigDict, Field, computed_field

from paidsearchnav.core.models.analysis import AnalysisResult


class DeviceType(str, Enum):
    """Supported device types."""

    MOBILE = "Mobile phones"
    DESKTOP = "Computers"
    TABLET = "Tablets"
    UNKNOWN = "Unknown"


class DevicePerformanceData(BaseModel):
    """Device performance data for a specific device type."""

    model_config = ConfigDict(str_strip_whitespace=True)

    customer_id: str
    campaign_id: str
    campaign_name: str
    ad_group_id: Optional[str] = None
    ad_group_name: Optional[str] = None
    device_type: DeviceType
    level: str = "Campaign"  # Campaign or Ad group level

    # Bid adjustments
    bid_adjustment: float = 0.0
    ad_group_bid_adjustment: Optional[float] = None

    # Performance metrics
    impressions: int = 0
    clicks: int = 0
    conversions: float = 0.0
    cost_micros: int = 0
    conversion_value_micros: int = 0

    # Date range
    start_date: datetime
    end_date: datetime

    @computed_field
    def cost(self) -> float:
        """Cost in account currency."""
        return self.cost_micros / 1_000_000

    @computed_field
    def conversion_value(self) -> float:
        """Conversion value in account currency."""
        return self.conversion_value_micros / 1_000_000

    @computed_field
    def ctr(self) -> float:
        """Click-through rate."""
        return self.clicks / self.impressions if self.impressions > 0 else 0.0

    @computed_field
    def avg_cpc(self) -> float:
        """Average cost per click."""
        return self.cost / self.clicks if self.clicks > 0 else 0.0

    @computed_field
    def conversion_rate(self) -> float:
        """Conversion rate."""
        return self.conversions / self.clicks if self.clicks > 0 else 0.0

    @computed_field
    def cpa(self) -> float:
        """Cost per acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @computed_field
    def roas(self) -> float:
        """Return on ad spend."""
        return self.conversion_value / self.cost if self.cost > 0 else 0.0


class DeviceShareMetrics(BaseModel):
    """Device share metrics across all device types."""

    device_type: DeviceType
    click_share: float = 0.0
    impression_share: float = 0.0
    cost_share: float = 0.0
    conversion_share: float = 0.0
    conversion_value_share: float = 0.0


class DeviceInsight(BaseModel):
    """Performance insight for a specific device type."""

    device_type: DeviceType
    performance_score: float = Field(ge=0, le=100)
    cpc_vs_average: float
    conversion_rate_vs_average: float
    roas_vs_average: float

    # Share metrics
    click_share: float
    cost_share: float
    conversion_share: float

    # Recommendations
    recommended_action: str
    bid_adjustment_recommendation: str
    budget_recommendation: str
    optimization_opportunity: str


class DevicePerformanceSummary(BaseModel):
    """Overall device performance summary."""

    customer_id: str
    analysis_date: datetime
    date_range_start: datetime
    date_range_end: datetime

    # Totals
    total_devices: int
    total_cost: float
    total_conversions: float
    total_clicks: int
    total_impressions: int

    # Averages
    average_cpc: float
    average_conversion_rate: float
    average_roas: float

    # Device distribution
    device_distribution: dict[str, int]

    # Performance analysis
    cpc_variance_percentage: float
    conversion_rate_variance_percentage: float
    optimization_potential: float

    # Top opportunities
    mobile_optimization_needed: bool = False
    desktop_opportunity: bool = False
    tablet_underperformance: bool = False


class DevicePerformanceAnalysisResult(AnalysisResult):
    """Complete device performance analysis result."""

    analysis_type: str = Field(
        default="device_performance", description="Type of analysis"
    )
    analyzer_name: str = Field(
        default="device_performance", description="Name of analyzer used"
    )

    # Core data
    performance_data: list[DevicePerformanceData]
    summary: DevicePerformanceSummary
    device_shares: list[DeviceShareMetrics]
    insights: list[DeviceInsight]

    # Recommendations
    device_recommendations: list[str]
    bid_adjustment_recommendations: dict[str, float]

    # Dashboard metrics
    dashboard_metrics: dict[str, float]

    # Analysis metadata
    analysis_date: datetime = Field(default_factory=datetime.utcnow)
    data_quality_score: float = Field(default=100.0, ge=0, le=100)
    recommendations_count: int = 0

    def model_post_init(self, __context) -> None:
        """Set computed fields after initialization."""
        self.recommendations_count = len(self.device_recommendations)
