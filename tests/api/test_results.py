"""Tests for results endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


class TestResultsEndpoints:
    """Test results API endpoints."""

    @pytest.mark.asyncio
    async def test_get_all_results_success(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        mock_repository: Mock,
        mock_analyzer_result: dict,
    ):
        """Test successful retrieval of all audit results."""
        # Mock audit data
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
            "analyzers": ["keyword_match", "search_terms", "negative_conflicts"],
        }

        # Mock results data
        mock_results = {
            "audit_id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "analyzers": [
                mock_analyzer_result,
                {
                    "analyzer_name": "search_terms",
                    "status": "completed",
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                    "findings": [
                        {
                            "type": "add_candidate",
                            "query": "running shoes near me",
                            "impressions": 1500,
                            "clicks": 125,
                            "conversions": 8,
                            "cpa": 45.50,
                        }
                    ],
                    "recommendations": [],
                    "metrics": {
                        "total_queries_analyzed": 5843,
                        "add_candidates": 156,
                        "negative_candidates": 423,
                    },
                    "error": None,
                },
            ],
            "summary": {
                "total_analyzers": 2,
                "completed": 2,
                "failed": 0,
                "total_findings": 234,
                "total_recommendations": 47,
                "estimated_savings": 8560.75,
            },
        }

        mock_repository.get_audit_results.return_value = mock_results

        response = await async_client.get(
            "/api/v1/results/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify response structure
        assert data["audit_id"] == "test-audit-123"
        assert data["status"] == "completed"
        assert len(data["analyzers"]) == 2
        assert "summary" in data

        # Verify analyzer results
        keyword_result = next(
            a for a in data["analyzers"] if a["analyzer_name"] == "keyword_match"
        )
        assert keyword_result["status"] == "completed"
        assert len(keyword_result["findings"]) > 0
        assert "metrics" in keyword_result

    @pytest.mark.asyncio
    async def test_get_all_results_no_auth(self, async_client: AsyncClient):
        """Test results access without authentication."""
        response = await async_client.get("/api/v1/results/test-audit-123")

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_all_results_audit_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test results for non-existent audit."""
        mock_repository.get_audit.return_value = None

        response = await async_client.get(
            "/api/v1/results/non-existent-audit", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Audit" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_all_results_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test results access for audit from different customer."""
        # Mock audit belongs to different customer
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "different-customer-456",
            "status": "completed",
        }

        response = await async_client.get(
            "/api/v1/results/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_all_results_running_audit(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test results for still running audit."""
        # Mock running audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "running",
            "progress": 65,
        }

        # Mock partial results
        mock_repository.get_audit_results.return_value = {
            "audit_id": "test-audit-123",
            "status": "running",
            "created_at": datetime.utcnow(),
            "analyzers": [
                {
                    "analyzer_name": "keyword_match",
                    "status": "completed",
                    "started_at": datetime.utcnow(),
                    "completed_at": datetime.utcnow(),
                    "findings": [],
                    "recommendations": [],
                    "metrics": {},
                },
                {
                    "analyzer_name": "search_terms",
                    "status": "running",
                    "started_at": datetime.utcnow(),
                    "completed_at": None,
                    "findings": [],
                    "recommendations": [],
                    "metrics": {},
                },
            ],
            "summary": {
                "total_analyzers": 3,
                "completed": 1,
                "failed": 0,
            },
        }

        response = await async_client.get(
            "/api/v1/results/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "running"
        assert data["summary"]["completed"] == 1
        assert data["summary"]["total_analyzers"] == 3

    @pytest.mark.asyncio
    async def test_get_specific_analyzer_results(
        self,
        async_client: AsyncClient,
        auth_headers: dict,
        mock_repository: Mock,
        mock_analyzer_result: dict,
    ):
        """Test retrieval of specific analyzer results."""
        # Mock audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
        }

        # Mock specific analyzer result
        mock_repository.get_analyzer_result.return_value = mock_analyzer_result

        response = await async_client.get(
            "/api/v1/results/test-audit-123/keyword_match", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()

        # Verify it's the specific analyzer result
        assert data["analyzer_name"] == "keyword_match"
        assert data["status"] == "completed"
        assert len(data["findings"]) > 0
        assert len(data["recommendations"]) > 0
        assert "metrics" in data

    @pytest.mark.asyncio
    async def test_get_specific_analyzer_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test specific analyzer results not found."""
        # Mock audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
            "analyzers": ["non_existent_analyzer"],
        }

        # Mock no result for analyzer
        mock_repository.get_analyzer_result.return_value = None

        response = await async_client.get(
            "/api/v1/results/test-audit-123/non_existent_analyzer", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Analyzer results not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_specific_analyzer_failed(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test retrieving results for failed analyzer."""
        # Mock audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
        }

        # Mock failed analyzer result
        mock_repository.get_analyzer_result.return_value = {
            "analyzer_name": "geo_performance",
            "status": "failed",
            "started_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "findings": [],
            "recommendations": [],
            "metrics": {},
            "error": "Failed to retrieve location data from Google Ads",
        }

        response = await async_client.get(
            "/api/v1/results/test-audit-123/geo_performance", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["status"] == "failed"
        assert data["error"] == "Failed to retrieve location data from Google Ads"
        assert len(data["findings"]) == 0

    @pytest.mark.asyncio
    async def test_results_caching_headers(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test that results include appropriate caching headers."""
        # Mock completed audit
        mock_repository.get_audit.return_value = {
            "id": "test-audit-123",
            "customer_id": "test-customer-123",
            "status": "completed",
        }

        mock_repository.get_audit_results.return_value = {
            "audit_id": "test-audit-123",
            "status": "completed",
            "created_at": datetime.utcnow(),
            "analyzers": [],
            "summary": {},
        }

        response = await async_client.get(
            "/api/v1/results/test-audit-123", headers=auth_headers
        )

        assert response.status_code == 200

        # For completed audits, results should be cacheable
        # Note: Actual caching headers would be set in the response
        # This is a placeholder test for when caching is implemented
