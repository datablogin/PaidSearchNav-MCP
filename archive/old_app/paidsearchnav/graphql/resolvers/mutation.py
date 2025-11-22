"""GraphQL Mutation resolvers."""

import logging

import strawberry
from strawberry.types import Info

from paidsearchnav.api.dependencies import get_current_user
from paidsearchnav.core.exceptions import ValidationError
from paidsearchnav.graphql.types import (
    Audit,
    AuditStatus,
    ScheduleAuditInput,
    ScheduledJob,
    TriggerAuditInput,
)
from paidsearchnav.services import audit_service, scheduler_service

logger = logging.getLogger(__name__)


@strawberry.type
class Mutation:
    """Root Mutation type."""

    @strawberry.mutation
    async def trigger_audit(self, info: Info, input: TriggerAuditInput) -> Audit:
        """Trigger a new audit for a customer."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        try:
            # Create audit
            audit_data = await audit_service.create_audit(
                customer_id=input.customer_id,
                analyzers=input.analyzers,
                force_refresh=input.force_refresh,
                user_id=user["sub"],
            )

            # Trigger async processing
            await audit_service.start_audit(audit_data.id)

            return Audit(
                id=audit_data.id,
                customer_id=audit_data.customer_id,
                status=AuditStatus.IN_PROGRESS,
                created_at=audit_data.created_at,
                started_at=audit_data.started_at,
                completed_at=audit_data.completed_at,
                error_message=audit_data.error_message,
                total_analyzers=audit_data.total_analyzers,
                completed_analyzers=audit_data.completed_analyzers,
            )

        except ValidationError as e:
            # Log the actual error for debugging
            logger.error(f"Validation error in trigger_audit: {str(e)}")
            raise Exception("Invalid input parameters provided")
        except Exception as e:
            # Log the actual error for debugging
            logger.error(f"Error in trigger_audit: {str(e)}", exc_info=True)
            raise Exception("Failed to trigger audit. Please try again later.")

    @strawberry.mutation
    async def schedule_audit(
        self, info: Info, input: ScheduleAuditInput
    ) -> ScheduledJob:
        """Schedule an audit for future execution."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        try:
            # Create scheduled job
            job_data = await scheduler_service.schedule_audit(
                customer_id=input.customer_id,
                schedule_at=input.schedule_at,
                recurrence=input.recurrence,
                analyzers=input.analyzers,
                user_id=user["sub"],
            )

            return ScheduledJob(
                id=job_data.id,
                job_type=job_data.job_type,
                status=job_data.status,
                scheduled_at=job_data.scheduled_at,
                created_at=job_data.created_at,
                updated_at=job_data.updated_at,
                payload=job_data.payload,
                recurrence=job_data.recurrence,
                next_run=job_data.next_run,
                last_run=job_data.last_run,
                error_count=job_data.error_count,
                last_error=job_data.last_error,
                customer_id=input.customer_id,
            )

        except ValidationError as e:
            raise Exception(f"Validation error: {str(e)}")
        except Exception as e:
            # Log the actual error for debugging
            logger.error(f"Error in schedule_audit: {str(e)}", exc_info=True)
            raise Exception("Failed to schedule audit. Please try again later.")

    @strawberry.mutation
    async def cancel_audit(self, info: Info, audit_id: strawberry.ID) -> Audit:
        """Cancel a running audit."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        try:
            # Cancel audit
            audit_data = await audit_service.cancel_audit(
                audit_id=audit_id, user_id=user["sub"]
            )

            return Audit(
                id=audit_data.id,
                customer_id=audit_data.customer_id,
                status=AuditStatus.CANCELLED,
                created_at=audit_data.created_at,
                started_at=audit_data.started_at,
                completed_at=audit_data.completed_at,
                error_message=audit_data.error_message,
                total_analyzers=audit_data.total_analyzers,
                completed_analyzers=audit_data.completed_analyzers,
            )

        except ValidationError as e:
            raise Exception(f"Validation error: {str(e)}")
        except Exception as e:
            # Log the actual error for debugging
            logger.error(f"Error in cancel_audit: {str(e)}", exc_info=True)
            raise Exception("Failed to cancel audit. Please try again later.")
