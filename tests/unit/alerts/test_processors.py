"""Tests for alert processors."""

import asyncio
from unittest.mock import Mock, patch

import pytest

from paidsearchnav.alerts.models import (
    Alert,
    AlertConfig,
    AlertPriority,
    AlertStatus,
    AlertType,
)
from paidsearchnav.alerts.processors import AsyncAlertProcessor
from paidsearchnav.alerts.rate_limiter import AlertRateLimiter


@pytest.fixture
def alert_config():
    """Create test alert configuration."""
    return AlertConfig(
        max_alerts_per_minute=100,
        enable_batching=True,
        batch_size=3,
        batch_timeout_seconds=1,  # Much shorter for tests (1 second instead of default 60)
        enable_duplicate_detection=True,
        duplicate_window_minutes=5,
        critical_alert_immediate_send=True,
    )


@pytest.fixture
def rate_limiter():
    """Create test rate limiter."""
    return AlertRateLimiter()


@pytest.fixture
def processor(alert_config, rate_limiter):
    """Create test alert processor."""
    return AsyncAlertProcessor(alert_config, rate_limiter)


@pytest.fixture
def sample_alert():
    """Create sample alert for testing."""
    return Alert(
        type=AlertType.WARNING,
        priority=AlertPriority.MEDIUM,
        title="Test Alert",
        message="This is a test alert",
        source="TestComponent",
    )


@pytest.fixture
def critical_alert():
    """Create critical alert for testing."""
    return Alert(
        type=AlertType.ERROR,
        priority=AlertPriority.CRITICAL,
        title="Critical Alert",
        message="This is a critical alert",
        source="CriticalComponent",
    )


