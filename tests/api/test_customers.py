"""Tests for customer management endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


class TestCustomerEndpoints:
    """Test customer API endpoints."""

    @pytest.mark.asyncio
    async def test_list_customers_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer listing."""
        mock_customers = [
            {
                "id": "customer-1",
                "name": "Customer One",
                "google_ads_customer_id": "123-456-7890",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
            {
                "id": "customer-2",
                "name": "Customer Two",
                "google_ads_customer_id": "098-765-4321",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "last_audit_date": datetime.utcnow(),
                "next_scheduled_audit": None,
            },
        ]

        mock_repository.get_customers_for_user.return_value = mock_customers
        mock_repository.count_customers_for_user.return_value = 2

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 2
        assert data["total"] == 2
        assert data["offset"] == 0
        assert data["limit"] == 20

        # Verify customer data structure
        customer = data["items"][0]
        assert "id" in customer
        assert "name" in customer
        assert "google_ads_customer_id" in customer
        assert "is_active" in customer

    @pytest.mark.asyncio
    async def test_list_customers_pagination(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test customer listing with pagination parameters."""
        mock_repository.get_customers_for_user.return_value = []
        mock_repository.count_customers_for_user.return_value = 50

        response = await async_client.get(
            "/api/v1/customers?offset=20&limit=10", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["offset"] == 20
        assert data["limit"] == 10
        assert data["total"] == 50

        # Verify repository was called with correct parameters
        mock_repository.get_customers_for_user.assert_called_with(
            user_id="test-user-123", offset=20, limit=10
        )

    @pytest.mark.asyncio
    async def test_list_customers_no_auth(self, async_client: AsyncClient):
        """Test customer listing without authentication."""
        response = await async_client.get("/api/v1/customers")

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_customers_invalid_pagination(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test customer listing with invalid pagination parameters."""
        response = await async_client.get(
            "/api/v1/customers?offset=-1&limit=200", headers=auth_headers
        )

        assert response.status_code == 422
        # Check for validation error structure (Pydantic v2 format)
        error_data = response.json()
        assert "detail" in error_data
        assert isinstance(error_data["detail"], list)
        # Should have validation errors for offset and limit
        assert len(error_data["detail"]) >= 2

    @pytest.mark.asyncio
    async def test_get_customer_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer retrieval."""
        mock_customer = {
            "id": "test-customer-123",
            "name": "Test Customer",
            "email": "test@example.com",
            "google_ads_customer_id": "123-456-7890",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {"timezone": "UTC"},
            "is_active": True,
            "last_audit_date": datetime.utcnow(),
            "next_scheduled_audit": None,
        }

        mock_repository.get_customer.return_value = mock_customer

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "test-customer-123"
        assert data["name"] == "Test Customer"
        assert data["google_ads_customer_id"] == "123-456-7890"
        assert data["is_active"] is True
        assert "settings" in data

    @pytest.mark.asyncio
    async def test_get_customer_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test getting non-existent customer."""
        mock_repository.get_customer.return_value = None

        response = await async_client.get(
            "/api/v1/customers/non-existent", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Customer" in response.json()["detail"]
        assert "not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_customer_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test getting customer without permission."""
        # Try to access a different customer
        response = await async_client.get(
            "/api/v1/customers/different-customer-456", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_get_customer_as_agency_with_access(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test agency accessing client customer they have access to."""
        mock_customer = {
            "id": "client-customer-456",
            "name": "Client Customer",
            "google_ads_customer_id": "456-789-0123",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {},
            "is_active": True,
            "user_id": "different-user-123",
            "last_audit_date": None,
            "next_scheduled_audit": None,
        }

        # Override the mock to allow access for this specific test
        def mock_user_access(user_id: str, customer_id: str) -> bool:
            return customer_id == "client-customer-456"

        mock_repository.get_customer.return_value = mock_customer
        mock_repository.user_has_customer_access.side_effect = mock_user_access

        response = await async_client.get(
            "/api/v1/customers/client-customer-456", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["id"] == "client-customer-456"
        assert data["name"] == "Client Customer"

    @pytest.mark.asyncio
    async def test_get_customer_as_agency_without_access(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test agency trying to access client customer without permission."""
        mock_customer = {
            "id": "client-customer-456",
            "name": "Client Customer",
            "google_ads_customer_id": "456-789-0123",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {},
            "is_active": True,
            "user_id": "different-user-123",
        }

        mock_repository.get_customer.return_value = mock_customer
        mock_repository.user_has_customer_access.return_value = False

        response = await async_client.get(
            "/api/v1/customers/client-customer-456", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_customers_as_individual_user(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test individual user listing their own customers only."""
        mock_customers = [
            {
                "id": "own-customer-1",
                "name": "My Customer",
                "google_ads_customer_id": "123-456-7890",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "user_id": "test-user-123",
                "last_audit_date": None,
                "next_scheduled_audit": None,
            }
        ]

        mock_repository.get_customers_for_user.return_value = mock_customers
        mock_repository.count_customers_for_user.return_value = 1

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 1
        assert data["total"] == 1
        assert data["items"][0]["name"] == "My Customer"

    @pytest.mark.asyncio
    async def test_list_customers_as_agency_user(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test agency user listing multiple customer accounts."""
        mock_customers = [
            {
                "id": "agency-customer-1",
                "name": "Agency Own Customer",
                "google_ads_customer_id": "111-111-1111",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "user_id": "test-user-123",  # Agency owns this
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
            {
                "id": "client-customer-2",
                "name": "Client Customer A",
                "google_ads_customer_id": "222-222-2222",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "user_id": "client-user-456",  # Agency has access to this
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
            {
                "id": "client-customer-3",
                "name": "Client Customer B",
                "google_ads_customer_id": "333-333-3333",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
                "user_id": "client-user-789",  # Agency has access to this
                "last_audit_date": None,
                "next_scheduled_audit": None,
            },
        ]

        mock_repository.get_customers_for_user.return_value = mock_customers
        mock_repository.count_customers_for_user.return_value = 3

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 200
        data = response.json()
        assert len(data["items"]) == 3
        assert data["total"] == 3

        # Verify agency can see both owned and client customers
        customer_names = [customer["name"] for customer in data["items"]]
        assert "Agency Own Customer" in customer_names
        assert "Client Customer A" in customer_names
        assert "Client Customer B" in customer_names

        # Verify user_id is not exposed in API response for security
        for customer in data["items"]:
            assert "user_id" not in customer

    @pytest.mark.asyncio
    async def test_individual_user_cannot_access_other_customers(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test individual user cannot access customers they don't own."""
        mock_customer = {
            "id": "other-customer-456",
            "name": "Other Customer",
            "google_ads_customer_id": "456-789-0123",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {},
            "is_active": True,
            "user_id": "different-user-789",
        }

        mock_repository.get_customer.return_value = mock_customer
        mock_repository.user_has_customer_access.return_value = False

        response = await async_client.get(
            "/api/v1/customers/other-customer-456", headers=auth_headers
        )

        assert response.status_code == 403
        assert "permission" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_list_customers_error_handling(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test error handling in customer listing."""
        mock_repository.get_customers_for_user.side_effect = Exception("Database error")

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 500
        assert (
            "An unexpected error occurred while listing customers"
            in response.json()["detail"]
        )
