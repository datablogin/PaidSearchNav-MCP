"""GA4 API data models for PaidSearchNav.

This module defines data models for GA4 API responses and real-time analytics data.
"""

from datetime import datetime
from typing import Any, Dict, List, Optional, Union

from pydantic import BaseModel, Field, validator


class GA4Dimension(BaseModel):
    """GA4 dimension metadata."""

    api_name: str = Field(..., description="API name of the dimension")
    ui_name: str = Field(..., description="UI display name")
    description: Optional[str] = Field(None, description="Dimension description")
    type: str = Field(..., description="Dimension data type")


class GA4Metric(BaseModel):
    """GA4 metric metadata."""

    api_name: str = Field(..., description="API name of the metric")
    ui_name: str = Field(..., description="UI display name")
    description: Optional[str] = Field(None, description="Metric description")
    type: str = Field(..., description="Metric data type")


class GA4PropertyMetadata(BaseModel):
    """GA4 property metadata response."""

    property_id: str = Field(..., description="GA4 property ID")
    dimensions: List[GA4Dimension] = Field(default_factory=list)
    metrics: List[GA4Metric] = Field(default_factory=list)
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class GA4ReportRow(BaseModel):
    """Single row of GA4 report data."""

    dimensions: Dict[str, str] = Field(default_factory=dict)
    metrics: Dict[str, Union[str, int, float]] = Field(default_factory=dict)

    @validator("metrics", pre=True)
    def convert_metric_values(cls, v):
        """Convert metric values to appropriate types."""
        if isinstance(v, dict):
            converted = {}
            for key, value in v.items():
                # Try to convert to numeric types
                if isinstance(value, str):
                    try:
                        # Try int first, then float
                        if "." not in value:
                            converted[key] = int(value)
                        else:
                            converted[key] = float(value)
                    except ValueError:
                        converted[key] = value
                else:
                    converted[key] = value
            return converted
        return v


class GA4ReportResponse(BaseModel):
    """GA4 API report response."""

    property_id: str = Field(..., description="GA4 property ID")
    rows: List[GA4ReportRow] = Field(default_factory=list)
    row_count: int = Field(default=0, description="Total number of rows")
    dimensions: List[str] = Field(default_factory=list, description="Dimension names")
    metrics: List[str] = Field(default_factory=list, description="Metric names")
    currency_code: str = Field(
        default="USD", description="Currency code for revenue metrics"
    )
    time_zone: str = Field(default="UTC", description="Property time zone")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    start_date: Optional[str] = Field(None, description="Report start date")
    end_date: Optional[str] = Field(None, description="Report end date")


class GA4RealtimeResponse(BaseModel):
    """GA4 real-time API response."""

    property_id: str = Field(..., description="GA4 property ID")
    rows: List[GA4ReportRow] = Field(default_factory=list)
    row_count: int = Field(default=0, description="Total number of rows")
    dimensions: List[str] = Field(default_factory=list, description="Dimension names")
    metrics: List[str] = Field(default_factory=list, description="Metric names")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)
    data_freshness: str = Field(
        default="real-time", description="Data freshness indicator"
    )


