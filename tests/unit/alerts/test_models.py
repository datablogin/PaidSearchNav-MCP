"""Tests for alert system models."""

from datetime import datetime

from paidsearchnav.alerts.models import (
    Alert,
    AlertBatch,
    AlertConfig,
    AlertMetrics,
    AlertPriority,
    AlertStatus,
    AlertType,
)


class TestAlert:
    """Test Alert model."""

    def test_alert_creation(self):
        """Test basic alert creation."""
        alert = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Test Alert",
            message="This is a test alert",
            source="TestComponent",
        )

        assert alert.type == AlertType.ERROR
        assert alert.priority == AlertPriority.HIGH
        assert alert.status == AlertStatus.PENDING
        assert alert.title == "Test Alert"
        assert alert.message == "This is a test alert"
        assert alert.source == "TestComponent"
        assert alert.retry_count == 0
        assert alert.channels_sent == []
        assert alert.context == {}
        assert alert.tags == []
        assert isinstance(alert.created_at, datetime)
        assert isinstance(alert.updated_at, datetime)

    def test_alert_with_context(self):
        """Test alert with context data."""
        context = {"customer_id": "123", "analysis_id": "456"}
        tags = ["error", "critical"]

        alert = Alert(
            type=AlertType.SECURITY,
            priority=AlertPriority.CRITICAL,
            title="Security Alert",
            message="Security issue detected",
            source="SecurityComponent",
            context=context,
            tags=tags,
            customer_id="123",
            job_id="job_789",
        )

        assert alert.context == context
        assert alert.tags == tags
        assert alert.customer_id == "123"
        assert alert.job_id == "job_789"

    def test_update_status(self):
        """Test status update functionality."""
        alert = Alert(
            type=AlertType.WARNING,
            priority=AlertPriority.MEDIUM,
            title="Warning Alert",
            message="Warning message",
            source="WarningComponent",
        )

        original_updated_at = alert.updated_at

        # Update to running
        alert.update_status(AlertStatus.PROCESSING)
        assert alert.status == AlertStatus.PROCESSING
        assert alert.updated_at > original_updated_at
        assert alert.sent_at is None

        # Update to sent
        alert.update_status(AlertStatus.SENT)
        assert alert.status == AlertStatus.SENT
        assert alert.sent_at is not None

        # Update to failed with error
        alert.update_status(AlertStatus.FAILED, "Network error")
        assert alert.status == AlertStatus.FAILED
        assert alert.error_message == "Network error"

    def test_increment_retry(self):
        """Test retry increment functionality."""
        alert = Alert(
            type=AlertType.INFO,
            priority=AlertPriority.LOW,
            title="Info Alert",
            message="Info message",
            source="InfoComponent",
        )

        original_retry_count = alert.retry_count
        original_updated_at = alert.updated_at

        alert.increment_retry()

        assert alert.retry_count == original_retry_count + 1
        assert alert.updated_at > original_updated_at

    def test_add_tag(self):
        """Test tag addition functionality."""
        alert = Alert(
            type=AlertType.PERFORMANCE,
            priority=AlertPriority.MEDIUM,
            title="Performance Alert",
            message="Performance issue",
            source="PerformanceComponent",
        )

        # Add first tag
        alert.add_tag("slow")
        assert "slow" in alert.tags

        # Add second tag
        alert.add_tag("memory")
        assert "memory" in alert.tags
        assert len(alert.tags) == 2

        # Add duplicate tag (should not be added)
        alert.add_tag("slow")
        assert len(alert.tags) == 2

    def test_is_duplicate_of(self):
        """Test duplicate detection."""
        alert1 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Connection failed",
            source="DatabaseComponent",
            customer_id="123",
        )

        # Same alert (duplicate)
        alert2 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Connection failed",
            source="DatabaseComponent",
            customer_id="123",
        )

        # Different message (not duplicate)
        alert3 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Timeout occurred",
            source="DatabaseComponent",
            customer_id="123",
        )

        # Different source (not duplicate)
        alert4 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Connection failed",
            source="CacheComponent",
            customer_id="123",
        )

        assert alert1.is_duplicate_of(alert2)
        assert alert2.is_duplicate_of(alert1)
        assert not alert1.is_duplicate_of(alert3)
        assert not alert1.is_duplicate_of(alert4)


class TestAlertBatch:
    """Test AlertBatch model."""

    def test_batch_creation(self):
        """Test batch creation."""
        alerts = [
            Alert(
                type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Warning 1",
                message="Warning message 1",
                source="Component1",
            ),
            Alert(
                type=AlertType.WARNING,
                priority=AlertPriority.LOW,
                title="Warning 2",
                message="Warning message 2",
                source="Component2",
            ),
        ]

        batch = AlertBatch(alerts=alerts)

        assert len(batch.alerts) == 2
        assert batch.alert_count == 2
        assert batch.processed_at is None
        assert isinstance(batch.created_at, datetime)

    def test_highest_priority(self):
        """Test highest priority calculation."""
        alerts = [
            Alert(
                type=AlertType.INFO,
                priority=AlertPriority.LOW,
                title="Info",
                message="Info message",
                source="Component1",
            ),
            Alert(
                type=AlertType.ERROR,
                priority=AlertPriority.CRITICAL,
                title="Critical Error",
                message="Critical message",
                source="Component2",
            ),
            Alert(
                type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Warning",
                message="Warning message",
                source="Component3",
            ),
        ]

        batch = AlertBatch(alerts=alerts)
        assert batch.highest_priority == AlertPriority.CRITICAL

    def test_mark_processed(self):
        """Test mark processed functionality."""
        alerts = [
            Alert(
                type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Warning",
                message="Warning message",
                source="Component",
            )
        ]

        batch = AlertBatch(alerts=alerts)
        assert batch.processed_at is None
        assert alerts[0].batch_id is None

        batch.mark_processed()

        assert batch.processed_at is not None
        assert alerts[0].batch_id == batch.id


