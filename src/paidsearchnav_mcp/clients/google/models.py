"""Google Ads specific models and data structures."""

from enum import Enum

from pydantic import BaseModel, Field


class GoogleAdsConfig(BaseModel):
    """Configuration for Google Ads API client."""

    # Required authentication fields
    developer_token: str = Field(..., description="Google Ads developer token")
    client_id: str = Field(..., description="OAuth2 client ID")
    client_secret: str = Field(..., description="OAuth2 client secret")
    refresh_token: str = Field(..., description="OAuth2 refresh token")

    # Optional fields
    login_customer_id: str | None = Field(
        None, description="Login customer ID for MCC accounts"
    )

    # API settings
    api_version: str = Field("v18", description="Google Ads API version")
    use_proto_plus: bool = Field(True, description="Whether to use proto-plus messages")

    model_config = {
        # Don't allow extra fields
        "extra": "forbid",
        # Validate assignment
        "validate_assignment": True,
    }


class AdGroup(BaseModel):
    """Google Ads ad group model."""

    ad_group_id: str = Field(..., description="Google Ads ad group ID")
    campaign_id: str = Field(..., description="Parent campaign ID")
    name: str = Field(..., description="Ad group name")
    status: str = Field(..., description="Ad group status")

    # Bidding
    cpc_bid_micros: int | None = Field(
        None, description="Default max CPC bid in micros"
    )

    # Performance metrics (optional)
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cost: float = Field(default=0.0)
    conversions: float = Field(default=0.0)
    conversion_value: float = Field(default=0.0)


class NegativeKeyword(BaseModel):
    """Negative keyword model."""

    id: str = Field(..., description="Negative keyword ID")
    text: str = Field(..., description="Negative keyword text")
    match_type: str = Field(..., description="Match type (EXACT, PHRASE, BROAD)")
    level: str = Field(
        ..., description="Level where negative is applied (account, campaign, ad_group)"
    )

    # Location info
    campaign_id: str | None = Field(
        None, description="Campaign ID if campaign or ad group level"
    )
    campaign_name: str | None = Field(None, description="Campaign name")
    ad_group_id: str | None = Field(None, description="Ad group ID if ad group level")
    ad_group_name: str | None = Field(None, description="Ad group name")

    # For shared sets
    shared_set_id: str | None = Field(
        None, description="Shared set ID if from shared set"
    )
    shared_set_name: str | None = Field(None, description="Shared set name")


class GeoTargetType(str, Enum):
    """Geographic targeting types."""

    COUNTRY = "COUNTRY"
    STATE = "STATE"
    CITY = "CITY"
    POSTAL_CODE = "POSTAL_CODE"
    DMA_REGION = "DMA_REGION"
    COUNTY = "COUNTY"
    AIRPORT = "AIRPORT"
    CONGRESSIONAL_DISTRICT = "CONGRESSIONAL_DISTRICT"
    OTHER = "OTHER"


class GeoPerformance(BaseModel):
    """Geographic performance data."""

    # Location info
    campaign_id: str = Field(..., description="Campaign ID")
    location_id: str = Field(..., description="Google Ads location criterion ID")
    location_name: str = Field(..., description="Location name (e.g., 'New York, NY')")
    location_type: GeoTargetType = Field(..., description="Type of location")

    # Hierarchy
    country_code: str | None = Field(None, description="Country code (e.g., 'US')")
    state: str | None = Field(None, description="State or province name")
    city: str | None = Field(None, description="City name")
    postal_code: str | None = Field(None, description="Postal/ZIP code")

    # Performance metrics
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cost: float = Field(default=0.0)
    conversions: float = Field(default=0.0)
    conversion_value: float = Field(default=0.0)

    # Location-specific metrics
    distance_miles: float | None = Field(
        None, description="Distance from business location"
    )
    store_visits: float | None = Field(None, description="Estimated store visits")


class PerformanceMaxAsset(BaseModel):
    """Performance Max campaign asset."""

    asset_id: str = Field(..., description="Asset ID")
    asset_type: str = Field(..., description="Asset type (TEXT, IMAGE, VIDEO, etc.)")
    content: str = Field(..., description="Asset content or URL")
    performance_label: str | None = Field(
        None, description="Performance label from Google"
    )

    # Performance metrics
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    conversions: float = Field(default=0.0)


class SharedNegativeKeywordSet(BaseModel):
    """Shared negative keyword list."""

    shared_set_id: str = Field(..., description="Shared set ID")
    name: str = Field(..., description="Shared set name")
    member_count: int = Field(..., description="Number of negative keywords in the set")

    # Applied campaigns
    applied_campaign_ids: list[str] = Field(
        default_factory=list, description="Campaign IDs using this set"
    )
    applied_campaign_names: list[str] = Field(
        default_factory=list, description="Campaign names using this set"
    )

    # The actual negative keywords
    negative_keywords: list[NegativeKeyword] = Field(
        default_factory=list, description="Negative keywords in this set"
    )


class AccountStructure(BaseModel):
    """Google Ads account structure information."""

    customer_id: str = Field(..., description="Google Ads customer ID")
    customer_name: str = Field(..., description="Account name")
    currency_code: str = Field(..., description="Account currency")
    time_zone: str = Field(..., description="Account time zone")

    # Account type info
    is_mcc: bool = Field(False, description="Whether this is an MCC account")
    is_test_account: bool = Field(False, description="Whether this is a test account")

    # Structure counts
    campaign_count: int = Field(0, description="Total number of campaigns")
    active_campaign_count: int = Field(0, description="Number of active campaigns")
    ad_group_count: int = Field(0, description="Total number of ad groups")
    keyword_count: int = Field(0, description="Total number of keywords")

    # Budget info
    total_budget: float = Field(0.0, description="Sum of all campaign budgets")

    # Performance summary
    total_cost_mtd: float = Field(0.0, description="Total cost month-to-date")
    total_conversions_mtd: float = Field(
        0.0, description="Total conversions month-to-date"
    )