class GA4SessionMetrics(BaseModel):
    """GA4 session metrics for campaign analysis."""

    property_id: str = Field(..., description="GA4 property ID")
    source: str = Field(..., description="Traffic source")
    medium: str = Field(..., description="Traffic medium")
    country: str = Field(..., description="User country")
    device_category: str = Field(..., description="Device category")
    sessions: int = Field(default=0, description="Number of sessions")
    bounce_rate: float = Field(default=0.0, description="Bounce rate (0.0-1.0)")
    avg_session_duration: float = Field(
        default=0.0, description="Average session duration in seconds"
    )
    conversions: float = Field(default=0.0, description="Number of conversions")
    revenue: float = Field(default=0.0, description="Total revenue")
    conversion_rate: float = Field(
        default=0.0, description="Session conversion rate (0.0-1.0)"
    )
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("bounce_rate", "conversion_rate")
    def validate_rate_range(cls, v):
        """Validate that rates are between 0 and 1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Rate must be between 0.0 and 1.0")
        return v


class GA4ConversionMetrics(BaseModel):
    """GA4 conversion metrics for attribution analysis."""

    property_id: str = Field(..., description="GA4 property ID")
    source: str = Field(..., description="Traffic source")
    medium: str = Field(..., description="Traffic medium")
    campaign_name: str = Field(..., description="Campaign name")
    country: str = Field(..., description="User country")
    conversions: float = Field(default=0.0, description="Number of conversions")
    revenue: float = Field(default=0.0, description="Total revenue")
    conversion_rate: float = Field(default=0.0, description="Conversion rate")
    event_conversions: Dict[str, float] = Field(
        default_factory=dict, description="Event-specific conversion counts"
    )
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)


class GA4LandingPageMetrics(BaseModel):
    """GA4 landing page performance metrics."""

    property_id: str = Field(..., description="GA4 property ID")
    landing_page: str = Field(..., description="Landing page path")
    source: str = Field(..., description="Traffic source")
    medium: str = Field(..., description="Traffic medium")
    country: str = Field(..., description="User country")
    sessions: int = Field(default=0, description="Number of sessions")
    bounce_rate: float = Field(default=0.0, description="Bounce rate (0.0-1.0)")
    avg_session_duration: float = Field(
        default=0.0, description="Average session duration in seconds"
    )
    exit_rate: float = Field(default=0.0, description="Exit rate (0.0-1.0)")
    conversions: float = Field(default=0.0, description="Number of conversions")
    revenue: float = Field(default=0.0, description="Total revenue")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("bounce_rate", "exit_rate")
    def validate_rate_range(cls, v):
        """Validate that rates are between 0 and 1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Rate must be between 0.0 and 1.0")
        return v


class GA4GeoPerformanceMetrics(BaseModel):
    """GA4 geographic performance metrics."""

    property_id: str = Field(..., description="GA4 property ID")
    country: str = Field(..., description="User country")
    region: str = Field(..., description="User region/state")
    city: str = Field(..., description="User city")
    source: str = Field(..., description="Traffic source")
    medium: str = Field(..., description="Traffic medium")
    sessions: int = Field(default=0, description="Number of sessions")
    bounce_rate: float = Field(default=0.0, description="Bounce rate (0.0-1.0)")
    avg_session_duration: float = Field(
        default=0.0, description="Average session duration in seconds"
    )
    conversions: float = Field(default=0.0, description="Number of conversions")
    revenue: float = Field(default=0.0, description="Total revenue")
    new_users: int = Field(default=0, description="Number of new users")
    returning_users: int = Field(default=0, description="Number of returning users")
    retrieved_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("bounce_rate")
    def validate_bounce_rate(cls, v):
        """Validate that bounce rate is between 0 and 1."""
        if not (0.0 <= v <= 1.0):
            raise ValueError("Bounce rate must be between 0.0 and 1.0")
        return v


class GA4QuotaUsage(BaseModel):
    """GA4 API quota usage tracking."""

    property_id: str = Field(..., description="GA4 property ID")
    requests_today: int = Field(default=0, description="Requests made today")
    requests_this_hour: int = Field(default=0, description="Requests made this hour")
    requests_this_minute: int = Field(
        default=0, description="Requests made this minute"
    )
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
    last_reset_time: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_approaching_daily_limit(self) -> bool:
        """Check if approaching daily quota limit."""
        # Default quota is 100k requests per day
        return self.requests_today > 80000

    @property
    def is_approaching_hourly_limit(self) -> bool:
        """Check if approaching hourly quota limit."""
        # Conservative hourly limit
        return self.requests_this_hour > 2000


