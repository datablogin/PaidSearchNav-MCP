"""Search term data models."""

from datetime import date
from enum import Enum
from typing import Any

import pandas as pd
from pydantic import Field, computed_field, field_validator, model_validator

from paidsearchnav_mcp.models.base import BasePSNModel


class SearchTermStatus(str, Enum):
    """Search term classification status."""

    ADD_CANDIDATE = "ADD_CANDIDATE"  # High-performing, not in keywords
    NEGATIVE_CANDIDATE = "NEGATIVE_CANDIDATE"  # Poor performing or irrelevant
    ALREADY_COVERED = "ALREADY_COVERED"  # Already exists as keyword
    MONITOR = "MONITOR"  # Needs more data
    REVIEW_NEEDED = "REVIEW_NEEDED"  # Requires manual review
    UNKNOWN = "UNKNOWN"


# Alias for backward compatibility
SearchTermClassification = SearchTermStatus


class SearchTermMetrics(BasePSNModel):
    """Performance metrics for a search term."""

    impressions: int = Field(default=0, description="Total impressions")
    clicks: int = Field(default=0, description="Total clicks")
    cost: float = Field(default=0.0, description="Total cost in account currency")
    conversions: float = Field(default=0.0, description="Total conversions")
    conversion_value: float = Field(default=0.0, description="Total conversion value")

    @field_validator("impressions", "clicks", mode="before")
    @classmethod
    def clean_integer_fields(cls, v: Any) -> int:
        """Clean and validate integer metric fields."""
        from paidsearchnav_mcp.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return int(cleaned) if cleaned is not None else 0

    @field_validator("cost", "conversions", "conversion_value", mode="before")
    @classmethod
    def clean_float_fields(cls, v: Any) -> float:
        """Clean and validate float metric fields."""
        from paidsearchnav_mcp.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return float(cleaned) if cleaned is not None else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def ctr(self) -> float:
        """Calculate click-through rate."""
        return (self.clicks / self.impressions * 100) if self.impressions > 0 else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def cpc(self) -> float:
        """Calculate cost per click."""
        return self.cost / self.clicks if self.clicks > 0 else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def cpa(self) -> float:
        """Calculate cost per acquisition."""
        return self.cost / self.conversions if self.conversions > 0 else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def conversion_rate(self) -> float:
        """Calculate conversion rate."""
        return (self.conversions / self.clicks * 100) if self.clicks > 0 else 0.0

    @computed_field  # type: ignore[misc]
    @property
    def roas(self) -> float:
        """Calculate return on ad spend."""
        return self.conversion_value / self.cost if self.cost > 0 else 0.0


