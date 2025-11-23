"""Tests for customer access control logic in API repository."""

from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav_mcp.storage.api_repository import APIRepository
from paidsearchnav_mcp.storage.models import UserType


class TestCustomerAccessControl:
    """Test customer access control logic."""

    @pytest.fixture
    def mock_repository(self):
        """Create a mock repository for testing."""
        from pathlib import Path

        from paidsearchnav.core.config import Settings

        # Create a mock settings object with all required attributes
        mock_settings = MagicMock(spec=Settings)
        mock_settings.environment = "test"
        mock_settings.database_url = "sqlite:///:memory:"
        mock_settings.data_dir = Path("/tmp")
        mock_settings.debug = False

        # Add logging configuration to prevent AttributeError
        mock_logging = MagicMock()
        mock_logging.session_logging = MagicMock()
        mock_logging.session_logging.enabled = False
        mock_logging.session_logging.metrics_interval = 60
        mock_logging.session_logging.detailed_logging = False
        mock_settings.logging = mock_logging

        repo = APIRepository(mock_settings)
        repo.AsyncSessionLocal = MagicMock()
        return repo

    @pytest.mark.asyncio
    async def test_individual_user_has_access_to_own_customer(self, mock_repository):
        """Test individual user can access their own customer."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Returns: user_type, owner_id, access_level
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.INDIVIDUAL.value,  # user_type
            "test-user-123",  # owner_id (customer owner)
            None,  # access_level (not needed for owner)
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "test-user-123", "customer-456"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_individual_user_cannot_access_other_customer(self, mock_repository):
        """Test individual user cannot access another user's customer."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Returns: user_type, owner_id, access_level
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.INDIVIDUAL.value,  # user_type
            "different-user-789",  # owner_id (different user owns this customer)
            None,  # access_level (no granted access)
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "test-user-123", "customer-456"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_agency_user_has_access_to_own_customer(self, mock_repository):
        """Test agency user can access their own customer."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Returns: user_type, owner_id, access_level
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.AGENCY.value,  # user_type
            "agency-user-123",  # owner_id (agency owns this customer)
            None,  # access_level (not needed since they own it)
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "agency-user-123", "customer-456"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_agency_user_has_access_via_customer_access(self, mock_repository):
        """Test agency user can access customer via CustomerAccess table."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Returns: user_type, owner_id, access_level
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.AGENCY.value,  # user_type
            "client-user-789",  # owner_id (different user owns this customer)
            "read",  # access_level (agency has been granted access)
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "agency-user-123", "customer-456"
        )

        assert result is True

    @pytest.mark.asyncio
    async def test_agency_user_no_access_without_permission(self, mock_repository):
        """Test agency user cannot access customer without permission."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Returns: user_type, owner_id, access_level
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.AGENCY.value,  # user_type
            "client-user-789",  # owner_id (different user owns this customer)
            None,  # access_level (no access granted)
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "agency-user-123", "customer-456"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_nonexistent_user_has_no_access(self, mock_repository):
        """Test nonexistent user has no access."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # User not found returns None
        query_result = MagicMock()
        query_result.fetchone.return_value = None

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "nonexistent-user", "customer-456"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_nonexistent_customer_has_no_access(self, mock_repository):
        """Test access to nonexistent customer returns False."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result
        # Customer not found returns owner_id as None
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.INDIVIDUAL.value,  # user_type (user exists)
            None,  # owner_id (customer not found)
            None,  # access_level
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "test-user-123", "nonexistent-customer"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_customers_for_individual_user(self, mock_repository):
        """Test individual user gets only their own customers."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock user type query
        user_result = MagicMock()
        user_result.fetchone.return_value = (UserType.INDIVIDUAL.value,)

        # Mock customers query
        customers_result = MagicMock()
        customers_result.fetchall.return_value = [
            (
                "customer-1",
                "My Customer",
                "test@example.com",
                "1234567890",
                "user-123",
                {},
                True,
                None,
                None,
                datetime.now(),
                datetime.now(),
            )
        ]

        mock_session.execute.side_effect = [user_result, customers_result]

        result = await mock_repository.get_customers_for_user(
            "user-123", offset=0, limit=20
        )

        assert len(result) == 1
        assert result[0]["id"] == "customer-1"
        assert result[0]["name"] == "My Customer"
        assert result[0]["user_id"] == "user-123"

    @pytest.mark.asyncio
    async def test_get_customers_for_agency_user(self, mock_repository):
        """Test agency user gets own customers plus accessible customers."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock user type query
        user_result = MagicMock()
        user_result.fetchone.return_value = (UserType.AGENCY.value,)

        # Mock customers query (includes own customers + accessible customers)
        customers_result = MagicMock()
        customers_result.fetchall.return_value = [
            (
                "customer-1",
                "Agency Customer",
                "agency@example.com",
                "1111111111",
                "agency-123",
                {},
                True,
                None,
                None,
                datetime.now(),
                datetime.now(),
            ),
            (
                "customer-2",
                "Client Customer A",
                "clienta@example.com",
                "2222222222",
                "client-456",
                {},
                True,
                None,
                None,
                datetime.now(),
                datetime.now(),
            ),
            (
                "customer-3",
                "Client Customer B",
                "clientb@example.com",
                "3333333333",
                "client-789",
                {},
                True,
                None,
                None,
                datetime.now(),
                datetime.now(),
            ),
        ]

        mock_session.execute.side_effect = [user_result, customers_result]

        result = await mock_repository.get_customers_for_user(
            "agency-123", offset=0, limit=20
        )

        assert len(result) == 3
        customer_names = [c["name"] for c in result]
        assert "Agency Customer" in customer_names
        assert "Client Customer A" in customer_names
        assert "Client Customer B" in customer_names

    @pytest.mark.asyncio
    async def test_count_customers_for_individual_user(self, mock_repository):
        """Test counting customers for individual user."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock user type query
        user_result = MagicMock()
        user_result.fetchone.return_value = (UserType.INDIVIDUAL.value,)

        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 2

        mock_session.execute.side_effect = [user_result, count_result]

        result = await mock_repository.count_customers_for_user("user-123")

        assert result == 2

    @pytest.mark.asyncio
    async def test_count_customers_for_agency_user(self, mock_repository):
        """Test counting customers for agency user."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock user type query
        user_result = MagicMock()
        user_result.fetchone.return_value = (UserType.AGENCY.value,)

        # Mock count query
        count_result = MagicMock()
        count_result.scalar.return_value = 5

        mock_session.execute.side_effect = [user_result, count_result]

        result = await mock_repository.count_customers_for_user("agency-123")

        assert result == 5

    @pytest.mark.asyncio
    async def test_database_error_handling(self, mock_repository):
        """Test error handling when database operations fail."""
        # Mock session that raises an exception
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )
        mock_session.execute.side_effect = Exception("Database connection failed")

        result = await mock_repository.user_has_customer_access(
            "user-123", "customer-456"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_get_customer_returns_proper_data(self, mock_repository):
        """Test get_customer returns properly structured data."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock customer query
        customer_result = MagicMock()
        created_at = datetime.now(timezone.utc)
        updated_at = datetime.now(timezone.utc)
        customer_result.fetchone.return_value = (
            "customer-123",
            "Test Customer",
            "test@example.com",
            "1234567890",
            "user-456",
            {"timezone": "UTC"},
            True,
            None,
            None,
            created_at,
            updated_at,
        )

        mock_session.execute.return_value = customer_result

        result = await mock_repository.get_customer("customer-123")

        assert result is not None
        assert result["id"] == "customer-123"
        assert result["name"] == "Test Customer"
        assert result["email"] == "test@example.com"
        assert result["google_ads_customer_id"] == "1234567890"
        assert result["user_id"] == "user-456"
        assert result["settings"] == {"timezone": "UTC"}
        assert result["is_active"] is True
        assert result["created_at"] == created_at
        assert result["updated_at"] == updated_at

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, mock_repository):
        """Test get_customer returns None for nonexistent customer."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock customer query (no results)
        customer_result = MagicMock()
        customer_result.fetchone.return_value = None

        mock_session.execute.return_value = customer_result

        result = await mock_repository.get_customer("nonexistent-customer")

        assert result is None

    @pytest.mark.asyncio
    async def test_invalid_user_type_returns_false(self, mock_repository):
        """Test that invalid user type in database returns False."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result with invalid user type
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            "INVALID_TYPE",  # Invalid user_type value
            "test-user-123",  # owner_id
            None,  # access_level
        )

        mock_session.execute.return_value = query_result

        result = await mock_repository.user_has_customer_access(
            "test-user-123", "customer-456"
        )

        assert result is False

    @pytest.mark.asyncio
    async def test_optimized_query_performance(self, mock_repository):
        """Test that user_has_customer_access uses only one query."""
        # Mock session and query results
        mock_session = AsyncMock()
        mock_repository.AsyncSessionLocal.return_value.__aenter__.return_value = (
            mock_session
        )

        # Mock single JOIN query result for agency user with granted access
        query_result = MagicMock()
        query_result.fetchone.return_value = (
            UserType.AGENCY.value,  # user_type
            "client-user-789",  # owner_id (different user owns this customer)
            "read",  # access_level (agency has been granted access)
        )

        mock_session.execute.return_value = query_result

        # Call the method
        result = await mock_repository.user_has_customer_access(
            "agency-user-123", "customer-456"
        )

        # Verify result
        assert result is True

        # IMPORTANT: Verify that execute was called only ONCE
        # This is the key performance improvement - reduced from 2-3 queries to 1
        assert mock_session.execute.call_count == 1

        # Verify the query includes all necessary JOINs
        executed_query = mock_session.execute.call_args[0][0].text
        assert "FROM users u" in executed_query
        assert "LEFT JOIN customers c" in executed_query
        assert "LEFT JOIN customer_access ca" in executed_query