class GA4DataFreshness(BaseModel):
    """GA4 data freshness tracking."""

    property_id: str = Field(..., description="GA4 property ID")
    last_data_timestamp: datetime = Field(
        ..., description="Timestamp of most recent data"
    )
    data_lag_hours: float = Field(..., description="Data lag in hours")
    is_realtime: bool = Field(..., description="Whether data is from real-time API")
    checked_at: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_fresh(self) -> bool:
        """Check if data is fresh enough for real-time analysis."""
        return self.data_lag_hours <= 2.0

    @property
    def freshness_status(self) -> str:
        """Get human-readable freshness status."""
        if self.is_realtime:
            return "real-time"
        elif self.data_lag_hours <= 1.0:
            return "very fresh"
        elif self.data_lag_hours <= 2.0:
            return "fresh"
        elif self.data_lag_hours <= 4.0:
            return "acceptable"
        else:
            return "stale"


class GA4APIRequest(BaseModel):
    """GA4 API request configuration."""

    property_id: str = Field(..., description="GA4 property ID")
    start_date: str = Field(..., description="Start date for request")
    end_date: str = Field(..., description="End date for request")
    dimensions: List[str] = Field(
        default_factory=list, description="Requested dimensions"
    )
    metrics: List[str] = Field(default_factory=list, description="Requested metrics")
    filters: Optional[Dict[str, Any]] = Field(None, description="Applied filters")
    limit: int = Field(default=1000, ge=1, le=100000, description="Row limit")
    is_realtime: bool = Field(
        default=False, description="Whether this is a real-time request"
    )
    created_at: datetime = Field(default_factory=datetime.utcnow)

    @validator("start_date", "end_date")
    def validate_date_format(cls, v):
        """Validate date format (allows GA4 date constants)."""
        # GA4 supports special date constants
        ga4_date_constants = [
            "today",
            "yesterday",
            "7daysAgo",
            "14daysAgo",
            "30daysAgo",
            "90daysAgo",
            "180daysAgo",
            "365daysAgo",
        ]

        if v in ga4_date_constants:
            return v

        # Validate YYYY-MM-DD format
        try:
            datetime.strptime(v, "%Y-%m-%d")
            return v
        except ValueError:
            raise ValueError(
                f"Date must be in YYYY-MM-DD format or a GA4 date constant. Got: {v}"
            )


class GA4APIResponse(BaseModel):
    """GA4 API response with metadata."""

    request: GA4APIRequest = Field(..., description="Original request")
    response_data: GA4ReportResponse = Field(..., description="Response data")
    processing_time_ms: float = Field(
        ..., description="Processing time in milliseconds"
    )
    cached: bool = Field(default=False, description="Whether response was cached")
    cache_hit_rate: Optional[float] = Field(
        None, description="Cache hit rate if applicable"
    )
    quota_used: int = Field(default=1, description="Quota units consumed")

    @property
    def is_successful(self) -> bool:
        """Check if the API response was successful."""
        return self.response_data.row_count >= 0

    @property
    def data_points(self) -> int:
        """Get number of data points returned."""
        return len(self.response_data.rows)


class GA4CacheEntry(BaseModel):
    """GA4 API response cache entry."""

    cache_key: str = Field(..., description="Cache key for the entry")
    response_data: Dict[str, Any] = Field(..., description="Cached response data")
    created_at: datetime = Field(default_factory=datetime.utcnow)
    expires_at: datetime = Field(..., description="Cache expiration time")
    access_count: int = Field(default=0, description="Number of times accessed")
    last_accessed: datetime = Field(default_factory=datetime.utcnow)

    @property
    def is_expired(self) -> bool:
        """Check if cache entry is expired."""
        return datetime.utcnow() > self.expires_at

    @property
    def ttl_seconds(self) -> float:
        """Get remaining TTL in seconds."""
        if self.is_expired:
            return 0.0
        return (self.expires_at - datetime.utcnow()).total_seconds()


