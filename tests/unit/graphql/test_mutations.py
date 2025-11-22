"""Tests for GraphQL mutations."""

from datetime import datetime
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.core.exceptions import ValidationError
from paidsearchnav_mcp.graphql.resolvers.mutation import Mutation
from paidsearchnav_mcp.graphql.types import (
    AuditStatus,
    ScheduleAuditInput,
    TriggerAuditInput,
)


class TestGraphQLMutations:
    """Test GraphQL mutation resolvers."""

    @pytest.fixture
    def mock_info(self):
        """Create mock Info object."""
        mock_request = Mock()
        mock_context = {"request": mock_request, "dataloaders": Mock()}
        return Mock(context=mock_context)

    @pytest.mark.asyncio
    async def test_trigger_audit_success(self, mock_info):
        """Test successfully triggering an audit."""
        mock_user = {"sub": "user123"}
        mock_audit_data = Mock(
            id="audit1",
            customer_id="cust1",
            status=AuditStatus.IN_PROGRESS,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=None,
            error_message=None,
            total_analyzers=5,
            completed_analyzers=0,
        )

        input_data = TriggerAuditInput(
            customer_id="cust1",
            analyzers=["keyword_performance", "ad_copy_effectiveness"],
            force_refresh=True,
        )

        with (
            patch(
                "paidsearchnav.graphql.resolvers.mutation.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.create_audit",
                return_value=mock_audit_data,
            ) as mock_create,
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.start_audit",
                return_value=None,
            ) as mock_start,
        ):
            mutation = Mutation()
            result = await mutation.trigger_audit(mock_info, input_data)

            assert result.id == "audit1"
            assert result.customer_id == "cust1"
            assert result.status == AuditStatus.IN_PROGRESS
            assert result.total_analyzers == 5

            # Verify service calls
            mock_create.assert_called_once_with(
                customer_id="cust1",
                analyzers=["keyword_performance", "ad_copy_effectiveness"],
                force_refresh=True,
                user_id="user123",
            )
            mock_start.assert_called_once_with("audit1")

    @pytest.mark.asyncio
    async def test_trigger_audit_validation_error(self, mock_info):
        """Test triggering audit with validation error."""
        mock_user = {"sub": "user123"}

        input_data = TriggerAuditInput(
            customer_id="invalid", analyzers=None, force_refresh=False
        )

        with (
            patch(
                "paidsearchnav.graphql.resolvers.mutation.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.create_audit",
                side_effect=ValidationError("Invalid customer ID"),
            ),
        ):
            mutation = Mutation()

            with pytest.raises(Exception) as exc_info:
                await mutation.trigger_audit(mock_info, input_data)

            assert "Invalid input parameters provided" in str(exc_info.value)

    @pytest.mark.asyncio
    async def test_schedule_audit_success(self, mock_info):
        """Test successfully scheduling an audit."""
        mock_user = {"sub": "user123"}
        schedule_time = datetime.now()

        mock_job_data = Mock(
            id="job1",
            job_type="audit",
            status="scheduled",
            scheduled_at=schedule_time,
            created_at=datetime.now(),
            updated_at=datetime.now(),
            payload='{"customer_id": "cust1"}',
            recurrence="0 9 * * MON",
            next_run=schedule_time,
            last_run=None,
            error_count=0,
            last_error=None,
        )

        input_data = ScheduleAuditInput(
            customer_id="cust1",
            schedule_at=schedule_time,
            recurrence="0 9 * * MON",  # Every Monday at 9 AM
            analyzers=["keyword_performance"],
        )

        with (
            patch(
                "paidsearchnav.graphql.resolvers.mutation.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.scheduler_service.schedule_audit",
                return_value=mock_job_data,
            ) as mock_schedule,
        ):
            mutation = Mutation()
            result = await mutation.schedule_audit(mock_info, input_data)

            assert result.id == "job1"
            assert result.job_type == "audit"
            assert result.status == "scheduled"
            assert result.recurrence == "0 9 * * MON"
            assert result.customer_id == "cust1"

            # Verify service call
            mock_schedule.assert_called_once_with(
                customer_id="cust1",
                schedule_at=schedule_time,
                recurrence="0 9 * * MON",
                analyzers=["keyword_performance"],
                user_id="user123",
            )

    @pytest.mark.asyncio
    async def test_cancel_audit_success(self, mock_info):
        """Test successfully cancelling an audit."""
        mock_user = {"sub": "user123"}
        mock_audit_data = Mock(
            id="audit1",
            customer_id="cust1",
            status=AuditStatus.CANCELLED,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            error_message="Cancelled by user",
            total_analyzers=5,
            completed_analyzers=2,
        )

        with (
            patch(
                "paidsearchnav.graphql.resolvers.mutation.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.cancel_audit",
                return_value=mock_audit_data,
            ) as mock_cancel,
        ):
            mutation = Mutation()
            result = await mutation.cancel_audit(mock_info, audit_id="audit1")

            assert result.id == "audit1"
            assert result.status == AuditStatus.CANCELLED
            assert result.error_message == "Cancelled by user"
            assert result.completed_analyzers == 2

            # Verify service call
            mock_cancel.assert_called_once_with(audit_id="audit1", user_id="user123")