class TestAlertConfig:
    """Test AlertConfig model."""

    def test_default_config(self):
        """Test default configuration values."""
        config = AlertConfig()

        assert config.max_alerts_per_minute == 60
        assert config.max_alerts_per_hour == 1000
        assert config.enable_batching is True
        assert config.batch_size == 10
        assert config.batch_timeout_seconds == 60
        assert config.max_retries == 3
        assert config.retry_delay_seconds == 30
        assert config.enable_duplicate_detection is True
        assert config.critical_alert_immediate_send is True
        assert config.default_channels == ["slack"]

    def test_custom_config(self):
        """Test custom configuration values."""
        config = AlertConfig(
            max_alerts_per_minute=120,
            enable_batching=False,
            batch_size=20,
            max_retries=5,
            duplicate_window_minutes=5,
            default_channels=["email", "slack"],
        )

        assert config.max_alerts_per_minute == 120
        assert config.enable_batching is False
        assert config.batch_size == 20
        assert config.max_retries == 5
        assert config.duplicate_window_minutes == 5
        assert config.default_channels == ["email", "slack"]


class TestAlertMetrics:
    """Test AlertMetrics model."""

    def test_default_metrics(self):
        """Test default metrics values."""
        metrics = AlertMetrics()

        assert metrics.total_alerts_generated == 0
        assert metrics.alerts_sent == 0
        assert metrics.alerts_failed == 0
        assert metrics.alerts_rate_limited == 0
        assert metrics.critical_alerts == 0
        assert metrics.error_alerts == 0
        assert metrics.average_processing_time_ms == 0.0
        assert isinstance(metrics.last_updated, datetime)

    def test_increment_alert(self):
        """Test alert increment functionality."""
        metrics = AlertMetrics()

        # Test critical error alert
        alert = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.CRITICAL,
            title="Critical Error",
            message="Critical error message",
            source="CriticalComponent",
        )

        metrics.increment_alert(alert)

        assert metrics.total_alerts_generated == 1
        assert metrics.critical_alerts == 1
        assert metrics.error_alerts == 1
        assert metrics.high_alerts == 0

        # Test medium warning alert
        warning_alert = Alert(
            type=AlertType.WARNING,
            priority=AlertPriority.MEDIUM,
            title="Warning",
            message="Warning message",
            source="WarningComponent",
        )

        metrics.increment_alert(warning_alert)

        assert metrics.total_alerts_generated == 2
        assert metrics.medium_alerts == 1
        assert metrics.warning_alerts == 1

    def test_increment_status(self):
        """Test status increment functionality."""
        metrics = AlertMetrics()

        metrics.increment_status(AlertStatus.SENT)
        assert metrics.alerts_sent == 1

        metrics.increment_status(AlertStatus.FAILED)
        assert metrics.alerts_failed == 1

        metrics.increment_status(AlertStatus.RATE_LIMITED)
        assert metrics.alerts_rate_limited == 1

    def test_update_processing_time(self):
        """Test processing time update."""
        metrics = AlertMetrics()

        # First processing time
        metrics.update_processing_time(100.0)
        assert metrics.average_processing_time_ms == 100.0
        assert metrics.max_processing_time_ms == 100.0

        # Second processing time
        metrics.update_processing_time(200.0)
        assert metrics.average_processing_time_ms == 150.0  # (100 + 200) / 2
        assert metrics.max_processing_time_ms == 200.0

        # Lower processing time (should not update max)
        metrics.update_processing_time(50.0)
        assert metrics.max_processing_time_ms == 200.0


class TestAlertEnums:
    """Test alert enum values."""

    def test_alert_type_values(self):
        """Test AlertType enum values."""
        assert AlertType.ERROR == "error"
        assert AlertType.WARNING == "warning"
        assert AlertType.INFO == "info"
        assert AlertType.PERFORMANCE == "performance"
        assert AlertType.SECURITY == "security"
        assert AlertType.SYSTEM == "system"
        assert AlertType.AUDIT == "audit"

    def test_alert_priority_values(self):
        """Test AlertPriority enum values."""
        assert AlertPriority.CRITICAL == "critical"
        assert AlertPriority.HIGH == "high"
        assert AlertPriority.MEDIUM == "medium"
        assert AlertPriority.LOW == "low"

    def test_alert_status_values(self):
        """Test AlertStatus enum values."""
        assert AlertStatus.PENDING == "pending"
        assert AlertStatus.PROCESSING == "processing"
        assert AlertStatus.SENT == "sent"
        assert AlertStatus.FAILED == "failed"
        assert AlertStatus.RATE_LIMITED == "rate_limited"
        assert AlertStatus.BATCHED == "batched"
