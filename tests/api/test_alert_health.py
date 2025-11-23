"""Tests for alert system health endpoints."""

from unittest.mock import AsyncMock, Mock, patch

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app
from paidsearchnav_mcp.core.config import Settings


@pytest.fixture
def mock_settings():
    """Create mock settings for testing."""
    settings = Mock(spec=Settings)
    settings.environment = "test"

    # Mock logging config for alert manager
    logging_config = Mock()
    logging_config.slack_webhook_url = None
    logging_config.email_to = []
    logging_config.sentry_dsn = None
    settings.logging = logging_config

    return settings


@pytest.fixture
def client():
    """Create test client."""
    app = create_app()

    # Mock repository in app state
    from unittest.mock import AsyncMock, Mock

    mock_repo = Mock()
    mock_repo.check_connection = AsyncMock()
    app.state.repository = mock_repo

    return TestClient(app)


@pytest.fixture(autouse=True)
def reset_alert_manager():
    """Reset alert manager before each test."""
    from paidsearchnav.alerts.manager import reset_alert_manager

    reset_alert_manager()
    yield
    reset_alert_manager()


@pytest.fixture
def mock_alert_manager():
    """Create mock alert manager."""
    manager = Mock()
    manager.get_health_status = AsyncMock()
    manager.get_metrics = AsyncMock()
    manager.test_handlers = AsyncMock()
    manager.flush_pending_alerts = AsyncMock()
    manager.get_config = Mock()
    return manager


