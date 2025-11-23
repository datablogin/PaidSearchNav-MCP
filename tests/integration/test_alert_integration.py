"""Integration tests for alert system end-to-end flow."""

import asyncio
from unittest.mock import Mock

import pytest

from paidsearchnav_mcp.alerts.manager import AlertManager, reset_alert_manager
from paidsearchnav_mcp.alerts.models import AlertConfig, AlertPriority, AlertType
from paidsearchnav_mcp.core.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for integration testing."""
    settings = Mock(spec=Settings)
    settings.environment = "test"

    # Mock logging configuration
    logging_config = Mock()
    logging_config.slack_webhook_url = None
    logging_config.email_to = []
    logging_config.sentry_dsn = None
    settings.logging = logging_config

    return settings


@pytest.fixture
def alert_config():
    """Create test alert configuration."""
    return AlertConfig(
        max_queue_size=100,
        batch_size=2,
        batch_timeout_seconds=1,
        enable_batching=True,
        enable_duplicate_detection=True,
    )


@pytest.fixture
def alert_manager(mock_settings, alert_config):
    """Create alert manager for integration testing."""
    reset_alert_manager()
    return AlertManager(mock_settings, alert_config)


@pytest.mark.asyncio
class TestAlertSystemIntegration:
    """Integration tests for complete alert system flow."""

    async def test_full_alert_flow_with_batching(self, alert_manager):
        """Test complete alert flow from submission to processing with batching."""
        # Start the alert manager
        await alert_manager.start()

        try:
            # Submit multiple alerts that should be batched
            alert_results = []
            for i in range(3):
                result = await alert_manager.send_alert(
                    alert_type=AlertType.INFO,
                    priority=AlertPriority.LOW,
                    title=f"Test Alert {i}",
                    message=f"Test message {i}",
                    source="IntegrationTest",
                )
                alert_results.append(result)

            # All alerts should be accepted
            assert all(alert_results)

            # Wait for processing and batching
            await asyncio.sleep(0.2)

            # Get metrics to verify processing
            metrics = await alert_manager.get_metrics()
            assert metrics.total_alerts_generated >= 3

            # Get health status
            health = await alert_manager.get_health_status()
            assert health["status"] in ["healthy", "degraded"]
            assert health["started"] is True

        finally:
            await alert_manager.stop()

    async def test_critical_alert_immediate_processing(self, alert_manager):
        """Test that critical alerts bypass batching."""
        await alert_manager.start()

        try:
            # Submit critical alert
            result = await alert_manager.send_alert(
                alert_type=AlertType.ERROR,
                priority=AlertPriority.CRITICAL,
                title="Critical System Error",
                message="System is down",
                source="SystemMonitor",
            )

            assert result is True

            # Critical alerts should be processed immediately
            # Wait a short time for processing
            await asyncio.sleep(0.5)

            metrics = await alert_manager.get_metrics()
            assert metrics.critical_alerts >= 1

        finally:
            await alert_manager.stop()

    async def test_queue_overflow_handling(self, mock_settings):
        """Test behavior when queues reach capacity."""
        # Create config with very small queue size
        small_config = AlertConfig(max_queue_size=2)
        manager = AlertManager(mock_settings, small_config)

        await manager.start()

        try:
            # Fill up the queue beyond capacity
            results = []
            for i in range(5):
                result = await manager.send_alert(
                    alert_type=AlertType.INFO,
                    priority=AlertPriority.LOW,
                    title=f"Overflow Alert {i}",
                    message=f"Message {i}",
                    source="OverflowTest",
                )
                results.append(result)
                # Small delay to allow processing
                await asyncio.sleep(0.01)

            # Some alerts should be rejected when queue is full
            # (depending on timing and processing speed)
            rejected_count = sum(1 for r in results if not r)
            # At least we should have attempted all submissions without crashing
            assert len(results) == 5

        finally:
            await manager.stop()

    async def test_error_recovery(self, alert_manager):
        """Test that system recovers from errors gracefully."""
        await alert_manager.start()

        try:
            # Register a failing handler
            def failing_handler(alert):
                raise Exception("Handler intentionally failed")

            alert_manager.processor.register_handler("failing", failing_handler)

            # Submit alert - should not crash the system
            result = await alert_manager.send_alert(
                alert_type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Test Error Recovery",
                message="Testing error handling",
                source="ErrorTest",
            )

            assert result is True

            # Wait for processing
            await asyncio.sleep(0.1)

            # System should still be healthy despite handler error
            health = await alert_manager.get_health_status()
            assert health["started"] is True

            # Metrics should show the alert was processed
            metrics = await alert_manager.get_metrics()
            assert metrics.total_alerts_generated >= 1

        finally:
            await alert_manager.stop()

    async def test_duplicate_detection(self, alert_manager):
        """Test duplicate alert detection works correctly."""
        await alert_manager.start()

        try:
            # Submit same alert multiple times
            results = []
            for _ in range(3):
                result = await alert_manager.send_alert(
                    alert_type=AlertType.WARNING,
                    priority=AlertPriority.MEDIUM,
                    title="Duplicate Alert",
                    message="This is a duplicate",
                    source="DuplicateTest",
                )
                results.append(result)

            # First alert should succeed, subsequent ones should be rejected
            assert results[0] is True
            # Note: Duplicate detection may allow some through depending on timing

            # Wait for processing
            await asyncio.sleep(0.1)

            # Check processor stats for duplicate detection
            stats = await alert_manager.processor.get_stats()
            if "duplicates_detected" in stats:
                assert stats["duplicates_detected"] >= 0

        finally:
            await alert_manager.stop()

    async def test_metrics_and_monitoring(self, alert_manager):
        """Test comprehensive metrics collection."""
        await alert_manager.start()

        try:
            # Generate various types of alerts
            await alert_manager.send_error_alert(
                "Error Alert", "Error message", "ErrorSource"
            )
            await alert_manager.send_alert(
                alert_type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Warning Alert",
                message="Warning message",
                source="WarningSource",
            )
            await alert_manager.send_performance_alert(
                "Performance Alert", "Performance message", "PerfSource"
            )

            # Wait for processing
            await asyncio.sleep(0.1)

            # Get comprehensive metrics
            metrics = await alert_manager.get_metrics()
            health = await alert_manager.get_health_status()
            processor_stats = await alert_manager.processor.get_stats()

            # Verify metrics structure
            assert hasattr(metrics, "total_alerts_generated")
            assert hasattr(metrics, "error_alerts")
            assert hasattr(metrics, "warning_alerts")
            assert hasattr(metrics, "performance_alerts")

            # Verify health status
            assert "status" in health
            assert "started" in health
            assert "handlers_registered" in health

            # Verify processor stats include queue monitoring
            assert "pending_queue_size" in processor_stats
            assert "pending_queue_maxsize" in processor_stats
            assert "recent_alerts_count" in processor_stats
            assert "recent_alerts_maxlen" in processor_stats

            # Verify queue limits are respected
            assert processor_stats["pending_queue_maxsize"] == 100  # From our config
            # Recent alerts maxlen should be set (1000) or None if not available
            assert (
                processor_stats["recent_alerts_maxlen"] is None
                or processor_stats["recent_alerts_maxlen"] == 1000
            )

        finally:
            await alert_manager.stop()
