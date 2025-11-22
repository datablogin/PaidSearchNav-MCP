"""Tests for Customer Management Dashboard API endpoints."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, patch

import pytest
from fastapi import status
from fastapi.testclient import TestClient

from paidsearchnav.api.main import app
from paidsearchnav.auth.jwt_manager import jwt_manager


@pytest.fixture
def client():
    """Create test client."""
    return TestClient(app)


@pytest.fixture
def admin_token():
    """Create admin JWT token."""
    return jwt_manager.create_access_token(
        user_id="admin-user-123",
        email="admin@example.com",
        role="admin",
        scopes=["admin", "read", "write"],
    )


@pytest.fixture
def customer_token():
    """Create customer JWT token."""
    return jwt_manager.create_access_token(
        user_id="customer-user-456",
        email="customer@example.com",
        role="customer",
        scopes=["read", "write"],
    )


@pytest.fixture
def mock_repository():
    """Create mock repository."""
    with patch("paidsearchnav.api.dependencies.get_repository") as mock:
        repo = AsyncMock()
        mock.return_value = repo
        yield repo


class TestCustomerManagementAPI:
    """Test Customer Management API endpoints."""

    @pytest.mark.asyncio
    async def test_create_customer_success(self, client, admin_token, mock_repository):
        """Test successful customer creation."""
        mock_repository.create_customer.return_value = {
            "id": "customer-123",
            "name": "Test Customer",
            "email": "test@example.com",
            "google_ads_customer_id": "1234567890",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
            "settings": {},
            "is_active": True,
        }
        mock_repository.log_audit_action.return_value = None

        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "name": "Test Customer",
                "email": "test@example.com",
                "google_ads_customer_id": "1234567890",
                "settings": {},
            },
        )

        assert response.status_code == status.HTTP_201_CREATED
        data = response.json()
        assert data["name"] == "Test Customer"
        assert data["email"] == "test@example.com"
        mock_repository.create_customer.assert_called_once()
        mock_repository.log_audit_action.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_customer_forbidden(
        self, client, customer_token, mock_repository
    ):
        """Test customer creation forbidden for non-admin users."""
        response = client.post(
            "/api/v1/customers",
            headers={"Authorization": f"Bearer {customer_token}"},
            json={
                "name": "Test Customer",
                "email": "test@example.com",
            },
        )

        assert response.status_code == status.HTTP_403_FORBIDDEN

    @pytest.mark.asyncio
    async def test_update_customer_success(self, client, admin_token, mock_repository):
        """Test successful customer update."""
        mock_repository.get_customer.return_value = {
            "id": "customer-123",
            "name": "Old Name",
        }
        mock_repository.get_user_customer_access_level.return_value = "admin"
        mock_repository.update_customer.return_value = {
            "id": "customer-123",
            "name": "New Name",
            "email": "new@example.com",
            "created_at": datetime.now(timezone.utc).isoformat(),
            "updated_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_repository.log_audit_action.return_value = None

        response = client.put(
            "/api/v1/customers/customer-123",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"name": "New Name", "email": "new@example.com"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["name"] == "New Name"
        mock_repository.update_customer.assert_called_once()

    @pytest.mark.asyncio
    async def test_delete_customer_success(self, client, admin_token, mock_repository):
        """Test successful customer deletion."""
        mock_repository.get_customer.return_value = {
            "id": "customer-123",
            "name": "Test Customer",
            "user_id": "admin-user-123",
        }
        mock_repository.delete_customer.return_value = True
        mock_repository.log_audit_action.return_value = None

        response = client.delete(
            "/api/v1/customers/customer-123",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_204_NO_CONTENT
        mock_repository.delete_customer.assert_called_once_with("customer-123")

    @pytest.mark.asyncio
    async def test_get_customer_metrics(self, client, admin_token, mock_repository):
        """Test getting customer metrics."""
        mock_repository.get_customer.return_value = {"id": "customer-123"}
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_customer_metrics.return_value = {
            "total_audits": 10,
            "completed_audits": 8,
            "active_schedules": 2,
            "total_recommendations": 150,
            "potential_savings": 5000.0,
            "last_activity": datetime.now(timezone.utc).isoformat(),
            "storage_used_mb": 256.5,
            "api_calls_today": 50,
            "api_calls_month": 1200,
        }

        response = client.get(
            "/api/v1/customers/customer-123/metrics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_audits"] == 10
        assert data["potential_savings"] == 5000.0


class TestAnalysisManagementAPI:
    """Test Analysis Management API endpoints."""

    @pytest.mark.asyncio
    async def test_trigger_analysis_success(self, client, admin_token, mock_repository):
        """Test successful analysis trigger."""
        mock_repository.get_customer.return_value = {"id": "customer-123"}
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.create_audit.return_value = {"id": "audit-123"}
        mock_repository.trigger_analysis_workflow.return_value = "workflow-123"
        mock_repository.log_audit_action.return_value = None

        response = client.post(
            "/api/v1/analyses/trigger",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={
                "customer_id": "customer-123",
                "analyzers": ["keyword_analyzer", "search_term_analyzer"],
                "date_range": {"start": "2024-01-01", "end": "2024-01-31"},
                "config": {},
                "priority": "normal",
            },
        )

        assert response.status_code == status.HTTP_202_ACCEPTED
        data = response.json()
        assert data["audit_id"] == "audit-123"
        assert data["workflow_id"] == "workflow-123"
        assert data["status"] == "accepted"

    @pytest.mark.asyncio
    async def test_list_analyses(self, client, admin_token, mock_repository):
        """Test listing analyses."""
        mock_repository.list_analyses.return_value = [
            {
                "id": "analysis-1",
                "customer_id": "customer-123",
                "analysis_type": "keyword",
                "analyzer_name": "keyword_analyzer",
                "start_date": datetime.now(timezone.utc).isoformat(),
                "end_date": datetime.now(timezone.utc).isoformat(),
                "status": "completed",
                "created_at": datetime.now(timezone.utc).isoformat(),
                "total_recommendations": 25,
                "critical_issues": 3,
                "potential_cost_savings": 1500.0,
            }
        ]
        mock_repository.count_analyses.return_value = 1

        response = client.get(
            "/api/v1/analyses",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"customer_id": "customer-123", "status": "completed"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert len(data["items"]) == 1
        assert data["items"][0]["id"] == "analysis-1"

    @pytest.mark.asyncio
    async def test_get_analysis_results(self, client, admin_token, mock_repository):
        """Test getting analysis results."""
        mock_repository.get_analysis.return_value = {
            "id": "analysis-123",
            "customer_id": "customer-123",
            "analyzer_name": "keyword_analyzer",
            "status": "completed",
            "created_at": datetime.now(timezone.utc).isoformat(),
        }
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_analysis_results.return_value = {
            "result_data": {
                "recommendations": [
                    {"type": "add_negative", "keyword": "test", "priority": "high"}
                ],
                "summary": {"total_issues": 10, "cost_savings": 1000.0},
            }
        }

        response = client.get(
            "/api/v1/analyses/analysis-123/results",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["analysis_id"] == "analysis-123"
        assert len(data["recommendations"]) == 1
        assert data["summary"]["total_issues"] == 10


class TestWorkflowManagementAPI:
    """Test Workflow Management API endpoints."""

    @pytest.mark.asyncio
    async def test_list_workflows(self, client, admin_token, mock_repository):
        """Test listing workflows."""
        mock_repository.list_workflows.return_value = [
            {
                "id": "workflow-1",
                "customer_id": "customer-123",
                "workflow_type": "analysis",
                "workflow_id": "wf-123",
                "status": "running",
                "progress": 0.5,
                "current_step": "Processing keywords",
                "total_steps": 10,
                "created_at": datetime.now(timezone.utc).isoformat(),
                "updated_at": datetime.now(timezone.utc).isoformat(),
            }
        ]
        mock_repository.count_workflows.return_value = 1

        response = client.get(
            "/api/v1/workflows",
            headers={"Authorization": f"Bearer {admin_token}"},
            params={"status": "running"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total"] == 1
        assert data["items"][0]["status"] == "running"
        assert data["items"][0]["progress"] == 0.5

    @pytest.mark.asyncio
    async def test_workflow_action_cancel(self, client, admin_token, mock_repository):
        """Test cancelling a workflow."""
        mock_repository.get_workflow_status.return_value = {
            "id": "workflow-123",
            "customer_id": "customer-123",
            "status": "running",
            "workflow_type": "analysis",
        }
        mock_repository.get_user_customer_access_level.return_value = "admin"
        mock_repository.perform_workflow_action.return_value = {
            "new_status": "cancelled"
        }
        mock_repository.log_audit_action.return_value = None

        response = client.post(
            "/api/v1/workflows/workflow-123/action",
            headers={"Authorization": f"Bearer {admin_token}"},
            json={"action": "cancel", "reason": "User requested"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["action"] == "cancel"
        assert data["status"] == "cancelled"

    @pytest.mark.asyncio
    async def test_get_workflow_logs(self, client, admin_token, mock_repository):
        """Test getting workflow logs."""
        mock_repository.get_workflow_status.return_value = {
            "id": "workflow-123",
            "customer_id": "customer-123",
        }
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_workflow_logs.return_value = {
            "entries": [
                {
                    "timestamp": datetime.now(timezone.utc).isoformat(),
                    "level": "info",
                    "message": "Starting analysis",
                    "metadata": {},
                }
            ],
            "has_more": False,
        }

        response = client.get(
            "/api/v1/workflows/workflow-123/logs",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["workflow_id"] == "workflow-123"
        assert len(data["entries"]) == 1
        assert data["entries"][0]["level"] == "info"


class TestAdminDashboardAPI:
    """Test Admin Dashboard API endpoints."""

    @pytest.mark.asyncio
    async def test_get_system_health(self, client, admin_token, mock_repository):
        """Test getting system health."""
        mock_repository.get_system_health.return_value = {
            "database": {"status": "healthy", "latency_ms": 5},
            "redis": {"status": "healthy", "latency_ms": 2},
            "storage": {"status": "healthy", "available_gb": 100},
            "workflows": {"status": "healthy", "active_count": 3},
            "api": {"status": "healthy", "uptime_hours": 168},
        }

        response = client.get(
            "/api/v1/admin/health",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["status"] == "healthy"
        assert data["database"]["status"] == "healthy"

    @pytest.mark.asyncio
    async def test_get_business_metrics(self, client, admin_token, mock_repository):
        """Test getting business metrics."""
        mock_repository.get_business_metrics.return_value = {
            "total_customers": 100,
            "active_customers": 85,
            "total_users": 150,
            "active_users_30d": 120,
            "total_audits": 1000,
            "audits_this_month": 50,
            "total_analyses": 5000,
            "analyses_this_month": 250,
            "storage_used_gb": 500.5,
            "api_calls_today": 10000,
            "api_calls_month": 250000,
            "revenue_metrics": {"mrr": 50000, "arr": 600000},
            "growth_metrics": {"customer_growth": 0.15, "revenue_growth": 0.25},
        }

        response = client.get(
            "/api/v1/admin/metrics",
            headers={"Authorization": f"Bearer {admin_token}"},
        )

        assert response.status_code == status.HTTP_200_OK
        data = response.json()
        assert data["total_customers"] == 100
        assert data["revenue_metrics"]["mrr"] == 50000

    @pytest.mark.asyncio
    async def test_admin_access_required(self, client, customer_token):
        """Test that admin endpoints require admin role."""
        endpoints = [
            "/api/v1/admin/health",
            "/api/v1/admin/metrics",
            "/api/v1/admin/customers/overview",
            "/api/v1/admin/config",
            "/api/v1/admin/audit-logs",
        ]

        for endpoint in endpoints:
            response = client.get(
                endpoint,
                headers={"Authorization": f"Bearer {customer_token}"},
            )
            assert response.status_code == status.HTTP_403_FORBIDDEN
