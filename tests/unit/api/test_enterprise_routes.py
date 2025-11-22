"""Tests for enterprise ML API endpoints."""

from datetime import datetime
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import FastAPI
from fastapi.testclient import TestClient

from paidsearchnav.api.routes.enterprise import router
from paidsearchnav.ml.models import (
    AnomalyDetection,
    BidRecommendation,
    CausalInsight,
    CausalMethod,
    InsightType,
    MLModelResult,
    ModelStatus,
    ModelType,
)


@pytest.fixture
def app():
    """Create test FastAPI app."""
    app = FastAPI()
    app.include_router(router)
    return app


@pytest.fixture
def client(app):
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def mock_current_user():
    """Mock current user with enterprise tier."""
    return {
        "sub": "test_user",
        "customer_id": "test_customer",
        "tier": "enterprise",
        "role": "user",
    }


@pytest.fixture
def mock_ml_service():
    """Mock ML service."""
    service = AsyncMock()
    service.is_available = True
    return service


class TestHealthEndpoints:
    """Test health and status endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_health_check_healthy(self, mock_get_service, client):
        """Test healthy ML service."""
        mock_service = AsyncMock()
        mock_service.health_check.return_value = {
            "service": "CausalML",
            "status": "healthy",
            "causal_tools_available": True,
        }
        mock_get_service.return_value = mock_service

        response = client.get("/enterprise/ml/health")

        assert response.status_code == 200
        data = response.json()
        assert data["service"] == "CausalML"
        assert data["status"] == "healthy"

    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_health_check_degraded(self, mock_get_service, client):
        """Test degraded ML service."""
        mock_service = AsyncMock()
        mock_service.health_check.return_value = {
            "service": "CausalML",
            "status": "degraded",
            "causal_tools_available": False,
        }
        mock_get_service.return_value = mock_service

        response = client.get("/enterprise/ml/health")

        assert response.status_code == 503
        data = response.json()
        assert data["status"] == "degraded"


class TestBidOptimization:
    """Test bid optimization endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_bid_predictions_success(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test successful bid predictions."""
        mock_get_user.return_value = mock_current_user

        # Mock bid recommendations
        mock_recommendation = BidRecommendation(
            keyword_id="kw1",
            keyword_text="test keyword",
            current_bid=1.0,
            recommended_bid=1.5,
            expected_effect=0.2,
            confidence_interval=[0.1, 0.3],
            p_value=0.01,
            roi_improvement=20.0,
            reasoning="Causal analysis suggests positive effect",
            method_used=CausalMethod.T_LEARNER,
            model_confidence=0.95,
        )

        mock_ml_service.generate_bid_recommendations.return_value = [
            mock_recommendation
        ]
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "keyword_data": {"test": "data"},
            "method": "t_learner",
            "target_metric": "conversion_rate",
            "max_recommendations": 10,
        }

        response = client.post("/enterprise/ml/bid-predictions", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert len(data["data"]["recommendations"]) == 1
        assert data["data"]["recommendations"][0]["keyword_id"] == "kw1"

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_bid_predictions_non_enterprise_user(
        self, mock_get_service, mock_get_user, client
    ):
        """Test bid predictions with non-enterprise user."""
        mock_get_user.return_value = {
            "sub": "test_user",
            "customer_id": "test_customer",
            "tier": "standard",  # Not enterprise
            "role": "user",
        }

        request_data = {
            "customer_id": "test_customer",
            "keyword_data": {"test": "data"},
        }

        response = client.post("/enterprise/ml/bid-predictions", json=request_data)

        assert response.status_code == 402
        assert "Enterprise tier required" in response.json()["detail"]

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_bid_predictions_access_denied(
        self, mock_get_service, mock_get_user, client, mock_ml_service
    ):
        """Test bid predictions with wrong customer access."""
        mock_get_user.return_value = {
            "sub": "test_user",
            "customer_id": "other_customer",  # Different customer
            "tier": "enterprise",
            "role": "user",
        }

        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",  # Requesting different customer
            "keyword_data": {"test": "data"},
        }

        response = client.post("/enterprise/ml/bid-predictions", json=request_data)

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]


class TestAnomalyDetection:
    """Test anomaly detection endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_anomaly_detection_success(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test successful anomaly detection."""
        mock_get_user.return_value = mock_current_user

        # Mock anomaly
        mock_anomaly = AnomalyDetection(
            anomaly_id="anom1",
            customer_id="test_customer",
            anomaly_type="conversion_rate_drop",
            severity="high",
            confidence_score=0.95,
            affected_metrics=["conversion_rate"],
            baseline_values={"conversion_rate": 0.05},
            observed_values={"conversion_rate": 0.02},
            deviation_magnitude=0.03,
            potential_causes=["Landing page issues"],
            recommended_actions=["Review landing page"],
            method_used=CausalMethod.AIPW,
            false_positive_probability=0.05,
        )

        mock_ml_service.detect_anomalies.return_value = [mock_anomaly]
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "performance_data": {"test": "data"},
            "detection_window_days": 7,
            "target_metrics": ["conversion_rate"],
            "method": "aipw",
        }

        response = client.post("/enterprise/ml/anomaly-detection", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_anomalies"] == 1
        assert data["data"]["high_priority_anomalies"] == 1


class TestInsightsGeneration:
    """Test insights generation endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_insights_generation_success(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test successful insights generation."""
        mock_get_user.return_value = mock_current_user

        # Mock insights
        mock_insight = CausalInsight(
            insight_id="insight1",
            customer_id="test_customer",
            insight_type=InsightType.POSITIVE_EFFECT,
            title="Bid Increase Shows Positive Impact",
            description="Causal analysis reveals significant positive effect",
            effect_size=0.15,
            confidence_interval=[0.05, 0.25],
            p_value=0.01,
            priority="high",
            actionable=True,
            estimated_impact=1500.0,
            method_used=CausalMethod.AIPW,
        )

        mock_ml_service.generate_causal_insights.return_value = [mock_insight]
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "analysis_data": {"test": "data"},
            "max_insights": 10,
        }

        response = client.post("/enterprise/ml/insights", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["summary"]["total"] == 1
        assert data["data"]["summary"]["actionable"] == 1


class TestModelManagement:
    """Test model training and management endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_train_custom_model_success(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test successful custom model training."""
        mock_get_user.return_value = mock_current_user

        # Mock model result
        mock_model = MLModelResult(
            model_id="model1",
            customer_id="test_customer",
            model_type=ModelType.BID_OPTIMIZATION,
            method=CausalMethod.T_LEARNER,
            status=ModelStatus.TRAINING,
            training_data_size=1000,
            feature_count=5,
            training_started=datetime.utcnow(),
        )

        mock_ml_service.train_model.return_value = mock_model
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "model_type": "bid_optimization",
            "training_data": {"test": "data"},
            "method": "t_learner",
        }

        response = client.post("/enterprise/ml/custom-models", json=request_data)

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["model_id"] == "model1"
        assert data["data"]["status"] == "training"

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_get_model_status_success(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test getting model status."""
        mock_get_user.return_value = mock_current_user

        # Mock model result
        mock_model = MLModelResult(
            model_id="model1",
            customer_id="test_customer",
            model_type=ModelType.BID_OPTIMIZATION,
            method=CausalMethod.T_LEARNER,
            status=ModelStatus.TRAINED,
            training_data_size=1000,
            feature_count=5,
            training_started=datetime.utcnow(),
        )

        mock_ml_service.get_model_status.return_value = mock_model
        mock_get_service.return_value = mock_ml_service

        response = client.get("/enterprise/ml/custom-models/model1")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["model_id"] == "model1"

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_get_model_status_not_found(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test getting status of non-existent model."""
        mock_get_user.return_value = mock_current_user

        mock_ml_service.get_model_status.return_value = None
        mock_get_service.return_value = mock_ml_service

        response = client.get("/enterprise/ml/custom-models/nonexistent")

        assert response.status_code == 404
        assert "Model not found" in response.json()["detail"]

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_list_customer_models(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test listing customer models."""
        mock_get_user.return_value = mock_current_user

        # Mock models list
        mock_models = [
            MLModelResult(
                model_id="model1",
                customer_id="test_customer",
                model_type=ModelType.BID_OPTIMIZATION,
                method=CausalMethod.T_LEARNER,
                status=ModelStatus.TRAINED,
                training_data_size=1000,
                feature_count=5,
                training_started=datetime.utcnow(),
            )
        ]

        mock_ml_service.list_customer_models.return_value = mock_models
        mock_get_service.return_value = mock_ml_service

        response = client.get("/enterprise/ml/custom-models?customer_id=test_customer")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert data["data"]["total_models"] == 1
        assert len(data["data"]["models"]) == 1


class TestUtilityEndpoints:
    """Test utility endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_clear_cache_admin(
        self, mock_get_service, mock_get_user, client, mock_ml_service
    ):
        """Test cache clearing with admin user."""
        mock_get_user.return_value = {
            "sub": "admin_user",
            "customer_id": "test_customer",
            "tier": "enterprise",
            "role": "admin",  # Admin role
        }

        mock_get_service.return_value = mock_ml_service

        response = client.delete("/enterprise/ml/cache")

        assert response.status_code == 200
        data = response.json()
        assert data["success"] is True
        assert "cache cleared" in data["message"].lower()
        mock_ml_service.clear_cache.assert_called_once()

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_clear_cache_non_admin(
        self, mock_get_service, mock_get_user, client, mock_ml_service
    ):
        """Test cache clearing with non-admin user."""
        mock_get_user.return_value = {
            "sub": "test_user",
            "customer_id": "test_customer",
            "tier": "enterprise",
            "role": "user",  # Regular user
        }

        mock_get_service.return_value = mock_ml_service

        response = client.delete("/enterprise/ml/cache")

        assert response.status_code == 403
        assert "Admin privileges required" in response.json()["detail"]


class TestErrorHandling:
    """Test error handling in endpoints."""

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_service_unavailable(
        self, mock_get_service, mock_get_user, client, mock_current_user
    ):
        """Test handling when ML service is unavailable."""
        mock_get_user.return_value = mock_current_user

        # Mock unavailable service
        mock_ml_service = AsyncMock()
        mock_ml_service.is_available = False
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "keyword_data": {"test": "data"},
        }

        response = client.post("/enterprise/ml/bid-predictions", json=request_data)

        assert response.status_code == 503
        assert "temporarily unavailable" in response.json()["detail"]

    @patch("paidsearchnav.api.routes.enterprise.get_current_user")
    @patch("paidsearchnav.api.routes.enterprise.get_causal_ml_service")
    def test_service_error(
        self,
        mock_get_service,
        mock_get_user,
        client,
        mock_current_user,
        mock_ml_service,
    ):
        """Test handling of service errors."""
        mock_get_user.return_value = mock_current_user

        # Mock service that raises exception
        mock_ml_service.generate_bid_recommendations.side_effect = Exception(
            "Service error"
        )
        mock_get_service.return_value = mock_ml_service

        request_data = {
            "customer_id": "test_customer",
            "keyword_data": {"test": "data"},
        }

        response = client.post("/enterprise/ml/bid-predictions", json=request_data)

        assert response.status_code == 500
        assert "failed" in response.json()["detail"].lower()


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
