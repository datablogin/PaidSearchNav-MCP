"""Store performance data models for local metrics optimization."""

from __future__ import annotations

from enum import Enum
from typing import List, Optional

from pydantic import BaseModel, ConfigDict, computed_field, field_validator

from paidsearchnav.core.models.analysis import AnalysisResult


class StoreIssueType(Enum):
    """Types of issues that can be detected in store performance."""

    MISSING_CALL_TRACKING = "missing_call_tracking"
    LOW_ENGAGEMENT = "low_engagement"
    NO_DRIVING_DIRECTIONS = "no_driving_directions"
    POOR_LOCAL_REACH = "poor_local_reach"
    GEOGRAPHIC_GAP = "geographic_gap"


class StorePerformanceLevel(Enum):
    """Performance levels for store categorization."""

    HIGH_PERFORMER = "high_performer"
    MODERATE_PERFORMER = "moderate_performer"
    LOW_PERFORMER = "low_performer"
    UNDERPERFORMER = "underperformer"


class StoreLocationData(BaseModel):
    """Store location and contact information."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str
    address_line_1: str
    address_line_2: Optional[str] = None
    city: str
    state: str
    postal_code: str
    country_code: str
    phone_number: Optional[str] = None


class StoreMetrics(BaseModel):
    """Store performance metrics."""

    model_config = ConfigDict(str_strip_whitespace=True)

    local_impressions: int = 0
    store_visits: int = 0
    call_clicks: int = 0
    driving_directions: int = 0
    website_visits: int = 0

    @field_validator(
        "local_impressions",
        "store_visits",
        "call_clicks",
        "driving_directions",
        "website_visits",
        mode="before",
    )
    @classmethod
    def clean_and_validate_metrics(cls, v) -> int:
        """Clean numeric values and validate that metrics are non-negative."""
        from paidsearchnav.utils.csv_parsing import clean_numeric_value

        cleaned = clean_numeric_value(v)
        value = int(cleaned) if cleaned is not None else 0

        if value < 0:
            raise ValueError("Metrics must be non-negative")
        return value

    @computed_field
    def total_engagements(self) -> int:
        """Calculate total engagement actions.

        Sums all local action metrics including:
        - Store visits: Physical visits to the location
        - Call clicks: Phone calls initiated through ads
        - Driving directions: Direction requests to the location
        - Website visits: Clicks to the business website

        Returns:
            Total number of engagement actions across all local metrics.
        """
        return (
            self.store_visits
            + self.call_clicks
            + self.driving_directions
            + self.website_visits
        )

    @computed_field
    def engagement_rate(self) -> float:
        """Calculate engagement rate as percentage of local impressions.

        The engagement rate measures how effectively local impressions convert to
        actionable customer interactions. It's calculated as:

        Engagement Rate = (Total Engagements / Local Impressions) × 100

        Where Total Engagements includes:
        - Store visits (physical location visits)
        - Call clicks (phone call initiations)
        - Driving directions (navigation requests)
        - Website visits (business website clicks)

        Performance thresholds typically used:
        - High performers: ≥3.0% engagement rate
        - Moderate performers: 1.5% - 2.9% engagement rate
        - Low performers: 0.5% - 1.4% engagement rate
        - Underperformers: <0.5% engagement rate

        Returns:
            Engagement rate as a percentage (0.0-100.0+).
            Returns 0.0 if no local impressions to avoid division by zero.
        """
        if self.local_impressions == 0:
            return 0.0
        return (self.total_engagements / self.local_impressions) * 100


class StorePerformanceData(BaseModel):
    """Complete store performance data including location and metrics."""

    model_config = ConfigDict(str_strip_whitespace=True)

    location: StoreLocationData
    metrics: StoreMetrics
    performance_level: StorePerformanceLevel

    @computed_field
    def has_call_tracking_issue(self) -> bool:
        """Check if store has call tracking issues."""
        return (
            self.metrics.local_impressions > 0
            and self.metrics.call_clicks == 0
            and self.location.phone_number is not None
        )

    @computed_field
    def has_low_engagement(self) -> bool:
        """Check if store has low engagement issues."""
        return (
            self.metrics.local_impressions > 0
            and self.metrics.engagement_rate < 1.0  # Less than 1% engagement
        )


class StoreInsight(BaseModel):
    """Insight about store performance issues or opportunities."""

    model_config = ConfigDict(str_strip_whitespace=True)

    store_name: str
    issue_type: StoreIssueType
    description: str
    impact: str
    recommendation: str
    priority: str  # "high", "medium", "low"


class StorePerformanceSummary(BaseModel):
    """Summary of overall store performance analysis."""

    model_config = ConfigDict(str_strip_whitespace=True)

    total_stores: int = 0
    total_local_impressions: int = 0
    total_engagements: int = 0
    avg_engagement_rate: float = 0.0
    stores_with_issues: int = 0
    high_performers: int = 0
    low_performers: int = 0

    @computed_field
    def overall_engagement_rate(self) -> float:
        """Calculate overall engagement rate across all stores."""
        if self.total_local_impressions == 0:
            return 0.0
        return (self.total_engagements / self.total_local_impressions) * 100


class StorePerformanceAnalysisResult(AnalysisResult):
    """Results from store performance analysis."""

    summary: StorePerformanceSummary
    store_data: List[StorePerformanceData] = []
    insights: List[StoreInsight] = []
    top_performers: List[StorePerformanceData] = []
    underperformers: List[StorePerformanceData] = []
