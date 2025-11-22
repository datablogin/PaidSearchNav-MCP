"""Alert system data models."""

from datetime import datetime
from enum import Enum
from typing import Any, Dict, List, Optional
from uuid import UUID, uuid4

from pydantic import BaseModel, Field


class AlertType(str, Enum):
    """Types of alerts that can be generated."""

    ERROR = "error"
    WARNING = "warning"
    INFO = "info"
    PERFORMANCE = "performance"
    SECURITY = "security"
    SYSTEM = "system"
    AUDIT = "audit"


class AlertPriority(str, Enum):
    """Alert priority levels."""

    CRITICAL = "critical"
    HIGH = "high"
    MEDIUM = "medium"
    LOW = "low"


class AlertStatus(str, Enum):
    """Alert processing status."""

    PENDING = "pending"
    PROCESSING = "processing"
    SENT = "sent"
    FAILED = "failed"
    RATE_LIMITED = "rate_limited"
    BATCHED = "batched"


class Alert(BaseModel):
    """Alert model with comprehensive metadata."""

    id: UUID = Field(default_factory=uuid4, description="Unique alert identifier")
    type: AlertType = Field(..., description="Alert type")
    priority: AlertPriority = Field(..., description="Alert priority level")
    status: AlertStatus = Field(
        default=AlertStatus.PENDING, description="Processing status"
    )
    title: str = Field(..., description="Alert title", min_length=1, max_length=200)
    message: str = Field(..., description="Alert message content")
    source: str = Field(..., description="Source component that generated the alert")

    # Timestamps
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Creation timestamp"
    )
    updated_at: datetime = Field(
        default_factory=datetime.utcnow, description="Last update timestamp"
    )
    sent_at: Optional[datetime] = Field(
        default=None, description="Time when alert was sent"
    )

    # Context and metadata
    context: Dict[str, Any] = Field(
        default_factory=dict, description="Alert context data"
    )
    tags: List[str] = Field(
        default_factory=list, description="Alert tags for categorization"
    )
    customer_id: Optional[str] = Field(
        default=None, description="Associated customer ID"
    )
    job_id: Optional[str] = Field(default=None, description="Associated job ID")

    # Processing metadata
    retry_count: int = Field(default=0, description="Number of send attempts")
    error_message: Optional[str] = Field(
        default=None, description="Error message if failed"
    )
    channels_sent: List[str] = Field(
        default_factory=list, description="Channels where alert was sent"
    )

    # Batching information
    batch_id: Optional[UUID] = Field(
        default=None, description="Batch ID if batched with other alerts"
    )

    def update_status(
        self, new_status: AlertStatus, error_message: Optional[str] = None
    ) -> None:
        """Update alert status and timestamp.

        Args:
            new_status: New status to set
            error_message: Optional error message
        """
        self.status = new_status
        self.updated_at = datetime.utcnow()

        if error_message:
            self.error_message = error_message

        if new_status == AlertStatus.SENT:
            self.sent_at = datetime.utcnow()

    def increment_retry(self) -> None:
        """Increment retry count."""
        self.retry_count += 1
        self.updated_at = datetime.utcnow()

    def add_tag(self, tag: str) -> None:
        """Add a tag to the alert.

        Args:
            tag: Tag to add
        """
        if tag not in self.tags:
            self.tags.append(tag)

    def is_duplicate_of(
        self, other: "Alert", similarity_threshold: float = 0.8
    ) -> bool:
        """Check if this alert is a duplicate of another alert.

        Args:
            other: Another alert to compare against
            similarity_threshold: Similarity threshold for considering duplicates

        Returns:
            True if alerts are considered duplicates
        """
        # Simple duplicate detection based on key fields
        if (
            self.type == other.type
            and self.source == other.source
            and self.title == other.title
            and self.customer_id == other.customer_id
        ):
            # Check if messages are similar (simple approach)
            if self.message == other.message:
                return True

            # Could add more sophisticated similarity detection here

        return False


class AlertBatch(BaseModel):
    """Model for batched alerts."""

    id: UUID = Field(default_factory=uuid4, description="Batch identifier")
    alerts: List[Alert] = Field(..., description="Alerts in this batch")
    created_at: datetime = Field(
        default_factory=datetime.utcnow, description="Batch creation time"
    )
    processed_at: Optional[datetime] = Field(
        default=None, description="Batch processing time"
    )

    @property
    def alert_count(self) -> int:
        """Number of alerts in batch."""
        return len(self.alerts)

    @property
    def highest_priority(self) -> AlertPriority:
        """Highest priority alert in batch."""
        if not self.alerts:
            return AlertPriority.LOW

        priority_order = {
            AlertPriority.CRITICAL: 0,
            AlertPriority.HIGH: 1,
            AlertPriority.MEDIUM: 2,
            AlertPriority.LOW: 3,
        }

        return min(self.alerts, key=lambda a: priority_order[a.priority]).priority

    def mark_processed(self) -> None:
        """Mark batch as processed."""
        self.processed_at = datetime.utcnow()
        for alert in self.alerts:
            alert.batch_id = self.id


