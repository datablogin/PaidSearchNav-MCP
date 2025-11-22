"""Comprehensive database tests for API repository methods."""

from datetime import datetime, timezone

import pytest
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from paidsearchnav.core.config import Settings
from paidsearchnav.storage.api_repository import APIRepository
from paidsearchnav.storage.models import (
    AnalysisRecord,
    Audit,
    Base,
    Customer,
    Report,
    User,
)


@pytest.fixture
async def async_engine():
    """Create async engine for testing."""
    engine = create_async_engine("sqlite+aiosqlite:///:memory:", echo=False)
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    yield engine
    await engine.dispose()


@pytest.fixture
async def session_local(async_engine):
    """Create session local for testing."""
    return async_sessionmaker(async_engine, expire_on_commit=False)


@pytest.fixture
def mock_settings(monkeypatch):
    """Create mock settings."""
    # Set environment variable for in-memory database
    monkeypatch.setenv("PSN_STORAGE_CONNECTION_STRING", "sqlite+aiosqlite:///:memory:")
    return Settings(
        environment="development",
        debug=True,
    )


@pytest.fixture
async def api_repository(session_local, mock_settings):
    """Create APIRepository with real database connection."""
    # Mock the repository to use our test session
    repo = APIRepository(mock_settings)
    repo.AsyncSessionLocal = session_local
    return repo


@pytest.fixture
async def test_user(session_local):
    """Create a test user."""
    async with session_local() as session:
        user = User(email="test@example.com", name="Test User", user_type="individual")
        session.add(user)
        await session.commit()
        await session.refresh(user)
        return user


@pytest.fixture
async def test_customer(session_local, test_user):
    """Create a test customer."""
    async with session_local() as session:
        customer = Customer(
            name="Test Customer",
            email="customer@example.com",
            google_ads_customer_id="1234567890",
            user_id=test_user.id,
        )
        session.add(customer)
        await session.commit()
        await session.refresh(customer)
        return customer


class TestAuditMethods:
    """Test audit-related methods."""

    @pytest.mark.asyncio
    async def test_create_audit_success(self, api_repository, test_customer, test_user):
        """Test successful audit creation."""
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match", "search_terms"],
            config={"date_range": 30},
            user_id=test_user.id,
        )

        assert audit_id is not None

        # Verify audit was created
        audit = await api_repository.get_audit(audit_id)
        assert audit is not None
        assert audit["name"] == "Test Audit"
        assert audit["status"] == "pending"
        assert audit["analyzers"] == ["keyword_match", "search_terms"]
        assert audit["customer_id"] == test_customer.id
        assert audit["user_id"] == test_user.id

    @pytest.mark.asyncio
    async def test_create_audit_invalid_customer(self, api_repository):
        """Test audit creation with invalid customer UUID format."""
        # SQLite doesn't enforce foreign key constraints by default,
        # so this test just verifies the audit is created (even with invalid references)
        audit_id = await api_repository.create_audit(
            customer_id="00000000-0000-0000-0000-000000000000",  # Valid UUID format but non-existent
            name="Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id="00000000-0000-0000-0000-000000000001",  # Valid UUID format but non-existent
        )
        assert audit_id is not None

    @pytest.mark.asyncio
    async def test_get_audit_not_found(self, api_repository):
        """Test getting non-existent audit."""
        audit = await api_repository.get_audit("non-existent")
        assert audit is None

    @pytest.mark.asyncio
    async def test_list_audits_empty(self, api_repository):
        """Test listing audits when none exist."""
        audits, total = await api_repository.list_audits()
        assert audits == []
        assert total == 0

    @pytest.mark.asyncio
    async def test_list_audits_with_data(
        self, api_repository, test_customer, test_user
    ):
        """Test listing audits with existing data."""
        # Create test audits
        audit1_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Audit 1",
            analyzers=["keyword_match"],
            config={},
            user_id=test_user.id,
        )

        audit2_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Audit 2",
            analyzers=["search_terms"],
            config={},
            user_id=test_user.id,
        )

        # Test listing all audits
        audits, total = await api_repository.list_audits()
        assert len(audits) == 2
        assert total == 2

        # Test filtering by customer
        audits, total = await api_repository.list_audits(customer_id=test_customer.id)
        assert len(audits) == 2
        assert total == 2

        # Test filtering by status
        audits, total = await api_repository.list_audits(status="pending")
        assert len(audits) == 2
        assert total == 2

        # Test pagination
        audits, total = await api_repository.list_audits(offset=0, limit=1)
        assert len(audits) == 1
        assert total == 2

    @pytest.mark.asyncio
    async def test_cancel_audit_success(self, api_repository, test_customer, test_user):
        """Test successful audit cancellation."""
        # Create audit
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id=test_user.id,
        )

        # Cancel audit
        result = await api_repository.cancel_audit(audit_id)
        assert result is True

        # Verify audit was cancelled
        audit = await api_repository.get_audit(audit_id)
        assert audit["status"] == "cancelled"
        assert audit["completed_at"] is not None

    @pytest.mark.asyncio
    async def test_cancel_audit_not_found(self, api_repository):
        """Test cancelling non-existent audit."""
        result = await api_repository.cancel_audit("non-existent")
        assert result is False

    @pytest.mark.asyncio
    async def test_cancel_audit_already_completed(
        self, api_repository, session_local, test_customer, test_user
    ):
        """Test cancelling already completed audit."""
        # Create and manually complete audit
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id=test_user.id,
        )

        # Manually mark as completed
        async with session_local() as session:
            audit = await session.get(Audit, audit_id)
            audit.status = "completed"
            await session.commit()

        # Try to cancel completed audit
        result = await api_repository.cancel_audit(audit_id)
        assert result is False


