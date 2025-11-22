"""Minimal integration test for backend completion verification."""

import os
import unittest.mock

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import create_app
from paidsearchnav_mcp.core.config import Settings


@pytest.fixture
def app_with_google_ads():
    """Create app with Google Ads configuration."""
    # Create mock Google Ads config for test
    from pydantic import SecretStr

    from paidsearchnav.api.dependencies import get_settings
    from paidsearchnav.core.config import GoogleAdsConfig

    # Create settings with Google Ads config
    settings = Settings.from_env()
    settings.google_ads = GoogleAdsConfig(
        developer_token=SecretStr("test-developer-token"),
        client_id="test-client-id.apps.googleusercontent.com",
        client_secret=SecretStr("test-client-secret"),
    )

    app = create_app(settings)

    # Override the settings dependency to return our test settings
    app.dependency_overrides[get_settings] = lambda: settings

    # Mock the repository for testing
    mock_repo = unittest.mock.AsyncMock()
    mock_repo.check_connection.return_value = True
    app.state.repository = mock_repo

    return app


@pytest.fixture
def client(app_with_google_ads):
    """Create test client."""
    return TestClient(app_with_google_ads)


class TestMinimalIntegration:
    """Test minimal integration flow for backend completion."""

    def test_health_check_google_ads_configured(self, client):
        """Verify Google Ads API is configured in health check."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        health_data = response.json()
        assert "services" in health_data
        assert "google_ads" in health_data["services"]

        # Should be True when Google Ads is configured
        assert health_data["services"]["google_ads"] is True

    def test_oauth2_init_returns_auth_url(self, client):
        """Test OAuth2 init endpoint returns auth URL."""
        response = client.post(
            "/api/v1/auth/google/init",
            json={"redirect_uri": "http://localhost:5173/auth/callback"},
        )
        assert response.status_code == 200

        auth_data = response.json()
        assert "auth_url" in auth_data
        assert "accounts.google.com/o/oauth2/v2/auth" in auth_data["auth_url"]

    def test_oauth2_callback_response_schema(self, client):
        """Test OAuth2 callback response has correct schema structure."""
        # This test verifies the response schema is properly defined
        # We'll test with invalid input to get schema validation errors

        response = client.post(
            "/api/v1/auth/google/callback",
            json={
                "code": "invalid-code",
                "redirect_uri": "http://localhost:5173/auth/callback",
            },
        )

        # Should fail due to invalid Google OAuth code, but should return proper error format
        assert response.status_code == 400
        error_data = response.json()
        assert "detail" in error_data

        # Test that the endpoint expects the right input format
        response = client.post(
            "/api/v1/auth/google/callback",
            json={},  # Missing required fields
        )

        assert response.status_code == 422  # Validation error
        validation_error = response.json()
        assert "detail" in validation_error

    def test_audit_creation_with_customer_id(self, client):
        """Test audit creation with customer ID."""
        # First, create a mock authentication token
        from datetime import datetime, timedelta

        from jose import jwt

        payload = {
            "sub": "test-user-123",
            "email": "test@example.com",
            "name": "Test User",
            "customer_ids": ["1234567890"],
            "exp": datetime.utcnow() + timedelta(hours=1),
        }

        # Use the same secret key that the app uses
        token = jwt.encode(payload, "change-me-in-production", algorithm="HS256")

        # Mock repository methods by overriding the app's existing mock

        # Get the existing mock repository from the app
        mock_repo = client.app.state.repository
        mock_repo.user_has_customer_access = unittest.mock.AsyncMock(return_value=True)
        mock_repo.create_audit = unittest.mock.AsyncMock(return_value="audit-123")
        mock_repo.get_audit = unittest.mock.AsyncMock(
            return_value={
                "id": "audit-123",
                "customer_id": "1234567890",
                "name": "Test Audit",
                "status": "pending",
                "progress": 0,
                "created_at": datetime.utcnow(),
                "analyzers": ["keyword_match"],
                "results_summary": None,
                "error": None,
            }
        )

        response = client.post(
            "/api/v1/audits",
            json={
                "customer_id": "1234567890",
                "name": "Test Audit",
                "analyzers": ["keyword_match"],
            },
            headers={"Authorization": f"Bearer {token}"},
        )

        assert response.status_code == 201
        audit_data = response.json()

        assert audit_data["id"] == "audit-123"
        assert audit_data["customer_id"] == "1234567890"
        assert audit_data["status"] in ["pending", "running"]
        assert "analyzers" in audit_data

    def test_api_endpoints_accessibility(self, client):
        """Test that all major API endpoints are accessible."""
        # Test root endpoint
        response = client.get("/")
        assert response.status_code == 200

        # Test health endpoint
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        # Test ready endpoint
        response = client.get("/api/v1/ready")
        assert response.status_code == 200

        # Test OpenAPI docs
        response = client.get("/docs")
        assert response.status_code == 200

        # Test OpenAPI spec
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        assert "paths" in spec
        assert len(spec["paths"]) >= 20  # Should have at least 20 endpoints

    def test_all_required_endpoints_present(self, client):
        """Verify all required endpoints are present in OpenAPI spec."""
        response = client.get("/openapi.json")
        assert response.status_code == 200

        spec = response.json()
        paths = spec["paths"]

        # Required endpoints
        required_endpoints = [
            "/api/v1/health",
            "/api/v1/auth/google/init",
            "/api/v1/auth/google/callback",
            "/api/v1/auth/revoke",
            "/api/v1/customers",
            "/api/v1/customers/{customer_id}",
            "/api/v1/audits",
            "/api/v1/audits/{audit_id}",
            "/api/v1/results/{audit_id}",
            "/api/v1/results/{audit_id}/{analyzer}",
            "/api/v1/dashboard/{audit_id}",
            "/api/v1/schedules",
            "/api/v1/schedules/{schedule_id}",
            "/api/v1/reports/{audit_id}/generate",
            "/api/v1/reports/{audit_id}/download",
            "/api/v1/events",
        ]

        for endpoint in required_endpoints:
            assert endpoint in paths, f"Missing required endpoint: {endpoint}"

    def test_error_handling(self, client):
        """Test error handling for various scenarios."""
        # Test auth required for protected endpoints
        response = client.get("/api/v1/audits/non-existent")
        # Should require auth first (might be 401 or 403 depending on middleware order)
        assert response.status_code in [401, 403]

        # Test 401 for missing auth on customers endpoint
        response = client.get("/api/v1/customers")
        assert response.status_code in [401, 403]

    def test_cors_and_security_headers(self, client):
        """Test CORS and security headers are present."""
        response = client.get("/api/v1/health")
        assert response.status_code == 200

        # Check security headers are present (from SecurityHeadersMiddleware)
        headers = response.headers
        expected_security_headers = [
            "x-content-type-options",
            "x-frame-options",
            "x-xss-protection",
            "strict-transport-security",
            "referrer-policy",
            "x-process-time",  # From TimingMiddleware (actual header name)
        ]

        for header in expected_security_headers:
            assert header in headers, f"Missing security header: {header}"


@pytest.mark.skipif(
    not os.getenv("PSN_GOOGLE_ADS_DEVELOPER_TOKEN"),
    reason="Google Ads API credentials not configured",
)
class TestRealGoogleAdsIntegration:
    """Integration tests that require real Google Ads API credentials."""

    def test_health_check_with_real_config(self):
        """Test health check with real Google Ads configuration."""
        settings = Settings.from_env()
        app = create_app(settings)

        # Mock the repository for testing to prevent actual DB connection
        mock_repo = unittest.mock.AsyncMock()
        mock_repo.check_connection.return_value = True
        app.state.repository = mock_repo

        client = TestClient(app)

        response = client.get("/api/v1/health")
        assert response.status_code == 200

        health_data = response.json()
        assert health_data["services"]["google_ads"] is True
        assert health_data["status"] == "healthy"