class AlertConfig(BaseModel):
    """Configuration for alert system behavior."""

    # Rate limiting
    max_alerts_per_minute: int = Field(
        default=60, description="Maximum alerts per minute"
    )
    max_alerts_per_hour: int = Field(
        default=1000, description="Maximum alerts per hour"
    )
    rate_limit_window_minutes: int = Field(
        default=5, description="Rate limit window in minutes"
    )

    # Batching
    enable_batching: bool = Field(default=True, description="Enable alert batching")
    batch_size: int = Field(default=10, description="Maximum alerts per batch")
    batch_timeout_seconds: int = Field(
        default=60, description="Batch timeout in seconds"
    )

    # Queue management
    max_queue_size: int = Field(
        default=1000, description="Maximum queue size to prevent memory issues"
    )

    # Retry configuration
    max_retries: int = Field(default=3, description="Maximum retry attempts")
    retry_delay_seconds: int = Field(default=30, description="Delay between retries")
    retry_backoff_multiplier: float = Field(
        default=2.0, description="Backoff multiplier for retries"
    )

    # Duplicate detection
    enable_duplicate_detection: bool = Field(
        default=True, description="Enable duplicate detection"
    )
    duplicate_window_minutes: int = Field(
        default=10, description="Window for duplicate detection"
    )

    # Priority thresholds
    critical_alert_immediate_send: bool = Field(
        default=True, description="Send critical alerts immediately"
    )
    high_priority_batch_timeout: int = Field(
        default=30, description="Shorter timeout for high priority batches"
    )

    # Channel configuration
    default_channels: List[str] = Field(
        default_factory=lambda: ["slack"], description="Default notification channels"
    )
    channel_priorities: Dict[str, List[AlertPriority]] = Field(
        default_factory=lambda: {
            "slack": [AlertPriority.CRITICAL, AlertPriority.HIGH, AlertPriority.MEDIUM],
            "email": [AlertPriority.CRITICAL, AlertPriority.HIGH],
            "sentry": [AlertPriority.CRITICAL, AlertPriority.HIGH],
        },
        description="Channel priorities mapping",
    )


class AlertMetrics(BaseModel):
    """Metrics for alert system monitoring."""

    total_alerts_generated: int = Field(default=0, description="Total alerts generated")
    alerts_sent: int = Field(default=0, description="Successfully sent alerts")
    alerts_failed: int = Field(default=0, description="Failed alerts")
    alerts_rate_limited: int = Field(default=0, description="Rate limited alerts")
    alerts_batched: int = Field(default=0, description="Batched alerts")
    duplicates_detected: int = Field(default=0, description="Duplicate alerts detected")

    # Processing times
    average_processing_time_ms: float = Field(
        default=0.0, description="Average processing time"
    )
    max_processing_time_ms: float = Field(
        default=0.0, description="Maximum processing time"
    )

    # By priority
    critical_alerts: int = Field(default=0, description="Critical alerts")
    high_alerts: int = Field(default=0, description="High priority alerts")
    medium_alerts: int = Field(default=0, description="Medium priority alerts")
    low_alerts: int = Field(default=0, description="Low priority alerts")

    # By type
    error_alerts: int = Field(default=0, description="Error alerts")
    warning_alerts: int = Field(default=0, description="Warning alerts")
    performance_alerts: int = Field(default=0, description="Performance alerts")
    security_alerts: int = Field(default=0, description="Security alerts")

    last_updated: datetime = Field(
        default_factory=datetime.utcnow, description="Last metrics update"
    )

    def increment_alert(self, alert: Alert) -> None:
        """Increment counters for a new alert.

        Args:
            alert: Alert to count
        """
        self.total_alerts_generated += 1

        # By priority
        if alert.priority == AlertPriority.CRITICAL:
            self.critical_alerts += 1
        elif alert.priority == AlertPriority.HIGH:
            self.high_alerts += 1
        elif alert.priority == AlertPriority.MEDIUM:
            self.medium_alerts += 1
        else:
            self.low_alerts += 1

        # By type
        if alert.type == AlertType.ERROR:
            self.error_alerts += 1
        elif alert.type == AlertType.WARNING:
            self.warning_alerts += 1
        elif alert.type == AlertType.PERFORMANCE:
            self.performance_alerts += 1
        elif alert.type == AlertType.SECURITY:
            self.security_alerts += 1

        self.last_updated = datetime.utcnow()

    def increment_status(self, status: AlertStatus) -> None:
        """Increment counter for alert status.

        Args:
            status: Alert status to count
        """
        if status == AlertStatus.SENT:
            self.alerts_sent += 1
        elif status == AlertStatus.FAILED:
            self.alerts_failed += 1
        elif status == AlertStatus.RATE_LIMITED:
            self.alerts_rate_limited += 1
        elif status == AlertStatus.BATCHED:
            self.alerts_batched += 1

        self.last_updated = datetime.utcnow()

    def update_processing_time(self, processing_time_ms: float) -> None:
        """Update processing time metrics.

        Args:
            processing_time_ms: Processing time in milliseconds
        """
        if processing_time_ms > self.max_processing_time_ms:
            self.max_processing_time_ms = processing_time_ms

        # Simple moving average (could be improved with more sophisticated tracking)
        if self.average_processing_time_ms == 0:
            self.average_processing_time_ms = processing_time_ms
        else:
            self.average_processing_time_ms = (
                self.average_processing_time_ms + processing_time_ms
            ) / 2

        self.last_updated = datetime.utcnow()
