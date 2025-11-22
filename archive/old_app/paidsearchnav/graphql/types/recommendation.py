"""Recommendation-related GraphQL types."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, Optional

import strawberry
from strawberry.scalars import JSON

if TYPE_CHECKING:
    pass


@strawberry.enum
class Priority(Enum):
    """Recommendation priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


@strawberry.enum
class RecommendationStatus(Enum):
    """Recommendation status."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    IMPLEMENTED = "implemented"
    REJECTED = "rejected"
    DEFERRED = "deferred"


@strawberry.type
@dataclass
class Recommendation:
    """Recommendation GraphQL type."""

    # Required fields
    id: strawberry.ID
    audit_id: strawberry.ID
    analysis_result_id: strawberry.ID
    title: str
    description: str
    priority: Priority
    action_items: JSON  # List of specific actions
    created_at: datetime
    updated_at: datetime

    # Optional fields with defaults
    status: RecommendationStatus = RecommendationStatus.PENDING
    estimated_impact: Optional[float] = None
    estimated_cost_savings: Optional[float] = None
    implementation_effort: Optional[str] = None  # low, medium, high
    implementation_notes: Optional[str] = None
    implemented_at: Optional[datetime] = None
