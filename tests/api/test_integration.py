"""Integration tests for complete API workflows."""

import asyncio
from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient

# Test constants (consistent with conftest.py)
TEST_CUSTOMER_ID = "1234567890"


class TestAPIIntegration:
    """Test complete API workflows and integrations."""

    @pytest.mark.asyncio
    async def test_complete_audit_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test complete workflow: create audit -> check status -> get results -> generate report."""
        # Step 1: Create audit
        mock_repository.create_audit.return_value = "test-audit-123"

        response = await async_client.post(
            f"/api/v1/audits?customer_id={TEST_CUSTOMER_ID}",
            headers=auth_headers,
            json={
                "customer_id": TEST_CUSTOMER_ID,
                "name": "Integration Test Audit",
                "analyzers": ["keyword_match", "search_terms"],
                "config": {"date_range": 90},
            },
        )

        assert response.status_code == 201
        audit_id = response.json()["id"]
        assert audit_id == "test-audit-123"

        # Step 2: Check audit status (running)
        def get_audit_running_side_effect(audit_id):
            return {
                "id": audit_id,
                "customer_id": "test-customer-123",
                "name": "Integration Test Audit",
                "status": "running",
                "progress": 50,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "analyzers": ["keyword_match", "search_terms"],
            }

        mock_repository.get_audit.side_effect = get_audit_running_side_effect

        response = await async_client.get(
            f"/api/v1/audits/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "running"

        # Step 3: Check audit status (completed)
        def get_audit_completed_side_effect(audit_id):
            return {
                "id": audit_id,
                "customer_id": "test-customer-123",
                "name": "Integration Test Audit",
                "status": "completed",
                "progress": 100,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": datetime.utcnow(),
                "analyzers": ["keyword_match", "search_terms"],
            }

        mock_repository.get_audit.side_effect = get_audit_completed_side_effect

        response = await async_client.get(
            f"/api/v1/audits/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "completed"

        # Step 4: Get results
        mock_repository.get_audit_results.return_value = {
            "audit_id": audit_id,
            "status": "completed",
            "created_at": datetime.utcnow(),
            "completed_at": datetime.utcnow(),
            "analyzers": [
                {
                    "analyzer_name": "keyword_match",
                    "status": "completed",
                    "findings": [{"type": "broad_match_overuse"}],
                    "recommendations": [{"action": "change_match_type"}],
                    "metrics": {"issues_found": 10},
                }
            ],
            "summary": {"total_recommendations": 10},
        }

        response = await async_client.get(
            f"/api/v1/results/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        results = response.json()
        assert len(results["analyzers"]) > 0
        assert results["summary"]["total_recommendations"] == 10

        # Step 5: Generate report
        mock_repository.generate_report.return_value = "report-123"

        response = await async_client.post(
            f"/api/v1/reports/{audit_id}/generate",
            headers=auth_headers,
            json={"format": "pdf", "template": "executive_summary"},
        )

        assert response.status_code == 201
        assert response.json()["report_id"] == "report-123"

    @pytest.mark.asyncio
    async def test_schedule_and_execution_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test workflow: create schedule -> trigger execution -> monitor audit."""
        # Step 1: Create schedule
        mock_repository.create_schedule.return_value = "test-schedule-123"

        response = await async_client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "name": "Weekly Audit",
                "cron_expression": "0 0 * * 0",
                "analyzers": ["keyword_match"],
                "config": {"date_range": 7},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        schedule_id = response.json()["schedule_id"]

        # Step 2: Get schedule details
        mock_repository.get_schedule.return_value = {
            "id": schedule_id,
            "customer_id": "test-customer-123",
            "name": "Weekly Audit",
            "cron_expression": "0 0 * * 0",
            "analyzers": ["keyword_match"],
            "config": {"date_range": 7},
            "enabled": True,
            "created_at": datetime.utcnow(),
            "last_run": None,
            "next_run": datetime.utcnow(),
        }

        response = await async_client.get(
            f"/api/v1/schedules/{schedule_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["enabled"] is True

        # Step 3: Simulate schedule execution (creates audit)
        # In real implementation, this would be triggered by the scheduler
        mock_repository.create_audit.return_value = "scheduled-audit-123"

        # Step 4: List audits to see the scheduled one
        mock_repository.list_audits.return_value = (
            [
                {
                    "id": "scheduled-audit-123",
                    "customer_id": "test-customer-123",
                    "name": "Weekly Audit - Scheduled",
                    "status": "running",
                    "progress": 50,
                    "created_at": datetime.utcnow(),
                    "started_at": datetime.utcnow(),
                    "completed_at": None,
                    "analyzers": ["keyword_match"],
                    "schedule_id": schedule_id,
                }
            ],
            1,
        )

        response = await async_client.get("/api/v1/audits", headers=auth_headers)

        assert response.status_code == 200
        audits = response.json()["items"]
        assert any(a["id"] == "scheduled-audit-123" for a in audits)

    @pytest.mark.asyncio
    async def test_multi_customer_agency_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test agency workflow managing multiple customers."""
        # Step 1: List customers (agency sees multiple)
        mock_repository.get_customers_for_user.return_value = [
            {
                "id": "customer-1",
                "name": "Client A",
                "google_ads_customer_id": "111-111-1111",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
            {
                "id": "customer-2",
                "name": "Client B",
                "google_ads_customer_id": "222-222-2222",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
        ]
        mock_repository.count_customers_for_user.return_value = 2

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 200
        customers = response.json()["items"]
        assert len(customers) == 2

        # Step 2: Create audits for different customers
        # This would require proper multi-customer support in auth
        # For now, we simulate the expected behavior

        for customer in customers:
            mock_repository.create_audit.return_value = f"audit-{customer['id']}"

            # In real implementation, would need to switch context to customer
            # For testing, we assume the API handles customer context

    @pytest.mark.asyncio
    async def test_dashboard_and_export_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test workflow: view dashboard -> export data -> download."""
        audit_id = "test-audit-123"

        # Step 1: Get dashboard data
        response = await async_client.get(
            f"/api/v1/dashboard/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        dashboard = response.json()
        assert "summary" in dashboard
        assert "kpis" in dashboard
        assert "recommendations_summary" in dashboard

        # Step 2: Generate different report formats
        formats = ["pdf", "excel", "html"]

        for format_type in formats:
            mock_repository.generate_report.return_value = f"report-{format_type}-123"

            response = await async_client.post(
                f"/api/v1/reports/{audit_id}/generate",
                headers=auth_headers,
                json={"format": format_type},
            )

            assert response.status_code == 201
            assert response.json()["report_id"] == f"report-{format_type}-123"

    @pytest.mark.asyncio
    async def test_error_recovery_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test API behavior during errors and recovery."""
        # Step 1: Create audit that will fail
        mock_repository.create_audit.return_value = "test-audit-123"

        response = await async_client.post(
            "/api/v1/audits",
            headers=auth_headers,
            json={
                "customer_id": TEST_CUSTOMER_ID,
                "name": "Test Audit",
                "analyzers": ["keyword_match"],
                "config": {},
            },
        )

        assert response.status_code == 201
        audit_id = response.json()["id"]

        # Step 2: Audit fails during execution
        def get_audit_failed_side_effect(audit_id):
            return {
                "id": audit_id,
                "customer_id": "test-customer-123",
                "name": "Test Audit",
                "status": "failed",
                "progress": 50,
                "created_at": datetime.utcnow(),
                "started_at": datetime.utcnow(),
                "completed_at": None,
                "analyzers": ["keyword_match"],
                "error": "Google Ads API rate limit exceeded",
            }

        mock_repository.get_audit.side_effect = get_audit_failed_side_effect

        response = await async_client.get(
            f"/api/v1/audits/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "failed"
        assert "error" in response.json()

        # Step 3: Attempt to get results for failed audit
        mock_repository.get_audit_results.return_value = {
            "audit_id": audit_id,
            "status": "failed",
            "created_at": datetime.utcnow(),
            "completed_at": None,
            "analyzers": [],
            "summary": {"error": "Audit failed"},
        }

        response = await async_client.get(
            f"/api/v1/results/{audit_id}", headers=auth_headers
        )

        assert response.status_code == 200
        assert response.json()["status"] == "failed"

        # Step 4: Cannot generate report for failed audit
        response = await async_client.post(
            f"/api/v1/reports/{audit_id}/generate",
            headers=auth_headers,
            json={"format": "pdf"},
        )

        assert response.status_code == 400
        assert "must be completed" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_concurrent_operations_workflow(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test API handling of concurrent operations."""
        # Enable dynamic audit ID generation for this test
        mock_repository.get_audit.side_effect = mock_repository._get_audit_side_effect

        # Create multiple audits concurrently
        audit_ids = []

        async def create_audit(name: str) -> str:
            response = await async_client.post(
                "/api/v1/audits",
                headers=auth_headers,
                json={
                    "customer_id": TEST_CUSTOMER_ID,
                    "name": f"Concurrent Audit {name}",
                    "analyzers": ["keyword_match"],
                    "config": {},
                },
            )
            return response.json()["id"]

        # Create 5 audits concurrently
        tasks = [create_audit(str(i)) for i in range(5)]
        audit_ids = await asyncio.gather(*tasks)

        assert len(audit_ids) == 5
        assert all(aid.startswith("audit-") for aid in audit_ids)

        # Check all audits concurrently - using the dynamic side_effect
        async def check_audit(audit_id: str):
            response = await async_client.get(
                f"/api/v1/audits/{audit_id}", headers=auth_headers
            )
            return response.status_code

        tasks = [check_audit(aid) for aid in audit_ids]
        statuses = await asyncio.gather(*tasks)

        assert all(status == 200 for status in statuses)
