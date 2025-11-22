"""Scheduled audit model for configuring automated audits."""

from datetime import datetime
from enum import Enum
from typing import Any

from pydantic import Field

from paidsearchnav_mcp.models.base import BasePSNModel


class AuditFrequency(str, Enum):
    """Frequency options for scheduled audits."""

    DAILY = "daily"
    WEEKLY = "weekly"
    MONTHLY = "monthly"
    QUARTERLY = "quarterly"
    ON_DEMAND = "on_demand"


class ScheduledAudit(BasePSNModel):
    """Represents a scheduled audit configuration.

    This model defines when and how audits should be executed automatically.
    Each ScheduledAudit can generate multiple AuditStatus records as it runs.
    """

    id: str = Field(..., description="Unique audit schedule ID")
    customer_id: str = Field(..., description="Customer ID to audit")
    audit_type: str = Field(..., description="Type of audit to run")
    frequency: AuditFrequency = Field(..., description="Audit frequency")
    cron_expression: str | None = Field(None, description="Cron schedule")

    config: dict[str, Any] = Field(
        default_factory=dict, description="Audit configuration"
    )

    enabled: bool = Field(True, description="Whether schedule is active")
    last_run: datetime | None = Field(None, description="Last execution time")
    next_run: datetime | None = Field(None, description="Next scheduled time")

    @property
    def is_active(self) -> bool:
        """Check if the schedule is currently active."""
        return self.enabled

    @property
    def is_due(self) -> bool:
        """Check if the audit is due to run."""
        if not self.enabled or not self.next_run:
            return False

        from datetime import timezone

        now = datetime.now(timezone.utc)
        next_run = self.next_run

        # Ensure both datetimes are timezone-aware
        if next_run.tzinfo is None:
            next_run = next_run.replace(tzinfo=timezone.utc)

        return now >= next_run

    @property
    def has_run(self) -> bool:
        """Check if the audit has ever been executed."""
        return self.last_run is not None

    def to_summary_dict(self) -> dict[str, Any]:
        """Convert to summary dictionary for reporting."""
        return {
            "id": self.id,
            "customer_id": self.customer_id,
            "audit_type": self.audit_type,
            "frequency": self.frequency,
            "enabled": self.enabled,
            "last_run": self.last_run.isoformat() if self.last_run else None,
            "next_run": self.next_run.isoformat() if self.next_run else None,
            "is_due": self.is_due,
        }
