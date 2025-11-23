"""Tests for enhanced error handling in customer endpoints."""

from datetime import datetime
from unittest.mock import Mock

import pytest
from httpx import AsyncClient
from sqlalchemy.exc import DataError as SQLDataError
from sqlalchemy.exc import IntegrityError, OperationalError

from paidsearchnav_mcp.core.exceptions import (
    AuthenticationError,
    AuthorizationError,
    ValidationError,
)


class TestCustomerErrorHandling:
    """Test error handling scenarios for customer API endpoints."""

    @pytest.mark.asyncio
    async def test_list_customers_database_connection_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test database connection error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = OperationalError(
            "Connection refused", None, None
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 503
        assert response.json()["detail"] == "Database temporarily unavailable"

    @pytest.mark.asyncio
    async def test_list_customers_validation_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test validation error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = ValidationError(
            "Invalid user ID format"
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 400
        assert "Invalid request" in response.json()["detail"]
        assert "Invalid user ID format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_list_customers_authentication_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test authentication error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = AuthenticationError(
            "Token expired"
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    @pytest.mark.asyncio
    async def test_list_customers_authorization_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test authorization error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = AuthorizationError(
            "Insufficient permissions"
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 403
        assert response.json()["detail"] == "Access denied"

    @pytest.mark.asyncio
    async def test_list_customers_generic_database_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test generic SQLAlchemy error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = IntegrityError(
            "Constraint violation", None, None
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 500
        assert response.json()["detail"] == "Database operation failed"

    @pytest.mark.asyncio
    async def test_list_customers_unexpected_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test unexpected error during customer listing."""
        mock_repository.get_customers_for_user.side_effect = RuntimeError(
            "Unexpected runtime error"
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        assert response.status_code == 500
        assert (
            response.json()["detail"]
            == "An unexpected error occurred while listing customers"
        )

    @pytest.mark.asyncio
    async def test_get_customer_database_connection_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test database connection error during customer retrieval."""
        mock_repository.get_customer.side_effect = OperationalError(
            "Database is locked", None, None
        )

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Database temporarily unavailable"

    @pytest.mark.asyncio
    async def test_get_customer_resource_not_found_custom_exception(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test ResourceNotFoundError during customer retrieval."""
        mock_repository.get_customer.return_value = None

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 404
        assert "Customer test-customer-123 not found" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_customer_authorization_denied_custom_exception(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test AuthorizationError during customer retrieval."""
        mock_customer = {
            "id": "denied-customer-123",
            "name": "Denied Customer",
            "google_ads_customer_id": "123-456-7890",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {},
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_customer
        # Override the default mock behavior completely
        mock_repository.user_has_customer_access.side_effect = None
        mock_repository.user_has_customer_access.return_value = False

        response = await async_client.get(
            "/api/v1/customers/denied-customer-123", headers=auth_headers
        )

        assert response.status_code == 403
        assert (
            "You don't have permission to view this customer"
            in response.json()["detail"]
        )

    @pytest.mark.asyncio
    async def test_get_customer_validation_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test validation error during customer retrieval."""
        mock_repository.get_customer.side_effect = ValidationError(
            "Invalid customer ID format"
        )

        response = await async_client.get(
            "/api/v1/customers/invalid-id", headers=auth_headers
        )

        assert response.status_code == 400
        assert "Invalid request" in response.json()["detail"]
        assert "Invalid customer ID format" in response.json()["detail"]

    @pytest.mark.asyncio
    async def test_get_customer_authentication_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test authentication error during customer retrieval."""
        mock_repository.get_customer.side_effect = AuthenticationError("Invalid token")

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 401
        assert response.json()["detail"] == "Authentication required"

    @pytest.mark.asyncio
    async def test_get_customer_generic_database_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test generic SQLAlchemy error during customer retrieval."""
        mock_repository.get_customer.side_effect = SQLDataError(
            "Data type mismatch", None, None
        )

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 500
        assert response.json()["detail"] == "Database operation failed"

    @pytest.mark.asyncio
    async def test_get_customer_unexpected_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test unexpected error during customer retrieval."""
        mock_repository.get_customer.side_effect = ValueError("Unexpected value error")

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 500
        assert (
            response.json()["detail"]
            == "An unexpected error occurred while retrieving customer details"
        )

    @pytest.mark.asyncio
    async def test_list_customers_count_error_still_returns_results(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test that customer listing returns results even if count fails."""
        mock_customers = [
            {
                "id": "customer-1",
                "name": "Customer One",
                "google_ads_customer_id": "123-456-7890",
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "settings": {},
                "is_active": True,
            }
        ]

        mock_repository.get_customers_for_user.return_value = mock_customers
        # Count operation fails with database error
        mock_repository.count_customers_for_user.side_effect = OperationalError(
            "Timeout", None, None
        )

        response = await async_client.get("/api/v1/customers", headers=auth_headers)

        # The entire operation should fail with 503
        assert response.status_code == 503
        assert response.json()["detail"] == "Database temporarily unavailable"

    @pytest.mark.asyncio
    async def test_get_customer_access_check_error(
        self, async_client: AsyncClient, auth_headers: dict, mock_repository: Mock
    ):
        """Test error during access check in get_customer."""
        mock_customer = {
            "id": "test-customer-123",
            "name": "Test Customer",
            "google_ads_customer_id": "123-456-7890",
            "created_at": datetime.utcnow(),
            "updated_at": datetime.utcnow(),
            "settings": {},
            "is_active": True,
        }

        mock_repository.get_customer.return_value = mock_customer
        # Access check fails with database error
        mock_repository.user_has_customer_access.side_effect = OperationalError(
            "Connection timeout", None, None
        )

        response = await async_client.get(
            "/api/v1/customers/test-customer-123", headers=auth_headers
        )

        assert response.status_code == 503
        assert response.json()["detail"] == "Database temporarily unavailable"
