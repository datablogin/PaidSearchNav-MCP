"""Audit-related GraphQL types."""

from dataclasses import dataclass
from datetime import datetime
from enum import Enum
from typing import TYPE_CHECKING, List, Optional

import strawberry

if TYPE_CHECKING:
    pass


@strawberry.enum
class AuditStatus(Enum):
    """Audit status enumeration."""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"


@strawberry.type
@dataclass
class Audit:
    """Audit GraphQL type."""

    id: strawberry.ID
    customer_id: strawberry.ID
    status: AuditStatus
    created_at: datetime
    started_at: Optional[datetime] = None
    completed_at: Optional[datetime] = None
    error_message: Optional[str] = None

    # Progress tracking
    total_analyzers: int = 0
    completed_analyzers: int = 0


@strawberry.type
@dataclass
class AuditProgress:
    """Real-time audit progress type for subscriptions."""

    audit_id: strawberry.ID
    status: AuditStatus
    progress_percentage: float
    completed_analyzers: int
    total_analyzers: int
    current_analyzer: Optional[str] = None
    message: Optional[str] = None


@strawberry.input
@dataclass
class TriggerAuditInput:
    """Input type for triggering a new audit."""

    customer_id: strawberry.ID
    analyzers: Optional[List[str]] = None
    force_refresh: bool = False


@strawberry.input
@dataclass
class ScheduleAuditInput:
    """Input type for scheduling an audit."""

    customer_id: strawberry.ID
    schedule_at: datetime
    recurrence: Optional[str] = None  # cron expression
    analyzers: Optional[List[str]] = None
