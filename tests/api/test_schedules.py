"""Tests for schedule management endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


class TestScheduleEndpoints:
    """Test schedule API endpoints."""

    @pytest.mark.asyncio
    async def test_create_schedule_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful schedule creation."""
        mock_repository.create_schedule.return_value = "new-schedule-123"

        response = await async_client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "name": "Monthly Audit",
                "cron_expression": "0 0 1 * *",
                "analyzers": ["keyword_match", "search_terms"],
                "config": {"date_range": 90},
                "enabled": True,
            },
        )

        assert response.status_code == 201
        data = response.json()
        assert data["schedule_id"] == "new-schedule-123"
        assert data["message"] == "Schedule created successfully"

        # Verify repository was called correctly
        mock_repository.create_schedule.assert_called_once()
        call_args = mock_repository.create_schedule.call_args[1]
        assert call_args["name"] == "Monthly Audit"
        assert call_args["cron_expression"] == "0 0 1 * *"
        assert call_args["enabled"] is True

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test schedule creation with invalid cron expression."""
        response = await async_client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "name": "Invalid Schedule",
                "cron_expression": "invalid cron",
                "analyzers": ["keyword_match"],
                "config": {},
                "enabled": True,
            },
        )

        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_schedule_no_auth(self, async_client: AsyncClient):
        """Test schedule creation without authentication."""
        response = await async_client.post(
            "/api/v1/schedules",
            json={
                "name": "Test Schedule",
                "cron_expression": "0 0 * * *",
                "analyzers": ["keyword_match"],
                "config": {},
                "enabled": True,
            },
        )

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_schedule_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_schedule_data: dict
    ):
        """Test successful schedule retrieval."""
        response = await async_client.get(
            "/api/v1/schedules/test-schedule-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-schedule-123"
        assert data["name"] == "Test Schedule"
        assert data["cron_expression"] == "0 0 1 * *"
        assert data["enabled"] is True

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test getting non-existent schedule."""
        mock_repository.get_schedule.return_value = None

        response = await async_client.get(
            "/api/v1/schedules/non-existent", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Schedule" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_schedules_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful schedule listing."""
        mock_schedules = [
            {
                "id": f"schedule-{i}",
                "customer_id": "test-customer-123",
                "name": f"Schedule {i}",
                "cron_expression": "0 0 * * *",
                "analyzers": ["keyword_match", "search_terms"],
                "config": {"date_range": 90},
                "enabled": i % 2 == 0,
                "created_at": datetime.utcnow(),
                "last_run": None,
                "next_run": None,
            }
            for i in range(3)
        ]
        mock_repository.list_schedules.return_value = (mock_schedules, 3)

        response = await async_client.get("/api/v1/schedules", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3
        assert data["page"] == 1
        assert data["per_page"] == 20
        assert data["pages"] == 1

    @pytest.mark.asyncio
    async def test_update_schedule_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful schedule update."""
        mock_repository.update_schedule.return_value = True

        response = await async_client.put(
            "/api/v1/schedules/test-schedule-123",
            headers=auth_headers,
            json={
                "name": "Updated Schedule",
                "cron_expression": "0 0 * * 0",  # Weekly
                "enabled": False,
            },
        )

        assert response.status_code == 200
        assert "updated successfully" in response.json()["message"]

        # Verify repository was called with correct updates
        mock_repository.update_schedule.assert_called_once()
        call_args = mock_repository.update_schedule.call_args[0]
        assert call_args[0] == "test-schedule-123"
        updates = call_args[1]
        assert updates["name"] == "Updated Schedule"
        assert updates["cron_expression"] == "0 0 * * 0"
        assert updates["enabled"] is False

    @pytest.mark.asyncio
    async def test_update_schedule_partial(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test partial schedule update."""
        mock_repository.update_schedule.return_value = True

        response = await async_client.put(
            "/api/v1/schedules/test-schedule-123",
            headers=auth_headers,
            json={"enabled": False},  # Only update enabled status
        )

        assert response.status_code == 200

        # Verify only provided fields were updated
        call_args = mock_repository.update_schedule.call_args[0]
        updates = call_args[1]
        assert updates == {"enabled": False}

    @pytest.mark.asyncio
    async def test_update_schedule_invalid_cron(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test schedule update with invalid cron expression."""
        response = await async_client.put(
            "/api/v1/schedules/test-schedule-123",
            headers=auth_headers,
            json={"cron_expression": "invalid"},
        )

        assert response.status_code == 400
        assert "Invalid cron expression" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_delete_schedule_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful schedule deletion."""
        mock_repository.delete_schedule.return_value = True

        response = await async_client.delete(
            "/api/v1/schedules/test-schedule-123", headers=auth_headers
        )

        assert response.status_code == 200
        assert "deleted successfully" in response.json()["message"]

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test deleting non-existent schedule."""
        mock_repository.get_schedule.return_value = None

        response = await async_client.delete(
            "/api/v1/schedules/non-existent", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Schedule" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_schedule_permission_check(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test schedule access permission check."""
        # Mock schedule belongs to different customer
        mock_repository.get_schedule.return_value = {
            "id": "test-schedule-123",
            "customer_id": "different-customer-456",
            "name": "Test Schedule",
            "cron_expression": "0 0 1 * *",
            "analyzers": ["keyword_match", "search_terms"],
            "config": {"date_range": 90},
            "enabled": True,
            "created_at": datetime.utcnow(),
            "last_run": None,
            "next_run": None,
        }

        response = await async_client.get(
            "/api/v1/schedules/test-schedule-123", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_schedule_analyzers_validation(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test schedule creation with invalid analyzer names."""
        response = await async_client.post(
            "/api/v1/schedules",
            headers=auth_headers,
            json={
                "name": "Test Schedule",
                "cron_expression": "0 0 * * *",
                "analyzers": ["invalid_analyzer", "another_invalid"],
                "config": {},
                "enabled": True,
            },
        )

        assert response.status_code == 400
        assert "Invalid analyzer" in response.json()["detail"]