class TestAlertHealthEndpoints:
    """Test alert system health endpoints."""

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_main_health_check_includes_alerts(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test that main health check includes alert system status."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager health
            mock_alert_manager.get_health_status.return_value = {"status": "healthy"}
            mock_get_manager.return_value = mock_alert_manager

            response = client.get("/api/v1/health")

            assert response.status_code == 200
            data = response.json()

            # Should include alert system in services
            assert "services" in data
            assert "alerts" in data["services"]

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_alert_health_endpoint(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test dedicated alert health endpoint."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager health response
            mock_health = {
                "status": "healthy",
                "started": True,
                "success_rate": 0.95,
                "total_alerts_processed": 100,
                "alerts_sent": 95,
                "alerts_failed": 5,
                "handlers_registered": 2,
            }
            mock_alert_manager.get_health_status.return_value = mock_health
            mock_get_manager.return_value = mock_alert_manager

            response = client.get("/api/v1/alerts/health")

            assert response.status_code == 200
            data = response.json()

            # Should include health data with timestamp and version
            assert data["status"] == "healthy"
            assert data["started"] is True
            assert data["success_rate"] == 0.95
            assert "timestamp" in data
            assert "version" in data

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_alert_health_endpoint_error(self, mock_get_manager, client, mock_settings):
        """Test alert health endpoint error handling."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager to raise exception
            mock_get_manager.side_effect = Exception("Alert manager error")

            response = client.get("/api/v1/alerts/health")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to check alert system health" in data["detail"]

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_alert_metrics_endpoint(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test alert metrics endpoint."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock metrics
            from paidsearchnav.alerts.models import AlertConfig, AlertMetrics

            mock_metrics = AlertMetrics()
            mock_metrics.total_alerts_generated = 150
            mock_metrics.alerts_sent = 140
            mock_metrics.alerts_failed = 10

            mock_config = AlertConfig()

            mock_alert_manager.get_metrics.return_value = mock_metrics
            mock_alert_manager.get_config.return_value = mock_config
            mock_get_manager.return_value = mock_alert_manager

            response = client.get("/api/v1/alerts/metrics")

            assert response.status_code == 200
            data = response.json()

            # Should include metrics data
            assert data["total_alerts_generated"] == 150
            assert data["alerts_sent"] == 140
            assert data["alerts_failed"] == 10
            assert "timestamp" in data
            assert "configuration" in data

            # Configuration should include key settings
            config = data["configuration"]
            assert "batching_enabled" in config
            assert "batch_size" in config
            assert "max_alerts_per_minute" in config

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_alert_metrics_endpoint_error(
        self, mock_get_manager, client, mock_settings
    ):
        """Test alert metrics endpoint error handling."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager to raise exception
            mock_get_manager.side_effect = Exception("Metrics error")

            response = client.get("/api/v1/alerts/metrics")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to get alert system metrics" in data["detail"]

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_test_alert_handlers_endpoint(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test alert handlers test endpoint."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock test results
            test_results = {"slack": True, "email": True, "sentry": False}

            mock_alert_manager.test_handlers.return_value = test_results
            mock_get_manager.return_value = mock_alert_manager

            response = client.post("/api/v1/alerts/test")

            assert response.status_code == 200
            data = response.json()

            # Should include test results
            assert data["status"] == "partial_failure"  # One handler failed
            assert data["total_handlers"] == 3
            assert data["successful_handlers"] == 2
            assert data["failed_handlers"] == 1
            assert data["handler_results"] == test_results
            assert "timestamp" in data

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_test_alert_handlers_all_success(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test alert handlers test endpoint with all handlers successful."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock all successful test results
            test_results = {"slack": True, "email": True}

            mock_alert_manager.test_handlers.return_value = test_results
            mock_get_manager.return_value = mock_alert_manager

            response = client.post("/api/v1/alerts/test")

            assert response.status_code == 200
            data = response.json()

            # Should show success status
            assert data["status"] == "success"
            assert data["successful_handlers"] == 2
            assert data["failed_handlers"] == 0

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_test_alert_handlers_error(self, mock_get_manager, client, mock_settings):
        """Test alert handlers test endpoint error handling."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager to raise exception
            mock_get_manager.side_effect = Exception("Handler test error")

            response = client.post("/api/v1/alerts/test")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to test alert handlers" in data["detail"]

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_flush_pending_alerts_endpoint(
        self, mock_get_manager, client, mock_settings, mock_alert_manager
    ):
        """Test flush pending alerts endpoint."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock health status before and after flushing
            mock_alert_manager.get_health_status.side_effect = [
                {"active_batches": 3},  # Before flush
                {"active_batches": 0},  # After flush
            ]
            mock_alert_manager.flush_pending_alerts.return_value = None
            mock_get_manager.return_value = mock_alert_manager

            response = client.post("/api/v1/alerts/flush")

            assert response.status_code == 200
            data = response.json()

            # Should include flush results
            assert data["status"] == "success"
            assert data["batches_flushed"] == 3
            assert data["active_batches_before"] == 3
            assert data["active_batches_after"] == 0
            assert "timestamp" in data

            # Should have called flush method
            mock_alert_manager.flush_pending_alerts.assert_called_once()

    @patch("paidsearchnav.api.v1.health.get_alert_manager")
    def test_flush_pending_alerts_error(self, mock_get_manager, client, mock_settings):
        """Test flush pending alerts endpoint error handling."""
        # Mock dependencies
        with patch(
            "paidsearchnav.api.v1.health.get_settings", return_value=mock_settings
        ):
            # Mock alert manager to raise exception
            mock_get_manager.side_effect = Exception("Flush error")

            response = client.post("/api/v1/alerts/flush")

            assert response.status_code == 500
            data = response.json()
            assert "Failed to flush pending alerts" in data["detail"]

    def test_alert_endpoints_require_settings(self, client):
        """Test that alert endpoints require settings."""
        # Without proper settings, get_alert_manager should fail during initialization
        # These endpoints depend on get_alert_manager which needs settings
        endpoints = ["/api/v1/alerts/health", "/api/v1/alerts/metrics"]

        with patch("paidsearchnav.api.v1.health.get_alert_manager") as mock_get_manager:
            # Mock to raise an exception when trying to get alert manager without settings
            mock_get_manager.side_effect = ValueError(
                "Settings required for first alert manager initialization"
            )

            for endpoint in endpoints:
                response = client.get(endpoint)
                # Should get 500 error when alert manager initialization fails
                assert response.status_code >= 400

    def test_alert_post_endpoints_require_settings(self, client):
        """Test that alert POST endpoints require settings."""
        # Without proper settings, get_alert_manager should fail during initialization
        endpoints = ["/api/v1/alerts/test", "/api/v1/alerts/flush"]

        with patch("paidsearchnav.api.v1.health.get_alert_manager") as mock_get_manager:
            # Mock to raise an exception when trying to get alert manager without settings
            mock_get_manager.side_effect = ValueError(
                "Settings required for first alert manager initialization"
            )

            for endpoint in endpoints:
                response = client.post(endpoint)
                # Should get 500 error when alert manager initialization fails
                assert response.status_code >= 400
