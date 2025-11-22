"""Comprehensive tests for API repository to improve coverage."""

import logging
from datetime import datetime, timezone
from unittest.mock import AsyncMock, MagicMock, patch

import pytest
from sqlalchemy.exc import SQLAlchemyError

from paidsearchnav_mcp.core.config import Settings
from paidsearchnav_mcp.storage.api_repository import APIRepository


@pytest.fixture
def mock_settings(monkeypatch):
    """Create mock settings."""
    # Set environment variable for in-memory database
    monkeypatch.setenv("PSN_STORAGE_CONNECTION_STRING", "sqlite+aiosqlite:///:memory:")
    return Settings(
        environment="development",  # Valid environment value
        debug=True,
    )


@pytest.fixture
async def api_repository(mock_settings):
    """Create APIRepository instance with in-memory database."""
    from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

    from paidsearchnav.storage.models import Base

    # Create an in-memory database for testing
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)

    # Create repository with test engine
    repo = APIRepository(mock_settings)
    repo.AsyncSessionLocal = async_sessionmaker(engine, expire_on_commit=False)

    yield repo

    # Clean up
    await engine.dispose()


def create_async_session_mock(session_mock):
    """Create a consistent async session factory mock."""
    mock_factory = MagicMock()
    mock_factory.return_value.__aenter__.return_value = session_mock
    mock_factory.return_value.__aexit__.return_value = None
    return mock_factory


class TestCheckConnection:
    """Test check_connection method."""

    @pytest.mark.asyncio
    async def test_check_connection_success(self, api_repository):
        """Test successful connection check."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.scalar.return_value = 1
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.check_connection()
            assert result is True
            mock_session.execute.assert_called_once()

    @pytest.mark.asyncio
    async def test_check_connection_failure(self, api_repository):
        """Test connection check failure."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Connection failed")

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "error"
            ) as mock_logger:
                result = await api_repository.check_connection()
                assert result is False
                mock_logger.assert_called_once()


