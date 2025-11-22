"""Tests for premium BigQuery-powered API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from fastapi.testclient import TestClient

from paidsearchnav_mcp.api.main import app
from paidsearchnav_mcp.core.config import BigQueryTier


@pytest.fixture
def client():
    """Test client."""
    return TestClient(app)


@pytest.fixture
def mock_user():
    """Mock authenticated user."""
    return {
        "sub": "test_user",
        "customer_id": "test_customer_123",
        "email": "test@example.com",
    }


@pytest.fixture
def mock_premium_settings():
    """Mock settings with premium BigQuery tier."""
    settings = MagicMock()
    settings.bigquery.enabled = True
    settings.bigquery.tier = BigQueryTier.PREMIUM
    settings.bigquery.project_id = "test-project"
    settings.bigquery.dataset_id = "test_dataset"
    settings.bigquery.query_timeout_seconds = 300
    settings.bigquery.daily_cost_limit_usd = 100.0
    return settings


@pytest.fixture
def mock_enterprise_settings():
    """Mock settings with enterprise BigQuery tier."""
    settings = MagicMock()
    settings.bigquery.enabled = True
    settings.bigquery.tier = BigQueryTier.ENTERPRISE
    settings.bigquery.project_id = "test-project"
    settings.bigquery.dataset_id = "test_dataset"
    settings.bigquery.query_timeout_seconds = 300
    settings.bigquery.daily_cost_limit_usd = 500.0
    return settings


@pytest.fixture
def mock_disabled_settings():
    """Mock settings with disabled BigQuery."""
    settings = MagicMock()
    settings.bigquery.enabled = False
    settings.bigquery.tier = BigQueryTier.DISABLED
    return settings


@pytest.fixture
def mock_bigquery_client():
    """Mock BigQuery client with sample data."""
    client = AsyncMock()

    # Mock query results
    mock_dataframe = MagicMock()
    mock_dataframe.empty = False
    mock_dataframe.to_dict.return_value = [
        {
            "search_term": "test keyword",
            "campaign_id": "123456789",
            "campaign_name": "Test Campaign",
            "impressions": 1000,
            "clicks": 50,
            "cost": 25.50,
            "conversions": 2,
            "ctr": 5.0,
            "analysis_timestamp": datetime.now(timezone.utc).isoformat(),
        }
    ]

    mock_query_job = MagicMock()
    mock_query_job.to_dataframe.return_value = mock_dataframe
    mock_query_job.total_bytes_processed = 1024 * 1024  # 1MB
    mock_query_job.cache_hit = False

    client.query.return_value = mock_query_job

    return client


class TestPremiumAnalyticsEndpoints:
    """Test premium analytics endpoints."""

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_search_terms_analytics_success(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test successful search terms analytics request."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={
                "customer_id": "test_customer_123",
                "date_range": "30d",
                "limit": 100,
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "data" in data
        assert "metadata" in data
        assert "query_info" in data
        assert data["metadata"]["customer_id"] == "test_customer_123"

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_analytics_requires_premium_tier(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_disabled_settings,
    ):
        """Test that analytics endpoints require premium tier."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_disabled_settings

        mock_service = MagicMock()
        mock_service.is_premium = False
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 402
        assert "Premium tier required" in response.json()["detail"]

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_keywords_analytics_with_filters(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test keywords analytics with filters."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/keywords",
            params={
                "customer_id": "test_customer_123",
                "match_type": "EXACT",
                "min_impressions": 100,
                "limit": 50,
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["metadata"]["filters"]["match_type"] == "EXACT"
        assert data["metadata"]["filters"]["min_impressions"] == 100

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_campaigns_analytics_success(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test campaigns analytics endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/campaigns",
            params={
                "customer_id": "test_customer_123",
                "campaign_type": "SEARCH",
                "min_cost": 10.0,
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["filters"]["campaign_type"] == "SEARCH"
        assert data["metadata"]["filters"]["min_cost"] == 10.0


class TestLivePerformanceEndpoints:
    """Test live performance monitoring endpoints."""

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_live_performance_dashboard(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test live performance dashboard endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        # Mock performance data
        mock_dataframe = MagicMock()
        mock_dataframe.empty = False
        mock_dataframe.iloc = [MagicMock()]
        mock_dataframe.iloc[0].to_dict.return_value = {
            "impressions_24h": 5000,
            "clicks_24h": 250,
            "cost_24h": 125.50,
            "conversions_24h": 10,
            "conversion_value_24h": 500.0,
            "avg_ctr_24h": 5.0,
            "avg_cpc_24h": 0.50,
            "active_campaigns": 5,
        }

        mock_query_job = MagicMock()
        mock_query_job.to_dataframe.return_value = mock_dataframe
        mock_bigquery_client.query.return_value = mock_query_job

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/live/performance",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "performance_data" in data
        assert "alerts" in data
        assert "recommendations" in data
        assert "last_updated" in data

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_live_alerts(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test live alerts endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/live/alerts",
            params={"customer_id": "test_customer_123", "severity": "high"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "alerts" in data
        assert "total_alerts" in data
        assert data["customer_id"] == "test_customer_123"

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_live_cost_monitoring(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test live cost monitoring endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        # Mock cost data
        mock_dataframe = MagicMock()
        mock_dataframe.empty = False
        mock_dataframe.iloc = [MagicMock()]
        mock_dataframe.iloc[0].to_dict.return_value = {
            "spend_today": 150.75,
            "spend_yesterday": 142.30,
            "avg_daily_spend_7d": 135.50,
            "active_campaigns": 8,
        }

        mock_query_job = MagicMock()
        mock_query_job.to_dataframe.return_value = mock_dataframe
        mock_bigquery_client.query.return_value = mock_query_job

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/live/costs",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "cost_summary" in data
        assert "budget_status" in data
        assert data["cost_summary"]["spend_today"] == 150.75


class TestPremiumRecommendations:
    """Test premium recommendations endpoints."""

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_automated_recommendations(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test automated recommendations endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/recommendations",
            params={
                "customer_id": "test_customer_123",
                "recommendation_type": "negative_keyword",
                "priority": "high",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["filters"]["recommendation_type"] == "negative_keyword"
        assert data["metadata"]["filters"]["priority"] == "high"

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_live_optimization_suggestions(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test live optimization suggestions endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/live/recommendations",
            params={"customer_id": "test_customer_123", "limit": 5},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "recommendations" in data
        assert "total_available" in data
        assert "generated_at" in data
        assert "next_refresh" in data
        assert len(data["recommendations"]) <= 5


class TestTrendsAndAnomalies:
    """Test trends and anomaly detection endpoints."""

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_performance_trends(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test performance trends endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/trends",
            params={
                "customer_id": "test_customer_123",
                "metric": "cost",
                "granularity": "daily",
                "date_range": "7d",
            },
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["metadata"]["metric"] == "cost"
        assert data["metadata"]["granularity"] == "daily"

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_anomaly_detection(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test anomaly detection endpoint."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/live/anomalies",
            params={"customer_id": "test_customer_123", "sensitivity": "high"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "anomalies" in data
        assert "total_detected" in data
        assert "sensitivity" in data
        assert data["sensitivity"] == "high"


class TestErrorHandling:
    """Test error handling and edge cases."""

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_bigquery_query_failure(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
    ):
        """Test handling of BigQuery query failures."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        # Mock service that raises exception
        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_client = AsyncMock()
        mock_client.query.side_effect = Exception("BigQuery connection failed")
        mock_service.authenticator.get_client = AsyncMock(return_value=mock_client)
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 500
        assert "Analytics query failed" in response.json()["detail"]

    def test_invalid_customer_id(self, client):
        """Test validation of customer ID parameter."""
        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={"customer_id": "invalid-chars!@#"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 422  # Validation error

    def test_missing_authentication(self, client):
        """Test that endpoints require authentication."""
        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={"customer_id": "test_customer_123"},
        )

        # Should return 401 or 403 for missing auth
        assert response.status_code in [401, 403]


class TestQueryOptimization:
    """Test query optimization and performance features."""

    def test_date_range_parsing(self):
        """Test date range parsing function."""
        from paidsearchnav.api.v1.premium import parse_date_range

        assert parse_date_range("30d") == "30 DAY"
        assert parse_date_range("2w") == "14 DAY"
        assert parse_date_range("3m") == "90 DAY"
        assert parse_date_range("7") == "7 DAY"

    @patch("paidsearchnav.api.v1.premium.get_current_user")
    @patch("paidsearchnav.api.v1.premium.get_settings")
    @patch("paidsearchnav.api.v1.premium.get_bigquery_service")
    def test_query_cost_tracking(
        self,
        mock_get_service,
        mock_get_settings,
        mock_get_user,
        client,
        mock_user,
        mock_premium_settings,
        mock_bigquery_client,
    ):
        """Test that query costs are tracked and reported."""
        mock_get_user.return_value = mock_user
        mock_get_settings.return_value = mock_premium_settings

        # Mock query job with cost info
        mock_query_job = MagicMock()
        mock_query_job.to_dataframe.return_value = MagicMock()
        mock_query_job.to_dataframe.return_value.empty = False
        mock_query_job.to_dataframe.return_value.to_dict.return_value = []
        mock_query_job.total_bytes_processed = 1024 * 1024 * 1024  # 1GB
        mock_query_job.cache_hit = False
        mock_bigquery_client.query.return_value = mock_query_job

        mock_service = MagicMock()
        mock_service.is_premium = True
        mock_service.authenticator.get_client = AsyncMock(
            return_value=mock_bigquery_client
        )
        mock_service.config = mock_premium_settings.bigquery
        mock_get_service.return_value = mock_service

        response = client.get(
            "/api/v1/premium/analytics/search-terms",
            params={"customer_id": "test_customer_123"},
            headers={"Authorization": "Bearer test_token"},
        )

        assert response.status_code == 200
        data = response.json()
        assert "query_info" in data
        assert "bytes_processed" in data["query_info"]
        assert "cost_estimate_usd" in data["query_info"]
        assert data["query_info"]["bytes_processed"] == 1024 * 1024 * 1024
