"""Attribution data models for cross-platform customer journey analysis."""

from datetime import datetime
from enum import Enum
from typing import Dict, List, Optional, Union
from uuid import uuid4

from pydantic import BaseModel, Field, validator


class TouchpointType(str, Enum):
    """Types of customer touchpoints in the attribution journey."""

    GOOGLE_ADS_IMPRESSION = "google_ads_impression"
    GOOGLE_ADS_CLICK = "google_ads_click"
    GA4_SESSION = "ga4_session"
    GA4_PAGEVIEW = "ga4_pageview"
    GA4_EVENT = "ga4_event"
    STORE_VISIT = "store_visit"
    EMAIL_OPEN = "email_open"
    EMAIL_CLICK = "email_click"
    ORGANIC_SEARCH = "organic_search"
    SOCIAL_MEDIA = "social_media"
    DIRECT_VISIT = "direct_visit"
    PHONE_CALL = "phone_call"


class AttributionModelType(str, Enum):
    """Attribution model types for customer journey analysis."""

    FIRST_TOUCH = "first_touch"
    LAST_TOUCH = "last_touch"
    LINEAR = "linear"
    TIME_DECAY = "time_decay"
    POSITION_BASED = "position_based"  # 40/20/40
    DATA_DRIVEN = "data_driven"
    CUSTOM = "custom"


class ConversionType(str, Enum):
    """Types of conversions tracked in attribution."""

    PURCHASE = "purchase"
    LEAD_FORM = "lead_form"
    PHONE_CALL = "phone_call"
    STORE_VISIT = "store_visit"
    SIGNUP = "signup"
    DOWNLOAD = "download"
    QUOTE_REQUEST = "quote_request"
    APPOINTMENT = "appointment"
    CUSTOM = "custom"


