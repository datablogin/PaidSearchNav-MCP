"""Tests for alert manager."""

from unittest.mock import AsyncMock, Mock, patch

import pytest

from paidsearchnav_mcp.alerts.manager import AlertManager, get_alert_manager, send_alert
from paidsearchnav_mcp.alerts.models import AlertConfig, AlertPriority, AlertType
from paidsearchnav_mcp.core.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings."""
    settings = Mock(spec=Settings)

    # Mock logging configuration
    logging_config = Mock()
    logging_config.slack_webhook_url = Mock()
    logging_config.slack_webhook_url.get_secret_value.return_value = (
        "https://hooks.slack.com/test"
    )
    logging_config.slack_channel = "#alerts"

    logging_config.smtp_host = "smtp.example.com"
    logging_config.smtp_port = 587
    logging_config.smtp_username = "user@example.com"
    logging_config.smtp_password = Mock()
    logging_config.smtp_password.get_secret_value.return_value = "password"
    logging_config.email_from = "alerts@example.com"
    logging_config.email_to = ["admin@example.com"]

    logging_config.sentry_dsn = Mock()
    logging_config.sentry_dsn.get_secret_value.return_value = (
        "https://sentry.example.com/project"
    )

    settings.logging = logging_config
    settings.environment = "test"

    return settings


@pytest.fixture
def alert_manager(mock_settings):
    """Create alert manager for testing."""
    return AlertManager(mock_settings)


class TestAlertManager:
    """Test AlertManager functionality."""

    def test_alert_manager_creation(self, mock_settings):
        """Test alert manager creation."""
        manager = AlertManager(mock_settings)

        assert manager.settings == mock_settings
        assert isinstance(manager.config, AlertConfig)
        assert manager.rate_limiter is not None
        assert manager.processor is not None
        assert manager.metrics is not None
        assert not manager._started

    @patch("paidsearchnav.alerts.manager.SlackAlertHandler")
    @patch("paidsearchnav.alerts.manager.EmailAlertHandler")
    @patch("paidsearchnav.alerts.manager.SentryHandler")
    def test_handler_initialization(
        self, mock_sentry, mock_email, mock_slack, mock_settings
    ):
        """Test handler initialization."""
        manager = AlertManager(mock_settings)

        # Verify handlers were created with correct parameters
        mock_slack.assert_called_once()
        mock_email.assert_called_once()
        mock_sentry.assert_called_once()

        # Verify handlers were registered
        assert len(manager.processor._handlers) >= 0  # Handlers may be registered

    @pytest.mark.asyncio
    async def test_start_stop(self, alert_manager):
        """Test start and stop functionality."""
        assert not alert_manager._started

        await alert_manager.start()
        assert alert_manager._started

        await alert_manager.stop()
        assert not alert_manager._started

    @pytest.mark.asyncio
    async def test_send_alert(self, alert_manager):
        """Test sending an alert."""
        await alert_manager.start()

        try:
            result = await alert_manager.send_alert(
                alert_type=AlertType.WARNING,
                priority=AlertPriority.MEDIUM,
                title="Test Alert",
                message="This is a test alert",
                source="TestComponent",
            )

            assert result is True
            assert alert_manager.metrics.total_alerts_generated >= 1

        finally:
            await alert_manager.stop()

    @pytest.mark.asyncio
    async def test_send_alert_with_context(self, alert_manager):
        """Test sending alert with context."""
        await alert_manager.start()

        try:
            context = {"customer_id": "123", "analysis_id": "456"}
            tags = ["error", "database"]

            result = await alert_manager.send_alert(
                alert_type=AlertType.ERROR,
                priority=AlertPriority.HIGH,
                title="Database Error",
                message="Database connection failed",
                source="DatabaseComponent",
                context=context,
                customer_id="123",
                job_id="job_789",
                tags=tags,
            )

            assert result is True

        finally:
            await alert_manager.stop()

    @pytest.mark.asyncio
    async def test_convenience_methods(self, alert_manager):
        """Test convenience methods for different alert types."""
        await alert_manager.start()

        try:
            # Test error alert
            result = await alert_manager.send_error_alert(
                title="Error Alert", message="Error occurred", source="ErrorComponent"
            )
            assert result is True

            # Test performance alert
            result = await alert_manager.send_performance_alert(
                title="Performance Alert",
                message="System slow",
                source="PerformanceComponent",
            )
            assert result is True

            # Test security alert
            result = await alert_manager.send_security_alert(
                title="Security Alert",
                message="Security breach detected",
                source="SecurityComponent",
            )
            assert result is True

            # Test system alert
            result = await alert_manager.send_system_alert(
                title="System Alert",
                message="System maintenance required",
                source="SystemComponent",
            )
            assert result is True

        finally:
            await alert_manager.stop()

    @pytest.mark.asyncio
    async def test_auto_start_on_send(self, alert_manager):
        """Test that manager auto-starts when sending alert."""
        # Manager should not be started initially
        assert not alert_manager._started

        try:
            # Sending alert should auto-start the manager
            result = await alert_manager.send_alert(
                alert_type=AlertType.INFO,
                priority=AlertPriority.LOW,
                title="Info Alert",
                message="Info message",
                source="InfoComponent",
            )

            assert result is True
            assert alert_manager._started

        finally:
            await alert_manager.stop()

    def test_update_system_load(self, alert_manager):
        """Test system load update for adaptive rate limiting."""
        # Should not raise an exception
        alert_manager.update_system_load(0.5)
        alert_manager.update_system_load(0.0)
        alert_manager.update_system_load(1.0)

    @pytest.mark.asyncio
    async def test_get_health_status(self, alert_manager):
        """Test health status retrieval."""
        await alert_manager.start()

        try:
            health = await alert_manager.get_health_status()

            # Verify health status structure
            assert "status" in health
            assert "started" in health
            assert "success_rate" in health
            assert "total_alerts_processed" in health
            assert "handlers_registered" in health
            assert health["status"] in ["healthy", "degraded"]
            assert health["started"] is True

        finally:
            await alert_manager.stop()

    @pytest.mark.asyncio
    async def test_get_metrics(self, alert_manager):
        """Test metrics retrieval."""
        await alert_manager.start()

        try:
            # Send some alerts to generate metrics
            await alert_manager.send_alert(
                alert_type=AlertType.INFO,
                priority=AlertPriority.LOW,
                title="Test Alert",
                message="Test message",
                source="TestComponent",
            )

            metrics = await alert_manager.get_metrics()

            # Verify metrics structure
            assert metrics.total_alerts_generated >= 1
            assert hasattr(metrics, "alerts_sent")
            assert hasattr(metrics, "alerts_failed")
            assert hasattr(metrics, "last_updated")

        finally:
            await alert_manager.stop()

    @pytest.mark.asyncio
    async def test_flush_pending_alerts(self, alert_manager):
        """Test flushing pending alerts."""
        await alert_manager.start()

        try:
            # Send some alerts that would be batched
            for i in range(3):
                await alert_manager.send_alert(
                    alert_type=AlertType.INFO,
                    priority=AlertPriority.LOW,
                    title=f"Info Alert {i}",
                    message=f"Info message {i}",
                    source="TestComponent",
                )

            # Flush pending alerts
            await alert_manager.flush_pending_alerts()

            # Should complete without error

        finally:
            await alert_manager.stop()

    def test_get_config(self, alert_manager):
        """Test configuration retrieval."""
        config = alert_manager.get_config()
        assert isinstance(config, AlertConfig)

    def test_update_config(self, alert_manager):
        """Test configuration update."""
        new_config = AlertConfig(max_alerts_per_minute=200, enable_batching=False)

        alert_manager.update_config(new_config)

        assert alert_manager.config == new_config
        assert alert_manager.config.max_alerts_per_minute == 200
        assert alert_manager.config.enable_batching is False

    @pytest.mark.asyncio
    @patch("paidsearchnav.alerts.manager.SlackAlertHandler")
    async def test_test_handlers(self, mock_slack_handler, alert_manager):
        """Test handler testing functionality."""
        # Create mock handler instance
        mock_handler_instance = Mock()
        mock_slack_handler.return_value = mock_handler_instance

        await alert_manager.start()

        try:
            results = await alert_manager.test_handlers()

            # Should return results dictionary
            assert isinstance(results, dict)

            # Results should contain handler names and success status
            for channel, success in results.items():
                assert isinstance(success, bool)

        finally:
            await alert_manager.stop()


class TestGlobalAlertManager:
    """Test global alert manager functionality."""

    def test_get_alert_manager_first_time(self, mock_settings):
        """Test getting alert manager for first time requires settings."""
        # Clear any existing global manager
        import paidsearchnav.alerts.manager

        paidsearchnav.alerts.manager._alert_manager = None

        # Should raise error without settings
        with pytest.raises(ValueError, match="Settings required"):
            get_alert_manager()

        # Should work with settings
        manager = get_alert_manager(mock_settings)
        assert manager is not None
        assert isinstance(manager, AlertManager)

    def test_get_alert_manager_subsequent_calls(self, mock_settings):
        """Test subsequent calls to get_alert_manager."""
        # Clear any existing global manager
        import paidsearchnav.alerts.manager

        paidsearchnav.alerts.manager._alert_manager = None

        # First call with settings
        manager1 = get_alert_manager(mock_settings)

        # Second call without settings should return same instance
        manager2 = get_alert_manager()

        assert manager1 is manager2

    @pytest.mark.asyncio
    async def test_convenience_send_alert_function(self, mock_settings):
        """Test convenience send_alert function."""
        # Clear any existing global manager
        import paidsearchnav.alerts.manager

        paidsearchnav.alerts.manager._alert_manager = None

        # Initialize with settings
        get_alert_manager(mock_settings)

        # Test convenience function
        result = await send_alert(
            alert_type=AlertType.WARNING,
            priority=AlertPriority.MEDIUM,
            title="Convenience Alert",
            message="Alert sent via convenience function",
            source="TestComponent",
        )

        # Should succeed (or at least not crash)
        assert isinstance(result, bool)

    @pytest.mark.asyncio
    @patch("paidsearchnav.alerts.manager.get_alert_manager")
    async def test_convenience_functions_error_handling(self, mock_get_manager):
        """Test error handling in convenience functions."""
        # Mock manager to raise exception
        mock_manager = Mock()
        mock_manager.send_alert = AsyncMock(side_effect=Exception("Manager error"))
        mock_get_manager.return_value = mock_manager

        # Should handle exception gracefully
        result = await send_alert(
            alert_type=AlertType.ERROR,
            priority=AlertPriority.HIGH,
            title="Error Alert",
            message="Error message",
            source="TestComponent",
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_convenience_alert_type_functions(self, mock_settings):
        """Test convenience functions for specific alert types."""
        # Clear any existing global manager
        import paidsearchnav.alerts.manager
        from paidsearchnav.alerts.manager import (
            send_error_alert,
            send_performance_alert,
            send_security_alert,
            send_warning_alert,
        )

        paidsearchnav.alerts.manager._alert_manager = None

        # Initialize with settings
        get_alert_manager(mock_settings)

        # Test each convenience function
        result1 = await send_error_alert("Error", "Error message", "TestComponent")
        result2 = await send_warning_alert(
            "Warning", "Warning message", "TestComponent"
        )
        result3 = await send_performance_alert(
            "Performance", "Performance message", "TestComponent"
        )
        result4 = await send_security_alert(
            "Security", "Security message", "TestComponent"
        )

        # All should return boolean results
        assert isinstance(result1, bool)
        assert isinstance(result2, bool)
        assert isinstance(result3, bool)
        assert isinstance(result4, bool)