class GA4ValidationResult(BaseModel):
    """GA4 data validation result comparing API vs BigQuery data."""

    property_id: str = Field(..., description="GA4 property ID")
    validation_type: str = Field(..., description="Type of validation performed")
    api_total: float = Field(..., description="Total from GA4 API")
    bigquery_total: float = Field(..., description="Total from BigQuery")
    variance_percentage: float = Field(..., description="Variance percentage")
    is_within_tolerance: bool = Field(..., description="Whether variance is acceptable")
    tolerance_percentage: float = Field(
        default=5.0, description="Acceptable variance tolerance"
    )
    checked_at: datetime = Field(default_factory=datetime.utcnow)
    notes: Optional[str] = Field(None, description="Additional validation notes")

    @validator("variance_percentage")
    def calculate_variance(cls, v, values):
        """Calculate variance percentage from API and BigQuery totals."""
        if "api_total" in values and "bigquery_total" in values:
            api_total = values["api_total"]
            bq_total = values["bigquery_total"]

            if bq_total == 0:
                return 100.0 if api_total != 0 else 0.0

            return abs((api_total - bq_total) / bq_total) * 100
        return v

    @validator("is_within_tolerance")
    def check_tolerance(cls, v, values):
        """Check if variance is within acceptable tolerance."""
        if "variance_percentage" in values and "tolerance_percentage" in values:
            return values["variance_percentage"] <= values["tolerance_percentage"]
        return v


class GA4AlertThreshold(BaseModel):
    """GA4 alert threshold configuration."""

    metric_name: str = Field(..., description="Metric to monitor")
    threshold_value: float = Field(..., description="Threshold value for alerts")
    comparison_operator: str = Field(
        default="greater_than",
        description="Comparison operator (greater_than, less_than, equals)",
    )
    alert_severity: str = Field(
        default="medium", description="Alert severity (low, medium, high, critical)"
    )
    cooldown_minutes: int = Field(
        default=30, ge=1, description="Minimum minutes between alerts"
    )
    enabled: bool = Field(default=True, description="Whether threshold is active")

    @validator("comparison_operator")
    def validate_operator(cls, v):
        """Validate comparison operator."""
        valid_operators = ["greater_than", "less_than", "equals", "not_equals"]
        if v not in valid_operators:
            raise ValueError(f"Invalid operator. Must be one of: {valid_operators}")
        return v

    @validator("alert_severity")
    def validate_severity(cls, v):
        """Validate alert severity level."""
        valid_severities = ["low", "medium", "high", "critical"]
        if v not in valid_severities:
            raise ValueError(f"Invalid severity. Must be one of: {valid_severities}")
        return v


class GA4Alert(BaseModel):
    """GA4 performance alert."""

    property_id: str = Field(..., description="GA4 property ID")
    threshold: GA4AlertThreshold = Field(
        ..., description="Threshold that triggered alert"
    )
    current_value: float = Field(..., description="Current metric value")
    triggered_at: datetime = Field(default_factory=datetime.utcnow)
    resolved_at: Optional[datetime] = Field(None, description="When alert was resolved")
    message: str = Field(..., description="Alert message")
    context: Optional[Dict[str, Any]] = Field(
        None, description="Additional alert context"
    )

    @property
    def is_resolved(self) -> bool:
        """Check if alert has been resolved."""
        return self.resolved_at is not None

    @property
    def duration_minutes(self) -> Optional[float]:
        """Get alert duration in minutes if resolved."""
        if self.resolved_at:
            return (self.resolved_at - self.triggered_at).total_seconds() / 60
        return None


class GA4CostEstimate(BaseModel):
    """GA4 API cost estimation."""

    property_id: str = Field(..., description="GA4 property ID")
    requests_count: int = Field(default=0, description="Number of API requests")
    estimated_cost_usd: float = Field(default=0.0, description="Estimated cost in USD")
    period_start: datetime = Field(default_factory=datetime.utcnow)
    period_end: datetime = Field(default_factory=datetime.utcnow)
    cost_per_request: float = Field(default=0.0001, description="Cost per API request")

    @property
    def daily_projected_cost(self) -> float:
        """Project daily cost based on current usage."""
        if self.period_start == self.period_end:
            return self.estimated_cost_usd

        period_hours = (self.period_end - self.period_start).total_seconds() / 3600
        if period_hours > 0:
            hourly_rate = self.estimated_cost_usd / period_hours
            return hourly_rate * 24
        return 0.0