class TestScheduleMethods:
    """Test schedule-related methods."""

    @pytest.mark.asyncio
    async def test_create_schedule_success(
        self, api_repository, test_customer, test_user
    ):
        """Test successful schedule creation."""
        schedule_id = await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Daily Audit",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={"date_range": 7},
            enabled=True,
            user_id=test_user.id,
        )

        assert schedule_id is not None

        # Verify schedule was created
        schedule = await api_repository.get_schedule(schedule_id)
        assert schedule is not None
        assert schedule["name"] == "Daily Audit"
        assert schedule["cron_expression"] == "0 9 * * *"
        assert schedule["enabled"] is True
        assert schedule["next_run_at"] is not None

    @pytest.mark.asyncio
    async def test_create_schedule_invalid_cron(
        self, api_repository, test_customer, test_user
    ):
        """Test schedule creation with invalid cron expression."""
        with pytest.raises(ValueError, match="Invalid cron expression"):
            await api_repository.create_schedule(
                customer_id=test_customer.id,
                name="Invalid Schedule",
                cron_expression="invalid cron",
                analyzers=["keyword_match"],
                config={},
                enabled=True,
                user_id=test_user.id,
            )

    @pytest.mark.asyncio
    async def test_create_schedule_disabled(
        self, api_repository, test_customer, test_user
    ):
        """Test creating disabled schedule."""
        schedule_id = await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Disabled Schedule",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={},
            enabled=False,
            user_id=test_user.id,
        )

        schedule = await api_repository.get_schedule(schedule_id)
        assert schedule["enabled"] is False
        assert schedule["next_run_at"] is None

    @pytest.mark.asyncio
    async def test_get_schedule_not_found(self, api_repository):
        """Test getting non-existent schedule."""
        schedule = await api_repository.get_schedule("non-existent")
        assert schedule is None

    @pytest.mark.asyncio
    async def test_list_schedules(self, api_repository, test_customer, test_user):
        """Test listing schedules."""
        # Create test schedules
        await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Schedule 1",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={},
            enabled=True,
            user_id=test_user.id,
        )

        schedules, total = await api_repository.list_schedules(
            customer_id=test_customer.id
        )
        assert len(schedules) == 1
        assert total == 1

    @pytest.mark.asyncio
    async def test_update_schedule_success(
        self, api_repository, test_customer, test_user
    ):
        """Test successful schedule update."""
        schedule_id = await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Original Schedule",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={},
            enabled=True,
            user_id=test_user.id,
        )

        # Update schedule
        result = await api_repository.update_schedule(
            schedule_id, {"name": "Updated Schedule", "enabled": False}
        )
        assert result is True

        # Verify update
        schedule = await api_repository.get_schedule(schedule_id)
        assert schedule["name"] == "Updated Schedule"
        assert schedule["enabled"] is False
        assert schedule["next_run_at"] is None

    @pytest.mark.asyncio
    async def test_update_schedule_invalid_cron(
        self, api_repository, test_customer, test_user
    ):
        """Test schedule update with invalid cron expression."""
        schedule_id = await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Test Schedule",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={},
            enabled=True,
            user_id=test_user.id,
        )

        result = await api_repository.update_schedule(
            schedule_id, {"cron_expression": "invalid cron"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_update_schedule_not_found(self, api_repository):
        """Test updating non-existent schedule."""
        result = await api_repository.update_schedule(
            "non-existent", {"name": "New Name"}
        )
        assert result is False

    @pytest.mark.asyncio
    async def test_delete_schedule_success(
        self, api_repository, test_customer, test_user
    ):
        """Test successful schedule deletion."""
        schedule_id = await api_repository.create_schedule(
            customer_id=test_customer.id,
            name="Test Schedule",
            cron_expression="0 9 * * *",
            analyzers=["keyword_match"],
            config={},
            enabled=True,
            user_id=test_user.id,
        )

        result = await api_repository.delete_schedule(schedule_id)
        assert result is True

        # Verify deletion
        schedule = await api_repository.get_schedule(schedule_id)
        assert schedule is None

    @pytest.mark.asyncio
    async def test_delete_schedule_not_found(self, api_repository):
        """Test deleting non-existent schedule."""
        result = await api_repository.delete_schedule("non-existent")
        assert result is False


class TestReportMethods:
    """Test report-related methods."""

    @pytest.mark.asyncio
    async def test_generate_report_success(
        self, api_repository, test_customer, test_user
    ):
        """Test successful report generation."""
        # Create audit first
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id=test_user.id,
        )

        # Generate report
        report_id = await api_repository.generate_report(
            audit_id=audit_id,
            format="pdf",
            template="executive_summary",
            include_recommendations=True,
            include_charts=True,
        )

        assert report_id is not None

        # Verify report metadata
        metadata = await api_repository.get_report_metadata(report_id)
        assert metadata is not None
        assert metadata["audit_id"] == audit_id
        assert metadata["format"] == "pdf"
        assert metadata["template"] == "executive_summary"
        assert metadata["status"] == "generating"

    @pytest.mark.asyncio
    async def test_generate_report_invalid_audit(self, api_repository):
        """Test report generation with invalid audit."""
        with pytest.raises(ValueError, match="Audit .* not found"):
            await api_repository.generate_report(
                audit_id="non-existent", format="pdf", template="executive_summary"
            )

    @pytest.mark.asyncio
    async def test_get_report_metadata_not_found(self, api_repository):
        """Test getting metadata for non-existent report."""
        metadata = await api_repository.get_report_metadata("non-existent")
        assert metadata is None


class TestResultsMethods:
    """Test results-related methods."""

    @pytest.mark.asyncio
    async def test_get_audit_results_not_found(self, api_repository):
        """Test getting results for non-existent audit."""
        results = await api_repository.get_audit_results("non-existent")
        assert results is None

    @pytest.mark.asyncio
    async def test_get_audit_results_with_data(
        self, api_repository, session_local, test_customer, test_user
    ):
        """Test getting audit results with analysis data."""
        # Create audit
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match", "search_terms"],
            config={},
            user_id=test_user.id,
        )

        # Add a small delay to ensure analysis records are created after the audit
        import asyncio

        await asyncio.sleep(0.01)

        # Create some analysis records
        async with session_local() as session:
            record1 = AnalysisRecord(
                customer_id=test_customer.google_ads_customer_id,
                analysis_type="audit",
                analyzer_name="keyword_match",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                status="completed",
                total_recommendations=5,
                critical_issues=2,
                potential_cost_savings=100.0,
                result_data={
                    "recommendations": [{"id": "rec1", "type": "optimization"}]
                },
            )

            record2 = AnalysisRecord(
                customer_id=test_customer.google_ads_customer_id,
                analysis_type="audit",
                analyzer_name="search_terms",
                start_date=datetime.now(timezone.utc),
                end_date=datetime.now(timezone.utc),
                status="completed",
                total_recommendations=3,
                critical_issues=1,
                potential_cost_savings=50.0,
                result_data={
                    "recommendations": [{"id": "rec2", "type": "cost_reduction"}]
                },
            )

            session.add(record1)
            session.add(record2)
            await session.commit()

        # Get audit results
        results = await api_repository.get_audit_results(audit_id)
        assert results is not None
        assert results["audit_id"] == audit_id
        assert results["summary"]["total_recommendations"] == 8
        assert results["summary"]["critical_issues"] == 3
        assert results["summary"]["potential_savings"] == 150.0
        assert len(results["analyzers"]) == 2

    @pytest.mark.asyncio
    async def test_get_analyzer_result_not_found(self, api_repository):
        """Test getting analyzer result for non-existent audit."""
        result = await api_repository.get_analyzer_result(
            "non-existent", "keyword_match"
        )
        assert result is None

    @pytest.mark.asyncio
    async def test_get_analyzer_result_not_in_audit(
        self, api_repository, test_customer, test_user
    ):
        """Test getting analyzer result for analyzer not in audit."""
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match"],  # Only includes keyword_match
            config={},
            user_id=test_user.id,
        )

        result = await api_repository.get_analyzer_result(audit_id, "search_terms")
        assert result is None

    @pytest.mark.asyncio
    async def test_get_analyzer_result_pending(
        self, api_repository, test_customer, test_user
    ):
        """Test getting analyzer result when no analysis record exists yet."""
        audit_id = await api_repository.create_audit(
            customer_id=test_customer.id,
            name="Test Audit",
            analyzers=["keyword_match"],
            config={},
            user_id=test_user.id,
        )

        result = await api_repository.get_analyzer_result(audit_id, "keyword_match")
        assert result is not None
        assert result["status"] == "pending"
        assert result["recommendations"] == []
        assert result["metrics"]["items_analyzed"] == 0


