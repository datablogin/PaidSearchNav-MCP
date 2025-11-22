"""GraphQL Subscription resolvers."""

from typing import AsyncGenerator

import strawberry
from strawberry.types import Info

from paidsearchnav.api.dependencies import get_current_user
from paidsearchnav.core.pubsub import get_pubsub
from paidsearchnav.graphql.types import AuditProgress, AuditStatus
from paidsearchnav.services import audit_service


@strawberry.type
class Subscription:
    """Root Subscription type."""

    @strawberry.subscription
    async def audit_progress(
        self, info: Info, audit_id: strawberry.ID
    ) -> AsyncGenerator[AuditProgress, None]:
        """Subscribe to real-time audit progress updates."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Verify user has access to this audit
        audit = await audit_service.get_by_id(audit_id)
        if not audit:
            raise Exception("Audit not found")

        # Get pubsub instance
        pubsub = get_pubsub()
        channel = f"audit_progress:{audit_id}"

        # Subscribe to updates
        async with pubsub.subscribe(channel) as subscriber:
            async for message in subscriber:
                # Parse message and yield progress update
                progress_data = message.get("data", {})

                yield AuditProgress(
                    audit_id=audit_id,
                    status=AuditStatus(progress_data.get("status", "in_progress")),
                    current_analyzer=progress_data.get("current_analyzer"),
                    progress_percentage=progress_data.get("progress_percentage", 0.0),
                    message=progress_data.get("message"),
                    completed_analyzers=progress_data.get("completed_analyzers", 0),
                    total_analyzers=progress_data.get("total_analyzers", 0),
                )

                # Check if audit is complete
                if progress_data.get("status") in ["completed", "failed", "cancelled"]:
                    break
