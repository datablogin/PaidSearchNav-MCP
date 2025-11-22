"""Analysis-related GraphQL types."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

import strawberry
from strawberry.scalars import JSON

if TYPE_CHECKING:
    pass


@strawberry.enum
class AnalyzerType(Enum):
    """Available analyzer types."""

    KEYWORD_PERFORMANCE = "keyword_performance"
    AD_COPY_EFFECTIVENESS = "ad_copy_effectiveness"
    BID_STRATEGY = "bid_strategy"
    BUDGET_UTILIZATION = "budget_utilization"
    LOCATION_TARGETING = "location_targeting"
    DEVICE_PERFORMANCE = "device_performance"
    SCHEDULE_OPTIMIZATION = "schedule_optimization"
    NEGATIVE_KEYWORDS = "negative_keywords"
    SEARCH_TERMS = "search_terms"
    AUDIENCE_INSIGHTS = "audience_insights"


@strawberry.type
@dataclass
class AnalysisResult:
    """Analysis result GraphQL type."""

    id: strawberry.ID
    audit_id: strawberry.ID
    analyzer_type: AnalyzerType
    status: str
    created_at: datetime
    findings: JSON  # Flexible JSON field for analyzer-specific data

    # Optional fields
    completed_at: Optional[datetime] = None
    score: Optional[float] = None
    impact_level: Optional[str] = None  # high, medium, low

    # Metrics with defaults
    issues_found: int = 0
    opportunities_identified: int = 0
    potential_savings: Optional[float] = None
