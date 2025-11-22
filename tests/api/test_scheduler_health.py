"""Tests for scheduler health endpoints."""

from unittest.mock import AsyncMock, MagicMock

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import app


class TestSchedulerHealthEndpoints:
    """Test scheduler health and metrics endpoints."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_scheduler_health_check_success(self):
        """Test successful scheduler health check."""
        # Mock scheduler API and scheduler
        mock_scheduler_api = MagicMock()
        mock_scheduler = AsyncMock()
        mock_scheduler_api._ensure_scheduler.return_value = mock_scheduler

        # Mock health status response
        mock_health_status = {
            "scheduler": {
                "running": True,
                "instance_id": "test-123",
                "start_time": "2023-01-01T00:00:00",
                "active_jobs": 2,
            },
            "database": {"connected": True},
            "google_ads_api": {"available": True},
            "system": {"memory_bytes": 1024.0 * 1024 * 1024, "cpu_percentage": 25.5},
        }
        mock_scheduler.get_health_status = AsyncMock(return_value=mock_health_status)

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/health")

            assert response.status_code == 200
            data = response.json()

            assert data["status"] == "healthy"
            assert "timestamp" in data
            assert data["scheduler"]["running"] is True
            assert data["database"]["connected"] is True
            assert data["google_ads_api"]["available"] is True
            assert data["system"]["memory_bytes"] == 1024.0 * 1024 * 1024
            assert data["system"]["cpu_percentage"] == 25.5
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_scheduler_health_check_disabled(self):
        """Test scheduler health check when scheduler has issues."""
        # Mock scheduler API to raise exception when trying to get scheduler
        mock_scheduler_api = MagicMock()
        mock_scheduler_api._ensure_scheduler.side_effect = Exception(
            "Scheduler initialization failed"
        )

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/health")

            # Expect 500 error when scheduler API fails
            assert response.status_code == 500
            data = response.json()
            assert "Failed to check scheduler health" in data["detail"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_scheduler_health_check_error(self):
        """Test scheduler health check with error."""
        # Mock scheduler API to raise exception during health check
        mock_scheduler_api = MagicMock()
        mock_scheduler = AsyncMock()
        mock_scheduler.get_health_status.side_effect = Exception("Health check failed")
        mock_scheduler_api._ensure_scheduler.return_value = mock_scheduler

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/health")

            # Should get 500 error when health check fails
            assert response.status_code == 500
            data = response.json()
            assert "Failed to check scheduler health" in data["detail"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_scheduler_metrics_enabled(self):
        """Test scheduler metrics when enabled."""
        # Mock scheduler API and scheduler
        mock_scheduler_api = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler_api._ensure_scheduler.return_value = mock_scheduler

        # Mock metrics response
        mock_metrics = {
            "active_jobs": 3,
            "max_running_jobs": 100,
            "instance_id": "test-instance-123",
            "start_time": "2023-01-01T00:00:00",
            "scheduler_running": True,
        }
        mock_scheduler.get_metrics_summary.return_value = mock_metrics

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/metrics")

            assert response.status_code == 200
            data = response.json()

            assert "timestamp" in data
            assert data["active_jobs"] == 3
            assert data["max_running_jobs"] == 100
            assert data["instance_id"] == "test-instance-123"
            assert data["scheduler_running"] is True
            assert "note" in data
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_scheduler_metrics_disabled(self):
        """Test scheduler metrics when scheduler API fails."""
        # Mock scheduler API to raise exception when trying to get scheduler
        mock_scheduler_api = MagicMock()
        mock_scheduler_api._ensure_scheduler.side_effect = Exception(
            "Scheduler disabled"
        )

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/metrics")

            # Expect 500 error when scheduler API fails
            assert response.status_code == 500
            data = response.json()
            assert "Failed to get scheduler metrics" in data["detail"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    def test_scheduler_metrics_error(self):
        """Test scheduler metrics with error."""
        # Mock scheduler API to fail during metrics collection
        mock_scheduler_api = MagicMock()
        mock_scheduler = MagicMock()
        mock_scheduler.get_metrics_summary.side_effect = Exception("Metrics error")
        mock_scheduler_api._ensure_scheduler.return_value = mock_scheduler

        # Override the dependency
        from paidsearchnav.api.dependencies import get_scheduler_api

        app.dependency_overrides[get_scheduler_api] = lambda: mock_scheduler_api

        try:
            # Make request
            response = self.client.get("/api/v1/scheduler/metrics")

            # Expect 500 error when metrics collection fails
            assert response.status_code == 500
            data = response.json()
            assert "Failed to get scheduler metrics" in data["detail"]
        finally:
            # Clean up dependency override
            app.dependency_overrides.clear()

    @pytest.mark.skip(reason="Requires full app setup with repository dependency")
    def test_existing_health_endpoint_still_works(self):
        """Test that existing health endpoint still works."""
        # Make request to existing health endpoint
        response = self.client.get("/api/v1/health")

        # Should return successful response (though may show degraded status in test)
        assert response.status_code == 200
        data = response.json()

        assert "status" in data
        assert "version" in data
        assert "timestamp" in data
        assert "services" in data

    @pytest.mark.skip(reason="Requires full app setup with repository dependency")
    def test_readiness_endpoint_still_works(self):
        """Test that readiness endpoint still works."""
        # Make request to readiness endpoint
        response = self.client.get("/api/v1/ready")

        # Should return successful response (may show not_ready in test environment)
        assert response.status_code == 200
        data = response.json()

        assert "status" in data


@pytest.mark.asyncio
class TestSchedulerHealthIntegration:
    """Integration tests for scheduler health endpoints."""

    async def test_health_check_integration_with_real_settings(self):
        """Test health check with realistic settings configuration."""
        from paidsearchnav.core.config import Settings
        from paidsearchnav.scheduler.monitoring import HealthChecker

        # Create real settings object
        settings = Settings()
        health_checker = HealthChecker(settings)

        # Test system metrics (should work in any environment)
        system_metrics = health_checker.get_system_metrics()

        assert isinstance(system_metrics, dict)
        assert "memory_bytes" in system_metrics
        assert "cpu_percentage" in system_metrics
        assert isinstance(system_metrics["memory_bytes"], float)
        assert isinstance(system_metrics["cpu_percentage"], float)

    async def test_google_ads_api_check_with_missing_config(self):
        """Test Google Ads API check with missing configuration."""
        from paidsearchnav.scheduler.monitoring import HealthChecker

        # Create health checker with no settings
        health_checker = HealthChecker()

        # Should return False for missing config
        result = await health_checker.check_google_ads_api()
        assert result is False

    def test_scheduler_status_check_with_mock_scheduler(self):
        """Test scheduler status check with mock scheduler."""
        from paidsearchnav.scheduler.monitoring import HealthChecker

        health_checker = HealthChecker()

        # Test with None scheduler
        mock_scheduler = MagicMock()
        mock_scheduler._scheduler = None

        result = health_checker.check_scheduler_status(mock_scheduler)
        assert result is False

        # Test with running scheduler
        mock_scheduler._scheduler = MagicMock()
        mock_scheduler._scheduler.running = True

        result = health_checker.check_scheduler_status(mock_scheduler)
        assert result is True


class TestSchedulerHealthEndpointIntegration:
    """Integration tests for actual endpoint behavior."""

    def setup_method(self):
        """Set up test client."""
        self.client = TestClient(app)

    def test_scheduler_health_endpoint_accessibility(self):
        """Test that scheduler health endpoints are accessible."""
        # Test health endpoint
        health_response = self.client.get("/api/v1/scheduler/health")
        assert health_response.status_code in [
            200,
            500,
        ]  # Either works or fails gracefully

        # Test metrics endpoint
        metrics_response = self.client.get("/api/v1/scheduler/metrics")
        assert metrics_response.status_code in [
            200,
            500,
        ]  # Either works or fails gracefully

    def test_endpoint_response_format(self):
        """Test that endpoints return properly formatted JSON."""
        # Test health endpoint response format
        health_response = self.client.get("/api/v1/scheduler/health")

        if health_response.status_code == 200:
            data = health_response.json()
            assert isinstance(data, dict)
            assert "status" in data or "scheduler" in data

        # Test metrics endpoint response format
        metrics_response = self.client.get("/api/v1/scheduler/metrics")

        if metrics_response.status_code == 200:
            data = metrics_response.json()
            assert isinstance(data, dict)
            assert "timestamp" in data or "scheduler" in data
