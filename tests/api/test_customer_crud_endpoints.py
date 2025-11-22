"""Tests for customer CRUD endpoints (Create, Update, Delete, Initialize)."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient


class TestCustomerCreateEndpoint:
    """Test customer creation endpoint."""

    @pytest.mark.asyncio
    async def test_create_customer_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer creation."""
        customer_data = {
            "name": "New Customer",
            "email": "new@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "1234567890",
            "settings": {
                "business_type": "retail",
                "location": "Dallas, TX",
                "audit_frequency": "quarterly",
            },
        }

        mock_created_customer = {
            "id": "new-customer-123",
            "name": "New Customer",
            "email": "new@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "1234567890",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "settings": customer_data["settings"],
        }

        mock_repository.get_customer_by_google_ads_id.return_value = (
            None  # No duplicate
        )
        mock_repository.create_customer.return_value = mock_created_customer
        mock_repository.link_user_to_customer.return_value = None

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["name"] == "New Customer"
        assert data["email"] == "new@example.com"
        assert data["google_ads_customer_id"] == "1234567890"
        assert data["is_active"] is True
        assert "settings" in data

        # Verify repository methods were called
        mock_repository.get_customer_by_google_ads_id.assert_called_once_with(
            "1234567890"
        )
        mock_repository.create_customer.assert_called_once()
        mock_repository.link_user_to_customer.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_customer_duplicate_google_ads_id(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test creating customer with existing Google Ads ID."""
        customer_data = {
            "name": "Duplicate Customer",
            "email": "duplicate@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "1234567890",
        }

        # Mock existing customer
        mock_existing_customer = {
            "id": "existing-customer-456",
            "google_ads_customer_id": "1234567890",
        }
        mock_repository.get_customer_by_google_ads_id.return_value = (
            mock_existing_customer
        )

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 409
        assert "already exists" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_customer_invalid_email(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating customer with invalid email."""
        customer_data = {
            "name": "Invalid Email Customer",
            "email": "invalid-email-format",
            "user_type": "individual",
        }

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        assert any("email" in str(error).lower() for error in error_data["detail"])

    @pytest.mark.asyncio
    async def test_create_customer_invalid_google_ads_id(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating customer with invalid Google Ads ID."""
        customer_data = {
            "name": "Invalid Ads ID Customer",
            "email": "test@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "12345",  # Too short
        }

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "10 digits" in str(error_data["detail"])

    @pytest.mark.asyncio
    async def test_create_customer_invalid_user_type(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating customer with invalid user type."""
        customer_data = {
            "name": "Invalid User Type Customer",
            "email": "test@example.com",
            "user_type": "invalid_type",
        }

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "individual" in str(error_data["detail"]) or "agency" in str(
            error_data["detail"]
        )

    @pytest.mark.asyncio
    async def test_create_customer_no_auth(self, async_client: AsyncClient):
        """Test creating customer without authentication."""
        customer_data = {
            "name": "Unauthorized Customer",
            "email": "test@example.com",
            "user_type": "individual",
        }

        response = await async_client.post("/api/v1/customers", json=customer_data)

        assert response.status_code == 403
        assert "Not authenticated" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_create_customer_missing_required_fields(
        self, async_client: AsyncClient, auth_headers: dict
    ):
        """Test creating customer with missing required fields."""
        customer_data = {
            "name": "Incomplete Customer"
            # Missing email
        }

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 422
        error_data = response.json()
        assert "detail" in error_data
        assert any("email" in str(error).lower() for error in error_data["detail"])


class TestCustomerUpdateEndpoint:
    """Test customer update endpoint."""

    @pytest.mark.asyncio
    async def test_update_customer_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer update."""
        customer_id = "test-customer-123"
        update_data = {
            "name": "Updated Customer Name",
            "email": "updated@example.com",
            "settings": {"business_type": "updated_type", "audit_frequency": "monthly"},
        }

        mock_existing_customer = {
            "id": customer_id,
            "name": "Original Name",
            "email": "original@example.com",
            "is_active": True,
        }

        mock_updated_customer = {
            "id": customer_id,
            "name": "Updated Customer Name",
            "email": "updated@example.com",
            "google_ads_customer_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "settings": update_data["settings"],
            "last_audit_date": None,
            "next_scheduled_audit": None,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.update_customer.return_value = mock_updated_customer

        response = await async_client.put(
            f"/api/v1/customers/{customer_id}", headers=auth_headers, json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Updated Customer Name"
        assert data["email"] == "updated@example.com"
        assert data["settings"] == update_data["settings"]

        # Verify repository methods were called
        mock_repository.get_customer.assert_called_once_with(customer_id)
        mock_repository.user_has_customer_access.assert_called_once()
        mock_repository.update_customer.assert_called_once()

    @pytest.mark.asyncio
    async def test_update_customer_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test updating non-existent customer."""
        customer_id = "non-existent-123"
        update_data = {"name": "Updated Name"}

        mock_repository.get_customer.return_value = None

        response = await async_client.put(
            f"/api/v1/customers/{customer_id}", headers=auth_headers, json=update_data
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_update_customer_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test updating customer without permission."""
        customer_id = "no-access-customer-123"
        update_data = {"name": "Unauthorized Update"}

        mock_existing_customer = {
            "id": customer_id,
            "name": "Original Name",
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = False

        response = await async_client.put(
            f"/api/v1/customers/{customer_id}", headers=auth_headers, json=update_data
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_update_customer_partial_update(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test partial customer update (only some fields)."""
        customer_id = "test-customer-123"
        update_data = {"name": "Only Name Updated"}  # Only updating name

        mock_existing_customer = {
            "id": customer_id,
            "name": "Original Name",
            "email": "original@example.com",
            "is_active": True,
        }

        mock_updated_customer = {
            "id": customer_id,
            "name": "Only Name Updated",
            "email": "original@example.com",  # Email unchanged
            "google_ads_customer_id": None,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "settings": {},
            "last_audit_date": None,
            "next_scheduled_audit": None,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.update_customer.return_value = mock_updated_customer

        response = await async_client.put(
            f"/api/v1/customers/{customer_id}", headers=auth_headers, json=update_data
        )

        assert response.status_code == 200
        data = response.json()
        assert data["name"] == "Only Name Updated"
        assert data["email"] == "original@example.com"


class TestCustomerDeleteEndpoint:
    """Test customer deletion endpoint."""

    @pytest.mark.asyncio
    async def test_delete_customer_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer deletion."""
        customer_id = "test-customer-123"

        mock_existing_customer = {
            "id": customer_id,
            "name": "Customer to Delete",
            "created_by": "test-user-123",  # Same as authenticated user
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.update_customer.return_value = None

        response = await async_client.delete(
            f"/api/v1/customers/{customer_id}", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert "deleted successfully" in data["message"]

        # Verify soft delete was called
        mock_repository.update_customer.assert_called_once()
        update_call_args = mock_repository.update_customer.call_args[0]
        update_data = update_call_args[1]
        assert update_data["is_active"] is False
        assert "deleted_at" in update_data
        assert "deleted_by" in update_data

    @pytest.mark.asyncio
    async def test_delete_customer_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test deleting non-existent customer."""
        customer_id = "non-existent-123"

        mock_repository.get_customer.return_value = None

        response = await async_client.delete(
            f"/api/v1/customers/{customer_id}", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_delete_customer_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test deleting customer without permission."""
        customer_id = "no-permission-customer-123"

        mock_existing_customer = {
            "id": customer_id,
            "name": "Protected Customer",
            "created_by": "different-user-456",  # Different user
            "is_active": True,
        }

        # Mock user is not admin and didn't create the customer
        mock_user = {"id": "test-user-123", "role": "user"}

        mock_repository.get_customer.return_value = mock_existing_customer

        response = await async_client.delete(
            f"/api/v1/customers/{customer_id}", headers=auth_headers
        )

        assert response.status_code == 403
        assert "administrators or customer creators" in response.json()["detail"]


class TestCustomerInitializeEndpoint:
    """Test customer initialization endpoint."""

    @pytest.mark.asyncio
    async def test_initialize_customer_success(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test successful customer initialization."""
        customer_id = "test-customer-123"

        mock_existing_customer = {
            "id": customer_id,
            "name": "Customer to Initialize",
            "google_ads_customer_id": "1234567890",
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.update_customer.return_value = None

        response = await async_client.post(
            f"/api/v1/customers/{customer_id}/initialize", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == customer_id
        assert data["status"] == "initialized"
        assert data["s3_folder_created"] is True
        assert data["google_ads_validated"] is True
        assert "timestamp" in data
        assert "initialized_by" in data

        # Verify initialization status was updated
        mock_repository.update_customer.assert_called_once()
        update_call_args = mock_repository.update_customer.call_args[0]
        update_data = update_call_args[1]
        assert update_data["initialization_status"] == "completed"
        assert "initialization_date" in update_data

    @pytest.mark.asyncio
    async def test_initialize_customer_not_found(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test initializing non-existent customer."""
        customer_id = "non-existent-123"

        mock_repository.get_customer.return_value = None

        response = await async_client.post(
            f"/api/v1/customers/{customer_id}/initialize", headers=auth_headers
        )

        assert response.status_code == 404
        assert "not found" in response.json()["detail"].lower()

    @pytest.mark.asyncio
    async def test_initialize_customer_no_permission(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test initializing customer without permission."""
        customer_id = "no-access-customer-123"

        mock_existing_customer = {
            "id": customer_id,
            "name": "Protected Customer",
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = False

        response = await async_client.post(
            f"/api/v1/customers/{customer_id}/initialize", headers=auth_headers
        )

        assert response.status_code == 403
        assert "Access denied" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_initialize_customer_without_google_ads_id(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test initializing customer without Google Ads ID."""
        customer_id = "test-customer-123"

        mock_existing_customer = {
            "id": customer_id,
            "name": "Customer Without Ads ID",
            "google_ads_customer_id": None,  # No Google Ads ID
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_existing_customer
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.update_customer.return_value = None

        response = await async_client.post(
            f"/api/v1/customers/{customer_id}/initialize", headers=auth_headers
        )

        assert response.status_code == 200
        data = response.json()
        assert data["customer_id"] == customer_id
        assert data["status"] == "initialized"
        assert data["s3_folder_created"] is True
        assert (
            data["google_ads_validated"] is False
        )  # Should be False without Google Ads ID


class TestCustomerEndpointsValidation:
    """Test validation for all customer endpoints."""

    @pytest.mark.asyncio
    async def test_create_customer_with_valid_settings(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test creating customer with valid complex settings."""
        customer_data = {
            "name": "Customer with Settings",
            "email": "settings@example.com",
            "user_type": "agency",
            "google_ads_customer_id": "9876543210",
            "settings": {
                "business_type": "ecommerce",
                "location": "San Francisco, CA",
                "audit_frequency": "monthly",
                "local_targeting": True,
                "focus_areas": ["cost_efficiency", "keyword_conflicts"],
                "timezone": "America/Los_Angeles",
                "notifications_enabled": True,
            },
        }

        mock_created_customer = {
            "id": "settings-customer-123",
            **customer_data,
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
        }

        mock_repository.get_customer_by_google_ads_id.return_value = None
        mock_repository.create_customer.return_value = mock_created_customer
        mock_repository.link_user_to_customer.return_value = None

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["settings"]["business_type"] == "ecommerce"
        assert data["settings"]["local_targeting"] is True
        assert data["settings"]["focus_areas"] == [
            "cost_efficiency",
            "keyword_conflicts",
        ]

    @pytest.mark.asyncio
    async def test_email_normalization(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test that email addresses are normalized."""
        customer_data = {
            "name": "Email Test Customer",
            "email": "UPPERCASE@EXAMPLE.COM",  # Should be normalized to lowercase
            "user_type": "individual",
        }

        mock_created_customer = {
            "id": "email-test-123",
            "name": "Email Test Customer",
            "email": "uppercase@example.com",  # Normalized
            "user_type": "individual",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "settings": {},
        }

        mock_repository.get_customer_by_google_ads_id.return_value = None
        mock_repository.create_customer.return_value = mock_created_customer
        mock_repository.link_user_to_customer.return_value = None

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["email"] == "uppercase@example.com"  # Should be normalized

    @pytest.mark.asyncio
    async def test_google_ads_id_normalization(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test that Google Ads IDs are normalized (hyphens removed)."""
        customer_data = {
            "name": "Google Ads Test Customer",
            "email": "ads@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "123-456-7890",  # With hyphens
        }

        mock_created_customer = {
            "id": "ads-test-123",
            "name": "Google Ads Test Customer",
            "email": "ads@example.com",
            "user_type": "individual",
            "google_ads_customer_id": "1234567890",  # Normalized (no hyphens)
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "is_active": True,
            "settings": {},
        }

        mock_repository.get_customer_by_google_ads_id.return_value = None
        mock_repository.create_customer.return_value = mock_created_customer
        mock_repository.link_user_to_customer.return_value = None

        response = await async_client.post(
            "/api/v1/customers", headers=auth_headers, json=customer_data
        )

        assert response.status_code == 201
        data = response.json()
        assert data["google_ads_customer_id"] == "1234567890"  # Should be normalized
