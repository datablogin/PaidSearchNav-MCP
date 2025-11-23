"""Tests for service layer business logic."""

from unittest.mock import AsyncMock, MagicMock

import pytest

from paidsearchnav_mcp.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from paidsearchnav_mcp.services import (
    AnalysisService,
    AuditService,
    CustomerService,
    RecommendationService,
    SchedulerService,
)


@pytest.fixture
def mock_repository():
    """Create a mock repository."""
    return AsyncMock()


@pytest.fixture
def customer_service(mock_repository):
    """Create CustomerService with mock repository."""
    return CustomerService(mock_repository)


@pytest.fixture
def audit_service(mock_repository):
    """Create AuditService with mock repository."""
    return AuditService(mock_repository)


@pytest.fixture
def analysis_service(mock_repository):
    """Create AnalysisService with mock repository."""
    return AnalysisService(mock_repository)


@pytest.fixture
def recommendation_service(mock_repository):
    """Create RecommendationService with mock repository."""
    return RecommendationService(mock_repository)


@pytest.fixture
def scheduler_service(mock_repository):
    """Create SchedulerService with mock repository."""
    return SchedulerService(mock_repository)


class TestCustomerService:
    """Tests for CustomerService."""

    async def test_get_by_id_success(self, customer_service, mock_repository):
        """Test successful customer retrieval by ID."""
        # Setup
        customer_id = "test-customer-123"
        user_id = "test-user-456"
        expected_customer = {
            "id": customer_id,
            "name": "Test Customer",
            "email": "test@example.com",
        }

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_customer.return_value = expected_customer

        # Execute
        result = await customer_service.get_by_id(customer_id, user_id)

        # Assert
        assert result == expected_customer
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, customer_id
        )
        mock_repository.get_customer.assert_called_once_with(customer_id)

    async def test_get_by_id_validation_error(self, customer_service):
        """Test validation error for empty customer ID."""
        with pytest.raises(ValidationError, match="Customer ID is required"):
            await customer_service.get_by_id("", "user-123")

        with pytest.raises(ValidationError, match="User ID is required"):
            await customer_service.get_by_id("customer-123", "")

    async def test_get_by_id_authorization_error(
        self, customer_service, mock_repository
    ):
        """Test authorization error when user has no access."""
        mock_repository.user_has_customer_access.return_value = False

        with pytest.raises(
            AuthorizationError,
            match="You don't have permission to access this customer",
        ):
            await customer_service.get_by_id("customer-123", "user-456")

    async def test_get_by_id_not_found(self, customer_service, mock_repository):
        """Test resource not found error."""
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_customer.return_value = None

        with pytest.raises(
            ResourceNotFoundError, match="Customer customer-123 not found"
        ):
            await customer_service.get_by_id("customer-123", "user-456")

    async def test_get_by_ids_success(self, customer_service, mock_repository):
        """Test successful retrieval of multiple customers."""
        # Setup
        customer_ids = ["customer-1", "customer-2"]
        user_id = "user-123"
        # Mock accessible customers (including more than requested)
        accessible_customers = [
            {"id": "customer-1", "name": "Customer 1"},
            {"id": "customer-2", "name": "Customer 2"},
            {"id": "customer-3", "name": "Customer 3"},  # Not requested
        ]

        mock_repository.get_customers_for_user.return_value = accessible_customers

        # Execute
        result = await customer_service.get_by_ids(customer_ids, user_id)

        # Assert
        assert len(result) == 2
        assert result[0]["id"] == "customer-1"
        assert result[1]["id"] == "customer-2"
        # Verify the new optimized call pattern
        mock_repository.get_customers_for_user.assert_called_once_with(
            user_id=user_id,
            offset=0,
            limit=100,  # ServiceConfig.MAX_LIMIT
        )

    async def test_get_by_ids_empty_list(self, customer_service):
        """Test empty list handling."""
        result = await customer_service.get_by_ids([], "user-123")
        assert result == []

    async def test_get_filtered_success(self, customer_service, mock_repository):
        """Test successful filtered customer retrieval."""
        # Setup
        user_id = "user-123"
        customers = [
            {"id": "customer-1", "name": "Active Customer", "is_active": True},
            {"id": "customer-2", "name": "Inactive Customer", "is_active": False},
        ]

        mock_repository.get_customers_for_user.return_value = customers
        mock_repository.count_customers_for_user.return_value = 2

        # Execute
        result, total = await customer_service.get_filtered(user_id)

        # Assert
        assert len(result) == 2
        assert total == 2
        mock_repository.get_customers_for_user.assert_called_once_with(
            user_id=user_id, offset=0, limit=20
        )

    async def test_get_filtered_with_filters(self, customer_service, mock_repository):
        """Test filtered customer retrieval with filters."""
        # Setup
        user_id = "user-123"
        customers = [
            {"id": "customer-1", "name": "Active Customer", "is_active": True},
            {"id": "customer-2", "name": "Inactive Customer", "is_active": False},
        ]
        filters = {"is_active": True}

        mock_repository.get_customers_for_user.return_value = customers
        mock_repository.count_customers_for_user.return_value = 2

        # Execute
        result, total = await customer_service.get_filtered(user_id, filters=filters)

        # Assert
        assert len(result) == 1
        assert result[0]["name"] == "Active Customer"
        assert total == 2  # Total count doesn't change with client-side filtering

    async def test_get_filtered_validation_error(self, customer_service):
        """Test validation errors in get_filtered."""
        with pytest.raises(ValidationError, match="User ID is required"):
            await customer_service.get_filtered("")

        with pytest.raises(ValidationError, match="Offset cannot be negative"):
            await customer_service.get_filtered("user-123", offset=-1)

        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            await customer_service.get_filtered("user-123", limit=0)

        with pytest.raises(ValidationError, match="Limit must be between 1 and 100"):
            await customer_service.get_filtered("user-123", limit=101)