class TestValidationAndEdgeCases:
    """Test validation and edge cases."""

    @pytest.mark.asyncio
    async def test_model_validation_google_ads_id(self, session_local):
        """Test Google Ads customer ID validation."""
        async with session_local() as session:
            # First create a user
            user = User(
                email="test@example.com", name="Test User", user_type="individual"
            )
            session.add(user)
            await session.commit()
            await session.refresh(user)

            # Valid ID
            customer = Customer(
                name="Test Customer",
                google_ads_customer_id="1234567890",
                user_id=user.id,
            )
            session.add(customer)
            await session.commit()

            # Test validation during update
            customer.google_ads_customer_id = "123-456-7890"  # With hyphens
            await session.commit()
            assert (
                customer.google_ads_customer_id == "1234567890"
            )  # Stored without hyphens

    @pytest.mark.asyncio
    async def test_audit_status_validation(
        self, session_local, test_customer, test_user
    ):
        """Test audit status validation."""
        async with session_local() as session:
            audit = Audit(
                customer_id=test_customer.id,
                user_id=test_user.id,
                name="Test Audit",
                analyzers=["keyword_match"],
                config={},
                status="pending",
            )
            session.add(audit)
            await session.commit()

            # Test invalid status
            with pytest.raises(ValueError, match="Invalid audit status"):
                audit.status = "invalid_status"
                await session.commit()

    @pytest.mark.asyncio
    async def test_report_format_validation(
        self, session_local, test_customer, test_user
    ):
        """Test report format validation."""
        # Create audit first
        async with session_local() as session:
            audit = Audit(
                customer_id=test_customer.id,
                user_id=test_user.id,
                name="Test Audit",
                analyzers=["keyword_match"],
                config={},
            )
            session.add(audit)
            await session.commit()
            await session.refresh(audit)

            # Test valid format
            report = Report(
                audit_id=audit.id,
                user_id=test_user.id,
                format="pdf",
                template="executive_summary",
            )
            session.add(report)
            await session.commit()

            # Test invalid format
            with pytest.raises(ValueError, match="Invalid report format"):
                report.format = "invalid_format"
                await session.commit()
