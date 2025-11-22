"""Keyword data models."""

from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from paidsearchnav.core.models.base import BasePSNModel


class KeywordMatchType(str, Enum):
    """Keyword match type values."""

    EXACT = "EXACT"
    PHRASE = "PHRASE"
    BROAD = "BROAD"


# Alias for backward compatibility
MatchType = KeywordMatchType


class KeywordStatus(str, Enum):
    """Keyword status values."""

    ENABLED = "ENABLED"
    PAUSED = "PAUSED"
    REMOVED = "REMOVED"


class QualityScoreLevel(str, Enum):
    """Quality score performance levels."""

    BELOW_AVERAGE = "BELOW_AVERAGE"
    AVERAGE = "AVERAGE"
    ABOVE_AVERAGE = "ABOVE_AVERAGE"
    UNKNOWN = "UNKNOWN"


class Keyword(BasePSNModel):
    """Keyword representation."""

    keyword_id: str | None = Field(
        None, description="Google Ads keyword ID (may not be available in UI exports)"
    )
    campaign_id: str | None = Field(
        None, description="Parent campaign ID (may not be available in UI exports)"
    )
    campaign_name: str = Field(..., description="Parent campaign name")
    ad_group_id: str | None = Field(
        None, description="Parent ad group ID (may not be available in UI exports)"
    )
    ad_group_name: str = Field(..., description="Parent ad group name")

    # Keyword details
    text: str = Field(..., description="Keyword text")
    match_type: KeywordMatchType = Field(..., description="Match type")
    status: KeywordStatus = Field(..., description="Keyword status")

    # Bidding
    cpc_bid: float | None = Field(None, description="Max CPC bid")
    final_url: str | None = Field(None, description="Final URL")

    # Quality metrics
    quality_score: int | None = Field(None, description="Quality score (1-10)")
    landing_page_experience: QualityScoreLevel | None = Field(None)
    expected_ctr: QualityScoreLevel | None = Field(None)
    ad_relevance: QualityScoreLevel | None = Field(None)

    # Performance metrics
    impressions: int = Field(default=0)
    clicks: int = Field(default=0)
    cost: float = Field(default=0.0)
    conversions: float = Field(default=0.0)
    conversion_value: float = Field(default=0.0)

    # Position metrics
    avg_position: float | None = Field(None, description="Average position")
    top_impression_percentage: float | None = Field(None)
    absolute_top_impression_percentage: float | None = Field(None)

    @field_validator("impressions", "clicks", mode="before")
    @classmethod
    def clean_integer_fields(cls, v: Any) -> int:
        """Clean and validate integer metric fields."""
        from paidsearchnav.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return int(cleaned) if cleaned is not None else 0

    @field_validator("cost", "conversions", "conversion_value", mode="before")
    @classmethod
    def clean_required_float_fields(cls, v: Any) -> float:
        """Clean and validate required float metric fields."""
        from paidsearchnav.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return float(cleaned) if cleaned is not None else 0.0

    @field_validator(
        "cpc_bid",
        "avg_position",
        "top_impression_percentage",
        "absolute_top_impression_percentage",
        mode="before",
    )
    @classmethod
    def clean_optional_float_fields(cls, v: Any) -> float | None:
        """Clean and validate optional float metric fields."""
        from paidsearchnav.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        return float(cleaned) if cleaned is not None else None

    @field_validator("quality_score", mode="before")
    @classmethod
    def clean_quality_score(cls, v: Any) -> int | None:
        """Clean and validate quality score field."""
        from paidsearchnav.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        if cleaned is not None:
            # Quality score should be between 1 and 10
            score = int(cleaned)
            return score if 1 <= score <= 10 else None
        return None

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
    def is_low_quality(self) -> bool:
        """Check if keyword has low quality score."""
        return self.quality_score is not None and self.quality_score < 7

    @property
    def is_duplicate_candidate(self) -> bool:
        """Check if keyword might be a duplicate (same text, different match types)."""
        # This is a simple check - actual duplicate detection would compare across keywords
        return self.match_type == KeywordMatchType.BROAD

    def matches_negative(self, negative_keyword: "Keyword") -> bool:
        """Check if this keyword would be blocked by a negative keyword."""
        negative_text = negative_keyword.text.lower()
        keyword_text = self.text.lower()

        if negative_keyword.match_type == KeywordMatchType.EXACT:
            return keyword_text == negative_text
        elif negative_keyword.match_type == KeywordMatchType.PHRASE:
            return negative_text in keyword_text
        else:  # BROAD
            # Simple word-based matching for broad negatives
            negative_words = set(negative_text.split())
            keyword_words = set(keyword_text.split())
            return negative_words.issubset(keyword_words)