class TestAuditService:
    """Tests for AuditService."""

    async def test_get_by_id_success(self, audit_service, mock_repository):
        """Test successful audit retrieval by ID."""
        # Setup
        audit_id = "audit-123"
        user_id = "user-456"
        audit = {
            "id": audit_id,
            "customer_id": "customer-789",
            "name": "Test Audit",
            "status": "completed",
        }

        mock_repository.get_audit.return_value = audit
        mock_repository.user_has_customer_access.return_value = True

        # Execute
        result = await audit_service.get_by_id(audit_id, user_id)

        # Assert
        assert result == audit
        mock_repository.get_audit.assert_called_once_with(audit_id)
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, audit["customer_id"]
        )

    async def test_get_by_id_not_found(self, audit_service, mock_repository):
        """Test audit not found error."""
        mock_repository.get_audit.return_value = None

        with pytest.raises(ResourceNotFoundError, match="Audit audit-123 not found"):
            await audit_service.get_by_id("audit-123", "user-456")

    async def test_get_by_id_authorization_error(self, audit_service, mock_repository):
        """Test authorization error for audit access."""
        audit = {"id": "audit-123", "customer_id": "customer-789"}
        mock_repository.get_audit.return_value = audit
        mock_repository.user_has_customer_access.return_value = False

        with pytest.raises(
            AuthorizationError, match="You don't have permission to access this audit"
        ):
            await audit_service.get_by_id("audit-123", "user-456")

    async def test_create_audit_success(self, audit_service, mock_repository):
        """Test successful audit creation."""
        # Setup
        customer_id = "customer-123"
        name = "Test Audit"
        analyzers = ["keyword_match", "search_terms"]
        user_id = "user-456"
        config = {"date_range": 30}

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.create_audit.return_value = "audit-789"

        # Execute
        result = await audit_service.create_audit(
            customer_id=customer_id,
            name=name,
            analyzers=analyzers,
            user_id=user_id,
            config=config,
        )

        # Assert
        assert result == "audit-789"
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, customer_id
        )
        mock_repository.create_audit.assert_called_once_with(
            customer_id=customer_id,
            name=name,
            analyzers=analyzers,
            config=config,
            user_id=user_id,
        )

    async def test_create_audit_validation_errors(self, audit_service):
        """Test validation errors in audit creation."""
        with pytest.raises(ValidationError, match="Customer ID is required"):
            await audit_service.create_audit("", "name", ["analyzer"], "user")

        with pytest.raises(ValidationError, match="Audit name is required"):
            await audit_service.create_audit("customer", "", ["analyzer"], "user")

        with pytest.raises(ValidationError, match="At least one analyzer is required"):
            await audit_service.create_audit("customer", "name", [], "user")

        with pytest.raises(ValidationError, match="User ID is required"):
            await audit_service.create_audit("customer", "name", ["analyzer"], "")

    async def test_cancel_audit_success(self, audit_service, mock_repository):
        """Test successful audit cancellation."""
        # Setup
        audit_id = "audit-123"
        user_id = "user-456"
        audit = {
            "id": audit_id,
            "customer_id": "customer-789",
            "status": "running",
        }

        mock_repository.get_audit.return_value = audit
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.cancel_audit.return_value = True

        # Execute
        result = await audit_service.cancel_audit(audit_id, user_id)

        # Assert
        assert result is True
        mock_repository.cancel_audit.assert_called_once_with(audit_id)

    async def test_cancel_audit_invalid_status(self, audit_service, mock_repository):
        """Test cancellation error for invalid status."""
        audit = {
            "id": "audit-123",
            "customer_id": "customer-789",
            "status": "completed",
        }

        mock_repository.get_audit.return_value = audit
        mock_repository.user_has_customer_access.return_value = True

        with pytest.raises(
            ValidationError, match="Can only cancel pending or running audits"
        ):
            await audit_service.cancel_audit("audit-123", "user-456")


