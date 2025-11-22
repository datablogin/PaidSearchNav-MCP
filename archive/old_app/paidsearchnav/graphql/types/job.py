"""Job-related GraphQL types."""

from dataclasses import dataclass
from datetime import datetime
from typing import Optional

import strawberry


@strawberry.type
@dataclass
class ScheduledJob:
    """Scheduled job GraphQL type."""

    id: strawberry.ID
    job_type: str
    status: str
    scheduled_at: datetime
    created_at: datetime
    updated_at: datetime

    # Job details
    payload: Optional[str] = None
    recurrence: Optional[str] = None  # cron expression
    next_run: Optional[datetime] = None
    last_run: Optional[datetime] = None

    # Error tracking
    error_count: int = 0
    last_error: Optional[str] = None

    # Related fields
    customer_id: Optional[strawberry.ID] = None