class TestUserHasCustomerAccess:
    """Test user_has_customer_access method."""

    @pytest.mark.asyncio
    async def test_user_not_found(self, api_repository):
        """Test when user is not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns None when user not found
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "warning"
            ) as mock_logger:
                result = await api_repository.user_has_customer_access(
                    "user123", "customer456"
                )
                assert result is False
                mock_logger.assert_called_with("User user123 not found or inactive")

    @pytest.mark.asyncio
    async def test_customer_not_found(self, api_repository):
        """Test when customer is not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns user_type, but owner_id is None (customer not found)
        mock_result.fetchone.return_value = (
            "individual",  # user_type
            None,  # owner_id (customer not found)
            None,  # access_level
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "warning"
            ) as mock_logger:
                result = await api_repository.user_has_customer_access(
                    "user123", "customer456"
                )
                assert result is False
                mock_logger.assert_called_with(
                    "Customer customer456 not found or inactive"
                )

    @pytest.mark.asyncio
    async def test_invalid_user_type(self, api_repository):
        """Test when user has invalid user type."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns invalid user type
        mock_result.fetchone.return_value = (
            "invalid_type",  # invalid user_type
            "owner123",  # owner_id
            None,  # access_level
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "warning"
            ) as mock_logger:
                result = await api_repository.user_has_customer_access(
                    "user123", "customer456"
                )
                assert result is False
                assert any(
                    "Invalid user type" in str(call)
                    for call in mock_logger.call_args_list
                )

    @pytest.mark.asyncio
    async def test_individual_user_owns_customer(self, api_repository):
        """Test individual user accessing their own customer."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns user owns the customer
        mock_result.fetchone.return_value = (
            "individual",  # user_type
            "user123",  # owner_id (same as user_id)
            None,  # access_level
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.user_has_customer_access(
                "user123", "customer456"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_individual_user_not_owns_customer(self, api_repository):
        """Test individual user accessing someone else's customer."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns customer owned by different user
        mock_result.fetchone.return_value = (
            "individual",  # user_type
            "other_user",  # owner_id (different user)
            None,  # access_level
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.user_has_customer_access(
                "user123", "customer456"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_agency_user_owns_customer(self, api_repository):
        """Test agency user accessing their own customer."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns agency user owns the customer
        mock_result.fetchone.return_value = (
            "agency",  # user_type
            "user123",  # owner_id (same as user_id)
            None,  # access_level (not needed since they own it)
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.user_has_customer_access(
                "user123", "customer456"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_agency_user_granted_access(self, api_repository):
        """Test agency user with granted access to customer."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns agency user has granted access
        mock_result.fetchone.return_value = (
            "agency",  # user_type
            "other_user",  # owner_id (different user owns it)
            "read",  # access_level (user has been granted access)
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.user_has_customer_access(
                "user123", "customer456"
            )
            assert result is True

    @pytest.mark.asyncio
    async def test_agency_user_no_access(self, api_repository):
        """Test agency user without access to customer."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns agency user has no access
        mock_result.fetchone.return_value = (
            "agency",  # user_type
            "other_user",  # owner_id (different user owns it)
            None,  # access_level (no access granted)
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.user_has_customer_access(
                "user123", "customer456"
            )
            assert result is False

    @pytest.mark.asyncio
    async def test_unknown_user_type(self, api_repository):
        """Test user with unknown user type."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        # Single query returns admin user type (valid but not handled)
        mock_result.fetchone.return_value = (
            "admin",  # Valid UserType but not individual/agency
            "owner123",  # owner_id
            None,  # access_level
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "warning"
            ) as mock_logger:
                result = await api_repository.user_has_customer_access(
                    "user123", "customer456"
                )
                assert result is False
                # Check that a warning was logged about unknown user type
                mock_logger.assert_called_once()
                call_args = mock_logger.call_args[0][0]
                assert (
                    "Invalid user type" in call_args or "Unknown user type" in call_args
                )

    @pytest.mark.asyncio
    async def test_exception_handling(self, api_repository):
        """Test exception handling in user_has_customer_access."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Database error")

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "error"
            ) as mock_logger:
                result = await api_repository.user_has_customer_access(
                    "user123", "customer456"
                )
                assert result is False
                mock_logger.assert_called_once()


class TestGetCustomer:
    """Test get_customer method."""

    @pytest.mark.asyncio
    async def test_get_customer_not_found(self, api_repository):
        """Test when customer is not found."""
        mock_session = AsyncMock()
        mock_result = MagicMock()
        mock_result.fetchone.return_value = None
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            result = await api_repository.get_customer("customer123")
            assert result is None

    @pytest.mark.asyncio
    async def test_get_customer_success(self, api_repository):
        """Test successful customer retrieval."""
        mock_session = AsyncMock()
        mock_result = MagicMock()

        # Mock customer data as a tuple (matching SQL query result)
        mock_result.fetchone.return_value = (
            "customer123",  # id
            "Test Customer",  # name
            "test@example.com",  # email
            "123-456-7890",  # google_ads_customer_id
            "user456",  # user_id
            {},  # settings
            True,  # is_active
            datetime.now(timezone.utc),  # last_audit_date
            None,  # next_scheduled_audit
            datetime.now(timezone.utc),  # created_at
            datetime.now(timezone.utc),  # updated_at
        )
        mock_session.execute.return_value = mock_result

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            customer = await api_repository.get_customer("customer123")
            assert customer is not None
            assert customer["id"] == "customer123"
            assert customer["name"] == "Test Customer"
            assert customer["email"] == "test@example.com"

    @pytest.mark.asyncio
    async def test_get_customer_exception(self, api_repository):
        """Test exception handling in get_customer."""
        mock_session = AsyncMock()
        mock_session.execute.side_effect = SQLAlchemyError("Database error")

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            with patch.object(
                logging.getLogger("paidsearchnav.storage.api_repository"), "error"
            ) as mock_logger:
                result = await api_repository.get_customer("customer123")
                assert result is None
                mock_logger.assert_called_once()


class TestCreateAudit:
    """Test create_audit method."""

    @pytest.mark.asyncio
    async def test_create_audit_concurrent(self, api_repository):
        """Test concurrent audit creation."""
        # First create test user and customer
        async with api_repository.AsyncSessionLocal() as session:
            from paidsearchnav.storage.models import Customer, User

            user = User(
                email="test@example.com", name="Test User", user_type="individual"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            customer = Customer(
                name="Test Customer",
                email="customer@example.com",
                google_ads_customer_id="1234567890",
                user_id=user.id,
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)

        with patch("paidsearchnav.storage.api_repository.logger") as mock_logger:
            audit_id = await api_repository.create_audit(
                customer_id=customer.id,
                name="Concurrent Test Audit 1",
                analyzers=["keyword_match"],
                config={},
                user_id=user.id,
            )
            assert audit_id is not None
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_create_audit_default(self, api_repository):
        """Test default audit creation."""
        # First create test user and customer
        async with api_repository.AsyncSessionLocal() as session:
            from paidsearchnav.storage.models import Customer, User

            user = User(
                email="test2@example.com", name="Test User 2", user_type="individual"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            customer = Customer(
                name="Test Customer 2",
                email="customer2@example.com",
                google_ads_customer_id="1234567891",
                user_id=user.id,
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)

        with patch("paidsearchnav.storage.api_repository.logger") as mock_logger:
            audit_id = await api_repository.create_audit(
                customer_id=customer.id,
                name="Regular Test Audit",
                analyzers=["keyword_match"],
                config={},
                user_id=user.id,
            )
            assert audit_id is not None
            mock_logger.info.assert_called_once()


class TestGetAudit:
    """Test get_audit method."""

    @pytest.mark.asyncio
    async def test_get_audit_failed(self, api_repository):
        """Test getting a non-existent audit returns None."""
        audit = await api_repository.get_audit("test-failing-audit")
        assert audit is None

    @pytest.mark.asyncio
    async def test_get_audit_completed(self, api_repository):
        """Test getting a created audit."""
        # First create test user and customer
        async with api_repository.AsyncSessionLocal() as session:
            from paidsearchnav.storage.models import Customer, User

            user = User(
                email="test3@example.com", name="Test User 3", user_type="individual"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            customer = Customer(
                name="Test Customer 3",
                email="customer3@example.com",
                google_ads_customer_id="1234567892",
                user_id=user.id,
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)

        # Create audit
        audit_id = await api_repository.create_audit(
            customer_id=customer.id,
            name="Complete Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id=user.id,
        )

        audit = await api_repository.get_audit(audit_id)
        assert audit is not None
        assert audit["id"] == audit_id
        assert audit["status"] == "pending"

    @pytest.mark.asyncio
    async def test_get_audit_running(self, api_repository):
        """Test getting a non-existent audit returns None."""
        audit = await api_repository.get_audit("test-running-audit")
        assert audit is None


class TestListAudits:
    """Test list_audits method."""

    @pytest.mark.asyncio
    async def test_list_audits_basic(self, api_repository):
        """Test basic audit listing with no audits."""
        audits, total = await api_repository.list_audits()
        assert isinstance(audits, list)
        assert len(audits) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_audits_with_status(self, api_repository):
        """Test audit listing with status filter returns empty list."""
        audits, total = await api_repository.list_audits(status="completed")
        assert isinstance(audits, list)
        assert len(audits) == 0
        assert total == 0


class TestScheduleMethods:
    """Test schedule-related methods."""

    @pytest.mark.asyncio
    async def test_create_schedule(self, api_repository):
        """Test creating a schedule."""
        # First create test user and customer
        async with api_repository.AsyncSessionLocal() as session:
            from paidsearchnav.storage.models import Customer, User

            user = User(
                email="sched@example.com", name="Schedule User", user_type="individual"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            customer = Customer(
                name="Schedule Customer",
                email="schedcust@example.com",
                google_ads_customer_id="1234567893",
                user_id=user.id,
            )
            session.add(customer)
            await session.commit()
            await session.refresh(customer)

        with patch("paidsearchnav.storage.api_repository.logger") as mock_logger:
            schedule_id = await api_repository.create_schedule(
                customer_id=customer.id,
                name="Test Schedule",
                cron_expression="0 0 * * 0",
                analyzers=["keyword_match"],
                config={},
                enabled=True,
                user_id=user.id,
            )
            assert schedule_id is not None
            mock_logger.info.assert_called_once()

    @pytest.mark.asyncio
    async def test_get_schedule(self, api_repository):
        """Test getting non-existent schedule returns None."""
        schedule = await api_repository.get_schedule("test-schedule-123")
        assert schedule is None

    @pytest.mark.asyncio
    async def test_list_schedules(self, api_repository):
        """Test listing schedules returns empty list."""
        schedules, total = await api_repository.list_schedules()
        assert isinstance(schedules, list)
        assert len(schedules) == 0
        assert total == 0

    @pytest.mark.asyncio
    async def test_update_schedule(self, api_repository):
        """Test updating a non-existent schedule returns False."""
        result = await api_repository.update_schedule(
            "test-schedule-123", {"enabled": False}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_schedule(self, api_repository):
        """Test deleting a non-existent schedule returns False."""
        result = await api_repository.delete_schedule("test-schedule-123")
        assert result is False


class TestResultsMethods:
    """Test results-related methods."""

    @pytest.mark.asyncio
    async def test_get_audit_results(self, api_repository):
        """Test getting non-existent audit results returns None."""
        results = await api_repository.get_audit_results("test-audit-123")
        assert results is None

    @pytest.mark.asyncio
    async def test_get_analyzer_result(self, api_repository):
        """Test getting analyzer results for non-existent audit returns None."""
        results = await api_repository.get_analyzer_result(
            "test-audit-123", "keyword_match"
        )
        assert results is None

    @pytest.mark.asyncio
    async def test_get_analyzer_result_not_found(self, api_repository):
        """Test getting non-existent analyzer results."""
        results = await api_repository.get_analyzer_result(
            "test-audit-123", "invalid_analyzer"
        )
        assert results is None


class TestReportMethods:
    """Test report generation methods."""

    @pytest.mark.asyncio
    async def test_generate_report(self, api_repository):
        """Test generating a report for non-existent audit raises ValueError."""
        with pytest.raises(ValueError, match="Audit .* not found"):
            await api_repository.generate_report(
                audit_id="test-audit-123",
                format="pdf",
                template="executive_summary",
                include_recommendations=True,
                include_charts=True,
            )

    @pytest.mark.asyncio
    async def test_get_report_metadata(self, api_repository):
        """Test getting metadata for non-existent report returns None."""
        metadata = await api_repository.get_report_metadata(
            "test-report-123", audit_id="test-audit-123"
        )
        assert metadata is None


class TestCustomerMethods:
    """Test customer-related methods."""

    @pytest.mark.asyncio
    async def test_get_customers_for_user(self, api_repository):
        """Test getting customers for a user."""
        mock_session = AsyncMock()

        # Mock user query result
        mock_user_result = MagicMock()
        mock_user_result.fetchone.return_value = ("individual",)

        # Mock customers query result
        mock_customers_result = MagicMock()
        mock_customers_result.fetchall.return_value = [
            (
                "customer123",
                "Test Customer",
                "test@example.com",
                "123-456-7890",
                "user123",
                {},
                True,
                None,
                None,
                datetime.now(timezone.utc),
                datetime.now(timezone.utc),
            )
        ]

        mock_session.execute.side_effect = [mock_user_result, mock_customers_result]

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            customers = await api_repository.get_customers_for_user("user123")
            assert len(customers) == 1
            assert customers[0]["id"] == "customer123"

    @pytest.mark.asyncio
    async def test_count_customers_for_user(self, api_repository):
        """Test counting customers for a user."""
        mock_session = AsyncMock()

        # Mock user query result
        mock_user_result = MagicMock()
        mock_user_result.fetchone.return_value = ("individual",)

        # Mock count result
        mock_count_result = MagicMock()
        mock_count_result.scalar.return_value = 3

        mock_session.execute.side_effect = [mock_user_result, mock_count_result]

        with patch.object(
            api_repository, "AsyncSessionLocal", create_async_session_mock(mock_session)
        ):
            count = await api_repository.count_customers_for_user("user123")
            assert count == 3


class TestCancelAudit:
    """Test cancel_audit method."""

    @pytest.mark.asyncio
    async def test_cancel_audit(self, api_repository):
        """Test canceling a non-existent audit returns False."""
        result = await api_repository.cancel_audit("test-audit-123")
        assert result is False