class SearchTerm(BasePSNModel):
    """Search term representation from search terms report."""

    # Identifiers
    campaign_id: str | None = Field(
        None, description="Campaign ID (may not be available in UI exports)"
    )
    campaign_name: str = Field(default="Unknown Campaign", description="Campaign name")
    ad_group_id: str | None = Field(
        None, description="Ad group ID (may not be available in UI exports)"
    )
    ad_group_name: str = Field(default="Unknown Ad Group", description="Ad group name")

    # Search term details
    search_term: str = Field(..., description="The actual search query")
    keyword_id: str | None = Field(None, description="Triggering keyword ID")
    keyword_text: str | None = Field(None, description="Triggering keyword text")
    match_type: str | None = Field(
        None, description="Match type that triggered this term"
    )

    # Date range
    date_start: date | None = Field(None, description="Start date of metrics")
    date_end: date | None = Field(None, description="End date of metrics")

    # Performance metrics
    metrics: SearchTermMetrics = Field(default_factory=SearchTermMetrics)

    # Analysis fields
    classification: SearchTermStatus | None = Field(
        None, description="Term classification"
    )
    classification_reason: str | None = Field(
        None, description="Reason for classification"
    )
    recommendation: str | None = Field(None, description="Specific recommendation")
    priority_score: float | None = Field(None, description="Priority score for action")

    # Local intent indicators
    has_near_me: bool = Field(default=False, description="Contains 'near me'")
    has_location: bool = Field(default=False, description="Contains location terms")
    detected_location: str | None = Field(None, description="Detected location if any")
    location_terms: list[str] = Field(
        default_factory=list, description="Location terms found in query"
    )

    @model_validator(mode="before")
    @classmethod
    def handle_missing_fields(cls, data: Any) -> Any:
        """Handle missing required fields with smart inference."""
        if isinstance(data, dict):
            from paidsearchnav_mcp.utils.csv_parsing import infer_missing_fields

            data = infer_missing_fields(data)

            # Handle flat metrics fields by moving them into a metrics dict
            metrics_fields = [
                "impressions",
                "clicks",
                "cost",
                "conversions",
                "conversion_value",
            ]
            metrics_data = {}

            for field in metrics_fields:
                if field in data:
                    metrics_data[field] = data.pop(field)

            # If we have metrics data but no metrics object, create one
            if metrics_data and "metrics" not in data:
                data["metrics"] = metrics_data

            return data
        return data

    @field_validator("ad_group_name", mode="before")
    @classmethod
    def ensure_ad_group_name(cls, v: Any, info) -> str:
        """Ensure ad_group_name is present with smart defaults."""
        # Use the centralized inference logic if value is missing
        if not v or (v is not None and pd.isna(v)):
            from paidsearchnav_mcp.utils.csv_parsing import infer_missing_fields

            # Create temporary data dict for inference
            temp_data = info.data.copy() if info.data else {}
            temp_data["ad_group_name"] = v  # Include current value
            inferred_data = infer_missing_fields(temp_data)
            return inferred_data.get("ad_group_name", "Unknown Ad Group")
        return str(v)

    @field_validator("campaign_name", mode="before")
    @classmethod
    def ensure_campaign_name(cls, v: Any, info) -> str:
        """Ensure campaign_name is present with smart defaults."""
        # Use the centralized inference logic if value is missing
        if not v or (v is not None and pd.isna(v)):
            from paidsearchnav_mcp.utils.csv_parsing import infer_missing_fields

            # Create temporary data dict for inference
            temp_data = info.data.copy() if info.data else {}
            temp_data["campaign_name"] = v  # Include current value
            inferred_data = infer_missing_fields(temp_data)
            return inferred_data.get("campaign_name", "Unknown Campaign")
        return str(v)

    # Backward compatibility properties
    @property
    def impressions(self) -> int:
        """Get impressions from metrics."""
        return self.metrics.impressions

    @property
    def clicks(self) -> int:
        """Get clicks from metrics."""
        return self.metrics.clicks

    @property
    def cost(self) -> float:
        """Get cost from metrics."""
        return self.metrics.cost

    @property
    def conversions(self) -> float:
        """Get conversions from metrics."""
        return self.metrics.conversions

    @property
    def conversion_value(self) -> float:
        """Get conversion value from metrics."""
        return self.metrics.conversion_value

    @property
    def ctr(self) -> float:
        """Calculate Click-Through Rate."""
        return self.metrics.ctr

    @property
    def avg_cpc(self) -> float:
        """Calculate Average Cost Per Click."""
        return self.metrics.cpc

    @property
    def conversion_rate(self) -> float:
        """Calculate Conversion Rate."""
        return self.metrics.conversion_rate

    @property
    def cpa(self) -> float:
        """Calculate Cost Per Acquisition."""
        return self.metrics.cpa

    @property
    def roas(self) -> float:
        """Calculate Return on Ad Spend."""
        return self.metrics.roas

    @property
    def is_local_intent(self) -> bool:
        """Check if search term has local intent."""
        return self.has_near_me or self.has_location or bool(self.location_terms)

    @property
    def contains_near_me(self) -> bool:
        """Alias for has_near_me."""
        return self.has_near_me

    def detect_local_intent(self) -> None:
        """Detect local intent signals in the search term."""
        query_lower = self.search_term.lower()

        # Check for "near me"
        self.has_near_me = "near me" in query_lower

        # Common local intent patterns
        local_patterns = [
            "near me",
            "nearby",
            "close to",
            "in my area",
            "local",
            "closest",
            "nearest",
        ]

        # Detect local intent
        self.has_location = any(pattern in query_lower for pattern in local_patterns)

        # Extract location terms
        self.location_terms = [term for term in local_patterns if term in query_lower]

    def calculate_priority_score(self, account_avg_cpa: float) -> float:
        """Calculate priority score for taking action on this term."""
        score = 0.0

        # High volume terms get higher priority
        if self.impressions > 100:
            score += 20
        elif self.impressions > 50:
            score += 10

        # Good performance metrics increase priority
        if self.ctr > 5:  # High CTR
            score += 15

        if self.conversions > 0:
            if self.cpa < account_avg_cpa * 0.8:  # 20% better than average
                score += 25
            elif self.cpa < account_avg_cpa:
                score += 15

        # Poor performers also get priority (for negative keywords)
        if self.clicks > 10 and self.conversions == 0:
            score += 20

        # Local intent gets bonus
        if self.is_local_intent:
            score += 10

        self.priority_score = score
        return score

    def is_high_value(
        self, min_conversions: float = 1.0, max_cpa: float | None = None
    ) -> bool:
        """Check if search term is high value based on performance."""
        if self.conversions < min_conversions:
            return False

        if max_cpa is not None and self.cpa > max_cpa:
            return False

        return True

    def is_wasteful(
        self, min_clicks: int = 10, max_conversions: float = 0.0, min_cost: float = 50.0
    ) -> bool:
        """Check if search term is wasteful (high cost, no conversions)."""
        return (
            self.clicks >= min_clicks
            and self.conversions <= max_conversions
            and self.cost >= min_cost
        )
