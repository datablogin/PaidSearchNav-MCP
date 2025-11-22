"""Tests for dashboard endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


class TestDashboardEndpoints:
    """Test dashboard API endpoints."""

    @pytest.mark.asyncio
    async def test_get_dashboard_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful dashboard data retrieval."""
        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify dashboard structure
        assert "audit" in data
        assert data["audit"]["id"] == "test-audit-123"

        assert "summary" in data
        summary = data["summary"]
        assert "total_keywords" in summary
        assert "total_spend" in summary
        assert "wasted_spend" in summary
        assert "potential_savings_percent" in summary
        assert "critical_issues" in summary
        assert "total_recommendations" in summary

        assert "kpis" in data
        kpis = data["kpis"]
        assert "avg_cpc" in kpis
        assert "avg_ctr" in kpis
        assert "avg_conversion_rate" in kpis
        assert "avg_cpa" in kpis
        assert "roas" in kpis

        assert "geographic_performance" in data
        geo_perf = data["geographic_performance"]
        assert "top_performing_locations" in geo_perf
        assert "underperforming_locations" in geo_perf
        assert "distance_performance" in geo_perf

        assert "keyword_insights" in data
        keyword_insights = data["keyword_insights"]
        assert "match_type_distribution" in keyword_insights
        assert "negative_conflicts" in keyword_insights
        assert "low_quality_score" in keyword_insights
        assert "zero_conversions" in keyword_insights
        assert "near_me_opportunities" in keyword_insights

        assert "pmax_insights" in data
        pmax = data["pmax_insights"]
        assert "search_overlap_percent" in pmax
        assert "irrelevant_queries" in pmax
        assert "channel_distribution" in pmax

        assert "recommendations_summary" in data
        recs = data["recommendations_summary"]
        assert "high_priority" in recs
        assert "medium_priority" in recs
        assert "low_priority" in recs
        assert "top_recommendations" in recs

    @pytest.mark.asyncio
    async def test_get_dashboard_no_auth(self, async_client: AsyncClient):
        """Test dashboard access without authentication."""
        response = await async_client.get("/api/v1/dashboard/test-audit-123")

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_dashboard_audit_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test dashboard for non-existent audit."""
        mock_repository.get_audit.return_value = None

        response = await async_client.get(
            "/api/v1/dashboard/non-existent-audit", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Audit" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_dashboard_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test dashboard access for audit from different customer."""
        # Mock audit belongs to different customer
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "different-customer-456",
            "name": "Test Audit",
            "status": "completed",
        }

        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_dashboard_running_audit(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test dashboard for running audit with partial data."""
        # Mock a running audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "name": "Test Audit",
            "status": "running",
            "progress": 45,
            "created_at": "2024-01-01T00:00:00",
            "started_at": "2024-01-01T00:01:00",
            "completed_at": None,
            "analyzers": ["keyword_match", "search_terms"],
        }

        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["audit"]["status"] == "running"
        assert data["audit"]["completed_at"] is None

        # Dashboard should still return data structure even for running audit
        assert "summary" in data
        assert "kpis" in data
        assert "geographic_performance" in data

    @pytest.mark.asyncio
    async def test_get_dashboard_failed_audit(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test dashboard for failed audit."""
        # Mock a failed audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "name": "Test Audit",
            "status": "failed",
            "created_at": datetime.utcnow(),
            "error": "Failed to connect to Google Ads API",
        }

        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["audit"]["status"] == "failed"

        # Dashboard should handle failed audits gracefully
        assert "summary" in data
        assert data["summary"]["critical_issues"] == 0
        assert data["summary"]["total_recommendations"] == 0

    @pytest.mark.asyncio
    async def test_get_dashboard_error_handling(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test dashboard error handling."""
        mock_repository.get_audit.side_effect = Exception("Database error")

        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 500
        assert "Failed to get dashboard data" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_dashboard_top_recommendations(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test dashboard top recommendations structure."""
        response = await async_client.get(
            "/api/v1/dashboard/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify top recommendations structure
        top_recs = data["recommendations_summary"]["top_recommendations"]
        assert len(top_recs) > 0

        rec = top_recs[0]
        assert "type" in rec
        assert "description" in rec
        assert "impact" in rec
        assert "estimated_savings" in rec

        # Verify recommendation types (should match what the repository returns)
        rec_types = [r["type"] for r in top_recs]
        assert any(t in ["optimization", "cost_reduction"] for t in rec_types)