class TestAnalysisService:
    """Tests for AnalysisService."""

    async def test_get_by_audit_ids_success(self, analysis_service, mock_repository):
        """Test successful analysis retrieval by audit IDs."""
        # Setup
        audit_ids = ["audit-1", "audit-2"]
        user_id = "user-123"
        audits = [
            {"id": "audit-1", "customer_id": "customer-1"},
            {"id": "audit-2", "customer_id": "customer-1"},
        ]
        analysis_results = [
            {"audit_id": "audit-1", "summary": {"total_recommendations": 5}},
            {"audit_id": "audit-2", "summary": {"total_recommendations": 3}},
        ]

        mock_repository.get_audit.side_effect = audits
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_audit_results.side_effect = analysis_results

        # Execute
        result = await analysis_service.get_by_audit_ids(audit_ids, user_id)

        # Assert
        assert len(result) == 2
        assert "audit-1" in result
        assert "audit-2" in result
        assert result["audit-1"]["summary"]["total_recommendations"] == 5

    async def test_get_by_audit_ids_empty_list(self, analysis_service):
        """Test empty list handling."""
        result = await analysis_service.get_by_audit_ids([], "user-123")
        assert result == {}

    async def test_get_filtered_success(self, analysis_service, mock_repository):
        """Test successful filtered analysis retrieval."""
        # Setup
        user_id = "user-123"
        customer_id = "customer-456"
        mock_analysis = MagicMock()
        mock_analysis.customer_id = customer_id
        mock_analysis.model_dump.return_value = {
            "analysis_id": "analysis-1",
            "customer_id": customer_id,
            "analysis_type": "keyword_match",
        }

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.list_analyses.return_value = [mock_analysis]

        # Execute
        result = await analysis_service.get_filtered(
            user_id=user_id, customer_id=customer_id
        )

        # Assert
        assert len(result) == 1
        assert result[0]["analysis_id"] == "analysis-1"
        # Called twice: once for customer access check, once for analysis access check
        assert mock_repository.user_has_customer_access.call_count == 2


class TestRecommendationService:
    """Tests for RecommendationService."""

    async def test_get_by_audit_ids_success(
        self, recommendation_service, mock_repository
    ):
        """Test successful recommendation retrieval by audit IDs."""
        # Setup
        audit_ids = ["audit-1"]
        user_id = "user-123"
        audit = {"id": "audit-1", "customer_id": "customer-1"}
        audit_results = {
            "audit_id": "audit-1",
            "analyzers": [{"analyzer_name": "keyword_match"}],
        }
        analyzer_result = {
            "audit_id": "audit-1",
            "analyzer": "keyword_match",
            "recommendations": [
                {"id": "rec-1", "type": "optimization", "priority": "high"},
                {"id": "rec-2", "type": "cost_reduction", "priority": "medium"},
            ],
        }

        mock_repository.get_audit.return_value = audit
        mock_repository.user_has_customer_access.return_value = True
        mock_repository.get_audit_results.return_value = audit_results
        mock_repository.get_analyzer_result.return_value = analyzer_result

        # Execute
        result = await recommendation_service.get_by_audit_ids(audit_ids, user_id)

        # Assert
        assert len(result) == 1
        assert "audit-1" in result
        assert len(result["audit-1"]) == 2
        assert result["audit-1"][0]["id"] == "rec-1"

    async def test_get_filtered_success(self, recommendation_service, mock_repository):
        """Test successful filtered recommendation retrieval."""
        # Setup
        user_id = "user-123"
        customer_id = "customer-456"
        audits = [{"id": "audit-1", "customer_id": customer_id}]
        audit_results = {
            "audit_id": "audit-1",
            "analyzers": [{"analyzer_name": "keyword_match"}],
        }
        analyzer_result = {
            "recommendations": [
                {"id": "rec-1", "type": "optimization", "priority": "high"},
                {"id": "rec-2", "type": "cost_reduction", "priority": "medium"},
            ],
        }

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.list_audits.return_value = (audits, 1)
        mock_repository.get_audit.return_value = audits[0]
        mock_repository.get_audit_results.return_value = audit_results
        mock_repository.get_analyzer_result.return_value = analyzer_result

        # Execute
        result = await recommendation_service.get_filtered(
            user_id=user_id, customer_id=customer_id, priority="high"
        )

        # Assert
        assert len(result) == 1
        assert result[0]["priority"] == "high"
        assert result[0]["audit_id"] == "audit-1"


