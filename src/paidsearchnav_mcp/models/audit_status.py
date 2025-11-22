"""Audit status model for tracking audit execution state."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field, field_validator

from paidsearchnav_mcp.core.models.base import BasePSNModel, utc_now


class AuditState(str, Enum):
    """States for audit execution."""

    PENDING = "pending"
    RUNNING = "running"
    COMPLETED = "completed"
    FAILED = "failed"
    CANCELLED = "cancelled"
    RETRYING = "retrying"


class AuditStatus(BasePSNModel):
    """Represents the current status of an audit.

    This model tracks the execution state of an audit, including progress,
    results, and error information. It can be associated with a ScheduledAudit
    via the schedule_id field.
    """

    # Class constants
    MAX_RETRY_COUNT: int = 3

    audit_id: str = Field(..., description="Unique audit execution ID")
    schedule_id: str | None = Field(None, description="Associated schedule ID")
    customer_id: str = Field(..., description="Customer being audited")
    audit_type: str = Field(..., description="Type of audit")

    state: AuditState = Field(..., description="Current audit state")
    progress: float = Field(0.0, description="Progress percentage (0-100)")

    started_at: datetime = Field(default_factory=utc_now, description="Start time")
    completed_at: datetime | None = Field(None, description="Completion time")

    result_id: str | None = Field(None, description="ID of stored results")
    error_message: str | None = Field(None, description="Error details if failed")
    retry_count: int = Field(0, description="Number of retry attempts")

    metrics: dict[str, Any] = Field(
        default_factory=dict, description="Execution metrics"
    )

    @field_validator("progress")
    @classmethod
    def validate_progress(cls, v: float) -> float:
        """Validate progress is between 0 and 100."""
        if not 0.0 <= v <= 100.0:
            raise ValueError("Progress must be between 0 and 100")
        return v

    @property
    def is_terminal(self) -> bool:
        """Check if audit is in a terminal state."""
        return self.state in [
            AuditState.COMPLETED,
            AuditState.FAILED,
            AuditState.CANCELLED,
        ]

    @property
    def is_running(self) -> bool:
        """Check if audit is currently running."""
        return self.state == AuditState.RUNNING

    @property
    def is_successful(self) -> bool:
        """Check if audit completed successfully."""
        return self.state == AuditState.COMPLETED

    @property
    def duration_seconds(self) -> float | None:
        """Calculate audit duration in seconds."""
        if not self.completed_at:
            return None
        return (self.completed_at - self.started_at).total_seconds()

    @property
    def can_retry(self) -> bool:
        """Check if audit can be retried."""
        return (
            self.state == AuditState.FAILED and self.retry_count < self.MAX_RETRY_COUNT
        )

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for reporting."""
        return {
            "audit_id": self.audit_id,
            "schedule_id": self.schedule_id,
            "customer_id": self.customer_id,
            "audit_type": self.audit_type,
            "state": self.state,
            "progress": self.progress,
            "started_at": self.started_at.isoformat(),
            "completed_at": self.completed_at.isoformat()
            if self.completed_at
            else None,
            "duration_seconds": self.duration_seconds,
            "retry_count": self.retry_count,
            "error_message": self.error_message,
        }
