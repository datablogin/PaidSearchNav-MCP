"""Extended Google Ads models for additional report types."""

from enum import Enum
from typing import Optional

from pydantic import Field

from paidsearchnav.core.models.base import BasePSNModel


class DeviceType(str, Enum):
    """Device types in Google Ads."""

    MOBILE = "Mobile phones"
    DESKTOP = "Computers"
    TABLET = "Tablets"
    TV = "TV screens"
    OTHER = "Other"


class DevicePerformance(BasePSNModel):
    """Device performance data from Google Ads device report."""

    # Identifiers
    device: DeviceType = Field(..., description="Device type")
    level: str = Field(..., description="Aggregation level (Campaign or Ad group)")
    campaign_name: str = Field(..., description="Campaign name")
    campaign_id: Optional[str] = Field(None, description="Campaign ID")
    ad_group_name: Optional[str] = Field(None, description="Ad group name")
    ad_group_id: Optional[str] = Field(None, description="Ad group ID")

    # Bid adjustments
    bid_adjustment: Optional[float] = Field(None, description="Device bid adjustment")
    ad_group_bid_adjustment: Optional[float] = Field(
        None, description="Ad group level bid adjustment"
    )

    # Performance metrics
    clicks: int = Field(0, description="Number of clicks")
    impressions: int = Field(0, description="Number of impressions")
    ctr: Optional[float] = Field(None, description="Click-through rate")
    avg_cpc: Optional[float] = Field(None, description="Average cost per click")
    cost: float = Field(0.0, description="Total cost")
    conversions: float = Field(0.0, description="Number of conversions")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate")
    cpa: Optional[float] = Field(None, description="Cost per acquisition")

    # Metadata
    currency_code: str = Field("USD", description="Currency code")
    date_range: Optional[str] = Field(None, description="Date range for the data")


class AdSchedulePerformance(BasePSNModel):
    """Ad schedule/dayparting performance data."""

    # Schedule information
    day_time: str = Field(..., description="Day and time segment")
    day_of_week: Optional[str] = Field(
        None, description="Day of week extracted from day_time"
    )
    hour_range: Optional[str] = Field(
        None, description="Hour range extracted from day_time"
    )
    bid_adjustment: Optional[float] = Field(None, description="Schedule bid adjustment")

    # Performance metrics
    clicks: int = Field(0, description="Number of clicks")
    impressions: int = Field(0, description="Number of impressions")
    ctr: Optional[float] = Field(None, description="Click-through rate")
    avg_cpc: Optional[float] = Field(None, description="Average cost per click")
    cost: float = Field(0.0, description="Total cost")
    conversions: float = Field(0.0, description="Number of conversions")
    conversion_rate: Optional[float] = Field(None, description="Conversion rate")
    cpa: Optional[float] = Field(None, description="Cost per acquisition")

    # Metadata
    currency_code: str = Field("USD", description="Currency code")
    campaign_name: Optional[str] = Field(None, description="Campaign name if available")
    campaign_id: Optional[str] = Field(None, description="Campaign ID if available")


class StorePerformance(BasePSNModel):
    """Store-level performance data for location extensions."""

    # Store information
    store_name: str = Field(..., description="Store location name")
    address_line_1: str = Field(..., description="Store address line 1")
    address_line_2: Optional[str] = Field(None, description="Store address line 2")
    city: str = Field(..., description="City")
    state: str = Field(..., description="State/Province")
    postal_code: str = Field(..., description="Postal/ZIP code")
    country_code: str = Field("US", description="Country code")
    phone_number: Optional[str] = Field(None, description="Store phone number")

    # Local performance metrics
    local_impressions: int = Field(0, description="Local reach impressions")
    call_clicks: int = Field(0, description="Clicks on call button")
    driving_directions: int = Field(0, description="Driving direction requests")
    website_visits: int = Field(0, description="Website visits from store listing")

    # Calculated metrics
    @property
    def total_engagements(self) -> int:
        """Total engagement actions."""
        return self.call_clicks + self.driving_directions + self.website_visits

    @property
    def engagement_rate(self) -> Optional[float]:
        """Engagement rate (engagements/impressions)."""
        if self.local_impressions > 0:
            return self.total_engagements / self.local_impressions
        return None


class AuctionInsights(BasePSNModel):
    """Auction insights data for competitive analysis."""

    # Competitor information
    competitor_domain: str = Field(..., description="Competitor's display URL domain")

    # Competition metrics
    impression_share: Optional[float] = Field(None, description="Your impression share")
    overlap_rate: Optional[float] = Field(
        None, description="How often competitor showed with you"
    )
    top_of_page_rate: Optional[float] = Field(
        None, description="Competitor's top of page rate"
    )
    abs_top_of_page_rate: Optional[float] = Field(
        None, description="Competitor's absolute top rate"
    )
    outranking_share: Optional[float] = Field(
        None, description="How often you ranked above competitor"
    )
    position_above_rate: Optional[float] = Field(
        None, description="How often competitor was above you"
    )

    # Context
    campaign_name: Optional[str] = Field(None, description="Campaign name")
    campaign_id: Optional[str] = Field(None, description="Campaign ID")
    date_range: Optional[str] = Field(None, description="Date range for the data")

    @property
    def competitive_pressure(self) -> str:
        """Categorize competitive pressure level."""
        if self.overlap_rate is None:
            return "unknown"

        if self.overlap_rate > 0.7:
            return "high"
        elif self.overlap_rate > 0.4:
            return "medium"
        else:
            return "low"