class TestSchedulerService:
    """Tests for SchedulerService."""

    async def test_schedule_audit_success(self, scheduler_service, mock_repository):
        """Test successful audit scheduling."""
        # Setup
        customer_id = "customer-123"
        name = "Weekly Audit"
        cron_expression = "0 0 * * 0"
        analyzers = ["keyword_match"]
        user_id = "user-456"

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.create_schedule.return_value = "schedule-789"

        # Execute
        result = await scheduler_service.schedule_audit(
            customer_id=customer_id,
            name=name,
            cron_expression=cron_expression,
            analyzers=analyzers,
            user_id=user_id,
        )

        # Assert
        assert result == "schedule-789"
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, customer_id
        )
        mock_repository.create_schedule.assert_called_once_with(
            customer_id=customer_id,
            name=name,
            cron_expression=cron_expression,
            analyzers=analyzers,
            config={},
            enabled=True,
            user_id=user_id,
        )

    async def test_schedule_audit_validation_errors(self, scheduler_service):
        """Test validation errors in audit scheduling."""
        with pytest.raises(ValidationError, match="Customer ID is required"):
            await scheduler_service.schedule_audit(
                "", "name", "0 0 * * 0", ["analyzer"], "user"
            )

        with pytest.raises(ValidationError, match="Schedule name is required"):
            await scheduler_service.schedule_audit(
                "customer", "", "0 0 * * 0", ["analyzer"], "user"
            )

        with pytest.raises(ValidationError, match="Cron expression is required"):
            await scheduler_service.schedule_audit(
                "customer", "name", "", ["analyzer"], "user"
            )

        with pytest.raises(ValidationError, match="At least one analyzer is required"):
            await scheduler_service.schedule_audit(
                "customer", "name", "0 0 * * 0", [], "user"
            )

        with pytest.raises(ValidationError, match="Invalid cron expression format"):
            await scheduler_service.schedule_audit(
                "customer", "name", "invalid cron", ["analyzer"], "user"
            )

    async def test_get_schedule_success(self, scheduler_service, mock_repository):
        """Test successful schedule retrieval."""
        # Setup
        schedule_id = "schedule-123"
        user_id = "user-456"
        schedule = {
            "id": schedule_id,
            "customer_id": "customer-789",
            "name": "Weekly Audit",
        }

        mock_repository.get_schedule.return_value = schedule
        mock_repository.user_has_customer_access.return_value = True

        # Execute
        result = await scheduler_service.get_schedule(schedule_id, user_id)

        # Assert
        assert result == schedule
        mock_repository.get_schedule.assert_called_once_with(schedule_id)
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, schedule["customer_id"]
        )

    async def test_list_schedules_success(self, scheduler_service, mock_repository):
        """Test successful schedule listing."""
        # Setup
        customer_id = "customer-123"
        user_id = "user-456"
        schedules = [
            {"id": "schedule-1", "name": "Weekly Audit"},
            {"id": "schedule-2", "name": "Monthly Audit"},
        ]

        mock_repository.user_has_customer_access.return_value = True
        mock_repository.list_schedules.return_value = (schedules, 2)

        # Execute
        result = await scheduler_service.list_schedules(customer_id, user_id)

        # Assert
        assert len(result) == 2
        assert result[0]["name"] == "Weekly Audit"
        mock_repository.user_has_customer_access.assert_called_once_with(
            user_id, customer_id
        )
        mock_repository.list_schedules.assert_called_once_with(
            customer_id=customer_id, limit=20
        )
