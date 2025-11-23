"""Campaign data models."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from paidsearchnav_mcp.models.base import BasePSNModel


class CampaignStatus(str, Enum):
    """Campaign status values."""

    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"
    UNKNOWN = "UNKNOWN"


class CampaignType(str, Enum):
    """Campaign type values."""

    SEARCH = "SEARCH"
    DISPLAY = "DISPLAY"
    SHOPPING = "SHOPPING"
    VIDEO = "VIDEO"
    APP = "APP"
    SMART = "SMART"
    LOCAL = "LOCAL"
    HOTEL = "HOTEL"
    PERFORMANCE_MAX = "PERFORMANCE_MAX"
    DEMAND_GEN = "DEMAND_GEN"  # Demand Gen campaigns (newer campaign type)
    MULTI_CHANNEL = "MULTI_CHANNEL"  # Multi-channel campaigns
    UNKNOWN = "UNKNOWN"


class BiddingStrategy(str, Enum):
    """Bidding strategy types."""

    MANUAL_CPC = "MANUAL_CPC"
    MANUAL_CPV = "MANUAL_CPV"
    MANUAL_CPM = "MANUAL_CPM"
    TARGET_CPA = "TARGET_CPA"
    TARGET_CPM = "TARGET_CPM"  # Target CPM bidding
    TARGET_ROAS = "TARGET_ROAS"
    TARGET_SPEND = "TARGET_SPEND"
    MAXIMIZE_CONVERSIONS = "MAXIMIZE_CONVERSIONS"
    MAXIMIZE_CONVERSION_VALUE = "MAXIMIZE_CONVERSION_VALUE"
    TARGET_IMPRESSION_SHARE = "TARGET_IMPRESSION_SHARE"
    MAXIMIZE_CLICKS = "MAXIMIZE_CLICKS"
    UNKNOWN = "UNKNOWN"


class Campaign(BasePSNModel):
    """Google Ads campaign representation."""

    campaign_id: str = Field(..., description="Google Ads campaign ID")
    customer_id: str = Field(..., description="Google Ads customer ID")
    name: str = Field(..., description="Campaign name")
    status: CampaignStatus = Field(..., description="Campaign status")
    type: CampaignType = Field(..., description="Campaign type")

    # Budget and bidding
    budget_amount: float = Field(..., description="Daily budget in account currency")
    budget_currency: str = Field(..., description="Budget currency from account")
    bidding_strategy: BiddingStrategy = Field(..., description="Bidding strategy type")
    target_cpa: float | None = Field(None, description="Target CPA if applicable")
    target_roas: float | None = Field(None, description="Target ROAS if applicable")

    # Dates
    start_date: datetime | None = Field(None, description="Campaign start date")
    end_date: datetime | None = Field(None, description="Campaign end date")

    # Performance metrics (optional, populated when available)
    impressions: int = Field(default=0, description="Total impressions")
    clicks: int = Field(default=0, description="Total clicks")
    cost: float = Field(default=0.0, description="Total cost in account currency")
    conversions: float = Field(default=0.0, description="Total conversions")
    conversion_value: float = Field(default=0.0, description="Total conversion value")

    # Settings
    network_settings: dict = Field(
        default_factory=dict, description="Network targeting settings"
    )
    geo_targets: list[str] = Field(
        default_factory=list, description="Geographic targets"
    )
    language_targets: list[str] = Field(
        default_factory=list, description="Language targets"
    )

    # Tracking
    tracking_url_template: str | None = Field(None, description="Tracking URL template")

    @field_validator("impressions", "clicks", mode="before")
    @classmethod
    def clean_integer_fields(cls, v: Any) -> int:
        """Clean and validate integer metric fields."""
        from paidsearchnav_mcp.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return int(cleaned) if cleaned is not None else 0

    @field_validator(
        "budget_amount", "cost", "conversions", "conversion_value", mode="before"
    )
    @classmethod
    def clean_required_float_fields(cls, v: Any) -> float:
        """Clean and validate required float metric fields."""
        from paidsearchnav_mcp.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return float(cleaned) if cleaned is not None else 0.0

    @field_validator("target_cpa", "target_roas", mode="before")
    @classmethod
    def clean_optional_float_fields(cls, v: Any) -> float | None:
        """Clean and validate optional float metric fields."""
        from paidsearchnav_mcp.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return float(cleaned) if cleaned is not None else None

    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @property
    def avg_cpc(self) -> float:
        """Calculate Average Cost Per Click."""
        return self.cost / self.clicks if self.clicks > 0 else 0.0

    @property
    def conversion_rate(self) -> float:
        """Calculate Conversion Rate."""
        return (self.conversions / self.clicks * 100) if self.clicks > 0 else 0.0

    @property
    def cpa(self) -> float:
        """Calculate Cost Per Acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @property
    def roas(self) -> float:
        """Calculate Return on Ad Spend."""
        return self.conversion_value / self.cost if self.cost > 0 else 0.0