class AttributionTouch(BaseModel):
    """Individual touchpoint in a customer attribution journey."""

    touch_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_journey_id: str = Field(..., description="Journey this touch belongs to")
    customer_id: str = Field(..., description="Customer identifier")

    # Touchpoint details
    touchpoint_type: TouchpointType = Field(..., description="Type of touchpoint")
    timestamp: datetime = Field(..., description="When the touchpoint occurred")

    # Platform-specific identifiers
    gclid: Optional[str] = Field(
        None, description="Google Click ID for ads attribution"
    )
    wbraid: Optional[str] = Field(None, description="Web browser attribution ID")
    gbraid: Optional[str] = Field(None, description="Google browser attribution ID")
    ga4_session_id: Optional[str] = Field(None, description="GA4 session ID")
    ga4_user_id: Optional[str] = Field(None, description="GA4 user ID")

    # Campaign attribution data
    campaign_id: Optional[str] = Field(None, description="Google Ads campaign ID")
    campaign_name: Optional[str] = Field(None, description="Campaign name")
    ad_group_id: Optional[str] = Field(None, description="Ad group ID")
    keyword_id: Optional[str] = Field(None, description="Keyword ID")
    search_term: Optional[str] = Field(None, description="User search term")

    # GA4 attribution data
    source: Optional[str] = Field(None, description="Traffic source")
    medium: Optional[str] = Field(None, description="Traffic medium")
    landing_page: Optional[str] = Field(None, description="Landing page URL")
    event_name: Optional[str] = Field(None, description="GA4 event name")

    # Geographic data
    country: Optional[str] = Field(None, description="User country")
    region: Optional[str] = Field(None, description="User region/state")
    city: Optional[str] = Field(None, description="User city")
    store_location_id: Optional[str] = Field(None, description="Store location ID")
    distance_to_store: Optional[float] = Field(
        None, description="Distance to store in km"
    )

    # Device and context
    device_category: Optional[str] = Field(None, description="Device category")
    browser: Optional[str] = Field(None, description="Browser type")
    operating_system: Optional[str] = Field(None, description="Operating system")

    # Attribution weighting (calculated by attribution models)
    attribution_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    revenue_attributed: float = Field(default=0.0, ge=0.0)

    # Touch metadata
    is_conversion_touch: bool = Field(default=False)
    conversion_type: Optional[ConversionType] = Field(None)
    conversion_value: Optional[float] = Field(None, ge=0.0)

    # Additional touchpoint data
    engagement_time_msec: Optional[int] = Field(None, ge=0)
    page_views: Optional[int] = Field(None, ge=0)
    events_count: Optional[int] = Field(None, ge=0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CustomerJourney(BaseModel):
    """Complete customer journey with attribution analysis."""

    journey_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str = Field(..., description="Customer identifier")

    # Journey timeline
    first_touch: datetime = Field(..., description="First touchpoint timestamp")
    last_touch: datetime = Field(..., description="Last touchpoint timestamp")
    conversion_timestamp: Optional[datetime] = Field(
        None, description="Conversion timestamp"
    )

    # Journey metrics
    total_touches: int = Field(default=0, ge=0)
    total_sessions: int = Field(default=0, ge=0)
    total_pageviews: int = Field(default=0, ge=0)
    total_engagement_time_msec: int = Field(default=0, ge=0)

    # Conversion data
    converted: bool = Field(default=False)
    conversion_type: Optional[ConversionType] = Field(None)
    conversion_value: float = Field(default=0.0, ge=0.0)

    # Attribution model applied
    attribution_model: AttributionModelType = Field(
        ..., description="Attribution model used"
    )
    attribution_model_version: str = Field(default="1.0")

    # Journey classification
    journey_length_days: float = Field(default=0.0, ge=0.0)
    is_multi_session: bool = Field(default=False)
    is_multi_device: bool = Field(default=False)
    is_multi_channel: bool = Field(default=False)

    # Top-level attribution summary
    first_touch_source: str = Field(default="")
    first_touch_medium: str = Field(default="")
    first_touch_campaign: Optional[str] = Field(None)
    last_touch_source: str = Field(default="")
    last_touch_medium: str = Field(default="")
    last_touch_campaign: Optional[str] = Field(None)

    # Geographic journey data
    countries_visited: List[str] = Field(default_factory=list)
    stores_visited: List[str] = Field(default_factory=list)
    primary_location: Optional[str] = Field(None)

    # Device journey data
    devices_used: List[str] = Field(default_factory=list)
    browsers_used: List[str] = Field(default_factory=list)

    # Revenue attribution breakdown
    total_attributed_revenue: float = Field(default=0.0, ge=0.0)
    google_ads_attributed_revenue: float = Field(default=0.0, ge=0.0)
    organic_attributed_revenue: float = Field(default=0.0, ge=0.0)
    direct_attributed_revenue: float = Field(default=0.0, ge=0.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("journey_length_days", pre=True)
    def calculate_journey_length(cls, v, values):
        """Calculate journey length from first and last touch."""
        if "first_touch" in values and "last_touch" in values:
            first = values["first_touch"]
            last = values["last_touch"]
            if isinstance(first, datetime) and isinstance(last, datetime):
                return (last - first).total_seconds() / 86400  # Convert to days
        return v


class AttributionModel(BaseModel):
    """Configuration for attribution model calculations."""

    model_id: str = Field(default_factory=lambda: str(uuid4()))
    model_name: str = Field(..., description="Human-readable model name")
    model_type: AttributionModelType = Field(..., description="Attribution model type")

    # Model parameters
    time_decay_half_life_days: Optional[float] = Field(
        None, ge=1.0, description="Half-life for time decay model in days"
    )
    position_based_first_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Weight for first touch in position-based model",
    )
    position_based_last_weight: Optional[float] = Field(
        None,
        ge=0.0,
        le=1.0,
        description="Weight for last touch in position-based model",
    )
    custom_weights: Optional[Dict[str, float]] = Field(
        None, description="Custom weights by touchpoint type"
    )

    # Model constraints
    max_journey_length_days: int = Field(default=90, ge=1, le=365)
    min_touches_for_attribution: int = Field(default=1, ge=1)
    require_conversion: bool = Field(default=True)

    # Data-driven model parameters (for ML-based attribution)
    ml_model_path: Optional[str] = Field(
        None, description="Path to ML model for data-driven attribution"
    )
    feature_importance_weights: Optional[Dict[str, float]] = Field(None)
    confidence_threshold: float = Field(default=0.7, ge=0.0, le=1.0)

    # Business rules
    exclude_internal_traffic: bool = Field(default=True)
    exclude_bot_traffic: bool = Field(default=True)
    session_timeout_minutes: int = Field(default=30, ge=1, le=1440)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("position_based_first_weight", "position_based_last_weight")
    def validate_position_weights(cls, v, values):
        """Validate position-based model weights sum to 1.0."""
        if (
            values.get("model_type") == AttributionModelType.POSITION_BASED
            and v is not None
        ):
            first_weight = values.get("position_based_first_weight")
            last_weight = values.get("position_based_last_weight")

            # Only validate when both weights are provided
            if first_weight is not None and last_weight is not None:
                total_weight = first_weight + last_weight
                if (
                    abs(total_weight - 1.0) > 0.001
                ):  # Allow for small floating point differences
                    raise ValueError(
                        f"Position-based first and last weights must sum to 1.0, "
                        f"got {total_weight:.3f}"
                    )
                if first_weight <= 0 or last_weight <= 0:
                    raise ValueError("Position-based weights must be positive")

            if first_weight is not None and (first_weight <= 0 or first_weight >= 1):
                raise ValueError("Position-based first weight must be between 0 and 1")
            if last_weight is not None and (last_weight <= 0 or last_weight >= 1):
                raise ValueError("Position-based last weight must be between 0 and 1")
        return v


class AttributionResult(BaseModel):
    """Result of attribution analysis for a customer journey."""

    result_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_journey_id: str = Field(..., description="Journey this result belongs to")
    customer_id: str = Field(..., description="Customer identifier")
    attribution_model_id: str = Field(..., description="Attribution model used")

    # Attribution summary
    total_conversion_value: float = Field(default=0.0, ge=0.0)
    total_attributed_value: float = Field(default=0.0, ge=0.0)
    attribution_confidence: float = Field(default=0.0, ge=0.0, le=1.0)

    # Touch attribution breakdown
    touch_attributions: List[Dict[str, Union[str, float]]] = Field(
        default_factory=list, description="Attribution weights for each touch"
    )

    # Channel attribution summary
    channel_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by channel/source"
    )
    campaign_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by campaign"
    )
    touchpoint_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by touchpoint type"
    )

    # Time-based attribution
    attribution_by_day: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by day of journey"
    )
    attribution_by_hour: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by hour of day"
    )

    # Geographic attribution
    location_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by location"
    )
    store_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by store location"
    )

    # Device attribution
    device_attribution: Dict[str, float] = Field(
        default_factory=dict, description="Attribution by device category"
    )

    # ML insights (for data-driven models)
    predicted_ltv: Optional[float] = Field(
        None, description="Predicted customer lifetime value"
    )
    conversion_probability: Optional[float] = Field(None, ge=0.0, le=1.0)
    optimal_touchpoint_sequence: Optional[List[str]] = Field(None)

    # Model performance metrics
    model_accuracy: Optional[float] = Field(None, ge=0.0, le=1.0)
    cross_validation_score: Optional[float] = Field(None, ge=0.0, le=1.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class GCLIDMapping(BaseModel):
    """GCLID mapping between Google Ads and GA4 for attribution."""

    mapping_id: str = Field(default_factory=lambda: str(uuid4()))
    gclid: str = Field(..., description="Google Click ID")

    # Google Ads data
    google_ads_click_timestamp: datetime = Field(
        ..., description="Google Ads click time"
    )
    campaign_id: str = Field(..., description="Google Ads campaign ID")
    campaign_name: str = Field(..., description="Campaign name")
    ad_group_id: str = Field(..., description="Ad group ID")
    keyword_id: Optional[str] = Field(None, description="Keyword ID if applicable")
    search_term: Optional[str] = Field(None, description="User search term")
    click_cost: float = Field(default=0.0, ge=0.0, description="Cost of the click")

    # GA4 session data
    ga4_session_id: Optional[str] = Field(None, description="GA4 session ID")
    ga4_user_id: Optional[str] = Field(None, description="GA4 user ID")
    session_start_timestamp: Optional[datetime] = Field(
        None, description="Session start time"
    )
    landing_page: Optional[str] = Field(None, description="Landing page from GA4")

    # Match quality
    match_confidence: float = Field(default=1.0, ge=0.0, le=1.0)
    time_diff_seconds: Optional[int] = Field(
        None, description="Time difference between click and session"
    )

    # Attribution data
    session_converted: bool = Field(default=False)
    conversion_value: float = Field(default=0.0, ge=0.0)
    attribution_model_applied: Optional[str] = Field(None)
    attribution_weight: float = Field(default=0.0, ge=0.0, le=1.0)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class StoreVisitAttribution(BaseModel):
    """Store visit attribution from digital advertising."""

    visit_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_journey_id: str = Field(..., description="Journey this visit belongs to")
    customer_id: str = Field(..., description="Customer identifier")

    # Store visit data
    store_location_id: str = Field(..., description="Store location identifier")
    visit_timestamp: datetime = Field(..., description="Store visit timestamp")
    visit_duration_minutes: Optional[int] = Field(None, ge=0)

    # Attribution to digital touchpoints
    attributed_to_gclid: Optional[str] = Field(
        None, description="GCLID if attributed to Google Ads"
    )
    attributed_to_campaign_id: Optional[str] = Field(None, description="Campaign ID")
    attributed_to_ga4_session: Optional[str] = Field(None, description="GA4 session ID")

    # Attribution modeling
    attribution_confidence: float = Field(default=0.0, ge=0.0, le=1.0)
    attribution_weight: float = Field(default=0.0, ge=0.0, le=1.0)
    days_since_last_click: Optional[int] = Field(None, ge=0)

    # Visit outcome
    purchase_made: bool = Field(default=False)
    purchase_amount: Optional[float] = Field(None, ge=0.0)
    items_purchased: Optional[int] = Field(None, ge=0)

    # Enhanced conversions data
    enhanced_conversion_uploaded: bool = Field(default=False)
    conversion_adjustment_id: Optional[str] = Field(None)

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class MLAttributionModel(BaseModel):
    """ML-powered attribution model configuration and metadata."""

    model_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str = Field(..., description="Customer this model belongs to")
    model_name: str = Field(..., description="Model name")

    # Model type and configuration
    model_type: str = Field(default="xgboost", description="ML algorithm type")
    model_version: str = Field(default="1.0", description="Model version")

    # Training data configuration
    training_start_date: datetime = Field(..., description="Training data start date")
    training_end_date: datetime = Field(..., description="Training data end date")
    training_sample_size: int = Field(default=0, ge=0)
    validation_sample_size: int = Field(default=0, ge=0)

    # Feature configuration
    feature_columns: List[str] = Field(default_factory=list)
    target_column: str = Field(default="conversion_value")
    feature_importance: Dict[str, float] = Field(default_factory=dict)

    # Model performance
    accuracy_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    precision_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    recall_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    f1_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    auc_score: Optional[float] = Field(None, ge=0.0, le=1.0)
    rmse: Optional[float] = Field(None, ge=0.0)
    mae: Optional[float] = Field(None, ge=0.0)

    # Model deployment
    status: str = Field(
        default="training", description="Model status: training, active, deprecated"
    )
    deployed_at: Optional[datetime] = Field(
        None, description="Model deployment timestamp"
    )
    last_prediction_at: Optional[datetime] = Field(
        None, description="Last prediction timestamp"
    )
    prediction_count: int = Field(default=0, ge=0)

    # Retraining configuration
    retrain_frequency_days: int = Field(default=30, ge=1, le=365)
    auto_retrain_enabled: bool = Field(default=True)
    performance_threshold: float = Field(default=0.8, ge=0.0, le=1.0)

    # Model artifacts
    model_file_path: Optional[str] = Field(None, description="Path to saved model file")
    scaler_file_path: Optional[str] = Field(None, description="Path to feature scaler")
    feature_encoder_path: Optional[str] = Field(
        None, description="Path to categorical encoder"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class AttributionInsight(BaseModel):
    """Actionable insight generated from attribution analysis."""

    insight_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str = Field(..., description="Customer identifier")
    analysis_period_start: datetime = Field(..., description="Analysis period start")
    analysis_period_end: datetime = Field(..., description="Analysis period end")

    # Insight classification
    insight_type: str = Field(
        ...,
        description="Type of insight: channel_shift, underperforming_touchpoint, etc.",
    )
    priority: str = Field(
        default="medium", description="Priority: low, medium, high, critical"
    )
    confidence: float = Field(
        default=0.0, ge=0.0, le=1.0, description="Confidence in insight"
    )

    # Insight content
    title: str = Field(..., description="Insight title")
    description: str = Field(..., description="Detailed insight description")
    impact_description: str = Field(default="", description="Expected business impact")

    # Data supporting the insight
    supporting_data: Dict[str, Union[str, float, int]] = Field(
        default_factory=dict, description="Data points supporting this insight"
    )

    # Recommended actions
    recommended_actions: List[str] = Field(
        default_factory=list, description="Specific actionable recommendations"
    )

    # Business impact
    projected_revenue_impact: Optional[float] = Field(
        None, description="Projected revenue impact"
    )
    projected_cost_savings: Optional[float] = Field(
        None, description="Projected cost savings"
    )
    implementation_effort: str = Field(
        default="medium", description="Implementation effort: low, medium, high"
    )

    # Insight status
    status: str = Field(
        default="active", description="Status: active, implemented, dismissed"
    )
    implemented_at: Optional[datetime] = Field(
        None, description="Implementation timestamp"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)


class CrossPlatformMetrics(BaseModel):
    """Cross-platform performance metrics for attribution analysis."""

    metrics_id: str = Field(default_factory=lambda: str(uuid4()))
    customer_id: str = Field(..., description="Customer identifier")
    date: datetime = Field(..., description="Metrics date")

    # Google Ads metrics
    google_ads_clicks: int = Field(default=0, ge=0)
    google_ads_impressions: int = Field(default=0, ge=0)
    google_ads_cost: float = Field(default=0.0, ge=0.0)
    google_ads_conversions: float = Field(default=0.0, ge=0.0)
    google_ads_conversion_value: float = Field(default=0.0, ge=0.0)

    # GA4 metrics
    ga4_sessions: int = Field(default=0, ge=0)
    ga4_users: int = Field(default=0, ge=0)
    ga4_pageviews: int = Field(default=0, ge=0)
    ga4_bounce_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    ga4_conversion_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    ga4_revenue: float = Field(default=0.0, ge=0.0)

    # Attribution-calculated metrics
    attributed_revenue_google_ads: float = Field(default=0.0, ge=0.0)
    attributed_revenue_organic: float = Field(default=0.0, ge=0.0)
    attributed_revenue_direct: float = Field(default=0.0, ge=0.0)
    attributed_revenue_other: float = Field(default=0.0, ge=0.0)

    # Cross-platform KPIs
    gclid_match_rate: float = Field(default=0.0, ge=0.0, le=1.0)
    cross_platform_roas: float = Field(default=0.0, ge=0.0)
    multi_touch_journeys_count: int = Field(default=0, ge=0)
    single_touch_journeys_count: int = Field(default=0, ge=0)

    # Customer journey insights
    avg_journey_length_days: float = Field(default=0.0, ge=0.0)
    avg_touches_per_journey: float = Field(default=0.0, ge=0.0)
    top_converting_sequence: Optional[str] = Field(
        None, description="Most effective touchpoint sequence"
    )

    created_at: datetime = Field(default_factory=datetime.utcnow)
    updated_at: datetime = Field(default_factory=datetime.utcnow)