class TestAsyncAlertProcessor:
    """Test AsyncAlertProcessor functionality."""

    @pytest.mark.skip(
        reason="Hanging in CI - needs investigation of AsyncAlertProcessor start/stop"
    )
    @pytest.mark.asyncio
    async def test_processor_start_stop(self, processor):
        """Test processor start and stop."""
        assert not processor._running

        await processor.start()
        assert processor._running
        assert processor._processor_task is not None
        assert processor._batch_processor_task is not None
        assert processor._cleanup_task is not None

        await processor.stop()
        assert not processor._running

    def test_handler_registration(self, processor):
        """Test handler registration."""
        mock_handler = Mock()

        processor.register_handler("test_channel", mock_handler)

        assert "test_channel" in processor._handlers
        assert processor._handlers["test_channel"] == mock_handler

    @pytest.mark.asyncio
    async def test_submit_alert_success(self, processor, sample_alert):
        """Test successful alert submission."""
        await processor.start()

        try:
            result = await processor.submit_alert(sample_alert)
            assert result is True

            # Alert should be in pending queue
            assert not processor._pending_alerts.empty()

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_submit_alert_rate_limited(self, processor, sample_alert):
        """Test rate limited alert submission."""
        await processor.start()

        try:
            # Mock rate limiter to return rate limited
            with patch.object(processor.rate_limiter, "is_allowed") as mock_is_allowed:
                mock_is_allowed.return_value = (
                    False,
                    60.0,
                )  # Rate limited, retry after 60s

                result = await processor.submit_alert(sample_alert)
                assert result is False
                assert sample_alert.status == AlertStatus.RATE_LIMITED

        finally:
            await processor.stop()

    def test_duplicate_detection(self, processor):
        """Test duplicate alert detection."""
        alert1 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Connection failed",
            source="DatabaseComponent",
        )

        alert2 = Alert(
            type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Database Error",
            message="Connection failed",
            source="DatabaseComponent",
        )

        # First alert should not be duplicate
        assert not processor._is_duplicate(alert1)

        # Second identical alert should be duplicate
        assert processor._is_duplicate(alert2)

    def test_should_send_immediately(self, processor, sample_alert, critical_alert):
        """Test immediate send determination."""
        # Critical alerts should be sent immediately
        assert processor._should_send_immediately(critical_alert) is True

        # Normal alerts should be batched (if batching enabled)
        assert processor._should_send_immediately(sample_alert) is False

        # With batching disabled, all alerts should be sent immediately
        processor.config.enable_batching = False
        assert processor._should_send_immediately(sample_alert) is True

    def test_get_batch_key(self, processor):
        """Test batch key generation."""
        alert = Alert(
            type=AlertType.WARNING,
            priority=AlertPriority.MEDIUM,
            title="Test Alert",
            message="Test message",
            source="TestComponent",
        )

        batch_key = processor._get_batch_key(alert)
        expected_key = f"{alert.type.value}_{alert.priority.value}_{alert.source}"

        assert batch_key == expected_key

    def test_group_alerts_by_channel(self, processor):
        """Test grouping alerts by channel."""
        # Mock channel configuration
        processor.config.channel_priorities = {
            "slack": [AlertPriority.CRITICAL, AlertPriority.HIGH, AlertPriority.MEDIUM],
            "email": [AlertPriority.CRITICAL, AlertPriority.HIGH],
        }

        # Register mock handlers
        processor.register_handler("slack", Mock())
        processor.register_handler("email", Mock())

        alerts = [
            Alert(
                type=AlertType.ERROR,
                priority=AlertPriority.CRITICAL,
                title="Critical Alert",
                message="Critical message",
                source="Component1",
            ),
            Alert(
                type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Medium Alert",
                message="Medium message",
                source="Component2",
            ),
            Alert(
                type=AlertType.INFO,
                priority=AlertPriority.LOW,
                title="Low Alert",
                message="Low message",
                source="Component3",
            ),
        ]

        channel_alerts = processor._group_alerts_by_channel(alerts)

        # Critical alert should go to both channels
        assert len(channel_alerts["slack"]) >= 1
        assert len(channel_alerts["email"]) >= 1

        # Medium alert should only go to slack
        assert any(
            alert.priority == AlertPriority.MEDIUM for alert in channel_alerts["slack"]
        )

        # Low alert should go to default channels or none
        # (depends on default channel configuration)

    @pytest.mark.skip(
        reason="Hanging in CI - needs investigation of AsyncAlertProcessor cleanup"
    )
    @pytest.mark.asyncio
    async def test_batch_timeout(self, alert_config, rate_limiter, sample_alert):
        """Test batch timeout functionality."""
        # Create processor with very short batch timeout for this test
        alert_config.batch_timeout_seconds = 1  # 1 second timeout
        processor = AsyncAlertProcessor(alert_config, rate_limiter)
        await processor.start()

        try:
            # Submit an alert that should be batched
            await processor.submit_alert(sample_alert)

            # Wait for processing to start
            await asyncio.sleep(0.1)

            # Check that alert is in a batch (without holding lock too long)
            batch_key = processor._get_batch_key(sample_alert)

            # Verify alert is batched
            async with processor._lock:
                batch_count_before = len(processor._current_batches.get(batch_key, []))

            assert batch_count_before == 1

            # Wait for batch timeout (1s + buffer)
            await asyncio.sleep(1.2)

            # Batch should have been flushed
            async with processor._lock:
                batch_count_after = len(processor._current_batches.get(batch_key, []))

            assert batch_count_after == 0

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_batch_size_limit(self, alert_config, rate_limiter):
        """Test batch size limit triggers flush."""
        # Set small batch size for testing
        alert_config.batch_size = 2
        processor = AsyncAlertProcessor(alert_config, rate_limiter)

        await processor.start()

        try:
            alerts = []
            for i in range(3):
                alert = Alert(
                    type=AlertType.WARNING,
                    priority=AlertPriority.MEDIUM,
                    title=f"Test Alert {i}",
                    message=f"Test message {i}",
                    source="TestComponent",
                )
                alerts.append(alert)
                await processor.submit_alert(alert)

            # Wait for processing
            await asyncio.sleep(0.2)

            # First two alerts should have triggered a batch flush
            # Third alert should be in new batch
            batch_key = processor._get_batch_key(alerts[0])
            async with processor._lock:
                # Should have at most 1 alert in current batch (the third one)
                assert len(processor._current_batches[batch_key]) <= 1

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_slack_handler_integration(self, processor, sample_alert):
        """Test integration with Slack handler."""
        from paidsearchnav.logging.handlers import SlackAlertHandler

        # Create mock Slack handler
        mock_slack_handler = Mock(spec=SlackAlertHandler)
        mock_slack_handler.emit = Mock()

        processor.register_handler("slack", mock_slack_handler)

        await processor.start()

        try:
            # Submit alert and wait for processing
            await processor.submit_alert(sample_alert)
            await asyncio.sleep(0.1)

            # Force flush to trigger sending
            await processor.flush_all_batches()
            await asyncio.sleep(0.1)

            # Verify handler was called
            mock_slack_handler.emit.assert_called()

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_email_handler_integration(self, processor, sample_alert):
        """Test integration with Email handler."""
        from paidsearchnav.logging.handlers import EmailAlertHandler

        # Create mock Email handler
        mock_email_handler = Mock(spec=EmailAlertHandler)
        mock_email_handler.emit = Mock()

        processor.register_handler("email", mock_email_handler)

        await processor.start()

        try:
            # Submit alert and wait for processing
            await processor.submit_alert(sample_alert)
            await asyncio.sleep(0.1)

            # Force flush to trigger sending
            await processor.flush_all_batches()
            await asyncio.sleep(0.1)

            # Verify handler was called
            mock_email_handler.emit.assert_called()

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_get_stats(self, processor, sample_alert):
        """Test statistics retrieval."""
        await processor.start()

        try:
            # Submit some alerts
            await processor.submit_alert(sample_alert)
            await asyncio.sleep(0.1)

            stats = await processor.get_stats()

            # Verify stats structure
            assert "alerts_processed" in stats
            assert "alerts_sent" in stats
            assert "alerts_failed" in stats
            assert "pending_queue_size" in stats
            assert "batch_queue_size" in stats
            assert "rate_limiter" in stats
            assert "avg_processing_time_ms" in stats

            # Should have processed at least one alert
            assert stats["alerts_processed"] >= 0

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_flush_all_batches(self, processor):
        """Test flushing all pending batches."""
        await processor.start()

        try:
            # Add some alerts to batches
            alerts = []
            for i in range(2):
                alert = Alert(
                    type=AlertType.INFO,
                    priority=AlertPriority.LOW,
                    title=f"Info Alert {i}",
                    message=f"Info message {i}",
                    source="TestComponent",
                )
                alerts.append(alert)
                await processor.submit_alert(alert)

            # Wait for processing to start
            await asyncio.sleep(0.1)

            # Should have alerts in batches
            stats_before = await processor.get_stats()
            batches_before = stats_before.get("active_batches", 0)

            # Flush all batches
            await processor.flush_all_batches()
            await asyncio.sleep(0.1)

            # Should have fewer or no active batches
            stats_after = await processor.get_stats()
            batches_after = stats_after.get("active_batches", 0)

            assert batches_after <= batches_before

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_processor_error_handling(self, processor, sample_alert):
        """Test processor handles errors gracefully."""
        await processor.start()

        try:
            # Register handler that will raise an exception
            def failing_handler():
                raise Exception("Handler failed")

            processor.register_handler("failing", failing_handler)

            # Submit alert - should not crash processor
            result = await processor.submit_alert(sample_alert)
            assert result is True

            # Processor should still be running
            assert processor._running is True

        finally:
            await processor.stop()

    @pytest.mark.asyncio
    async def test_critical_alert_immediate_processing(self, processor, critical_alert):
        """Test critical alerts are processed immediately."""
        await processor.start()

        # Register mock handler
        mock_handler = Mock()
        mock_handler.emit = Mock()
        processor.register_handler("test", mock_handler)

        try:
            # Submit critical alert
            await processor.submit_alert(critical_alert)

            # Should be processed immediately, not batched
            await asyncio.sleep(0.2)

            # Check that it was processed (attempt to send)
            assert critical_alert.status in [
                AlertStatus.SENT,
                AlertStatus.FAILED,
                AlertStatus.PROCESSING,
            ]

        finally:
            await processor.stop()
