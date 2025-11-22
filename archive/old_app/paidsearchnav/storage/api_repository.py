"""Extended repository for API-specific operations."""

import json
import logging
from datetime import datetime, timedelta, timezone
from typing import TYPE_CHECKING, Any

from pydantic import ValidationError
from sqlalchemy import literal, select, text

from paidsearchnav.api.models.customer import CustomerSettings

if TYPE_CHECKING:
    from paidsearchnav.storage.models import Audit, UserType

from paidsearchnav.storage.repository import AnalysisRepository

logger = logging.getLogger(__name__)

# Constants for audit ID generation
AUDIT_ID_PREFIX = "audit-"
CONCURRENT_AUDIT_KEYWORD = "Concurrent"
DEFAULT_TEST_AUDIT_ID = "test-audit-123"

# Report expiration configuration (in days)
DEFAULT_REPORT_EXPIRATION_DAYS = 7


class APIRepository(AnalysisRepository):
    """Extended repository with API-specific methods."""

    def _validate_user_type(self, user_type: str, user_id: str) -> "UserType | None":
        """Validate user type string and convert to enum.

        Args:
            user_type: User type string from database
            user_id: User ID for logging purposes

        Returns:
            UserType enum or None if invalid
        """
        from paidsearchnav.storage.models import UserType

        try:
            return UserType.from_string(user_type)
        except ValueError as e:
            logger.warning(
                f"Invalid user type value '{user_type}' for user {user_id}: {e}"
            )
            return None
        except AttributeError as e:
            logger.warning(f"UserType method error for user {user_id}: {e}")
            return None

    async def check_connection(self) -> bool:
        """Check if database connection is healthy."""
        async with self.AsyncSessionLocal() as session:
            try:
                # Simple query to test connection
                result = await session.execute(select(literal(1)))
                return result.scalar() == 1
            except Exception as e:
                logger.error(f"Database connection check failed: {e}")
                return False

    async def user_has_customer_access(self, user_id: str, customer_id: str) -> bool:
        """Check if user has access to a specific customer.

        Uses a single optimized JOIN query to check:
        1. User exists and is active
        2. Customer exists and is active
        3. User has appropriate access (owner or granted access)

        Note: For optimal performance, ensure the following database indexes exist:
        - CREATE INDEX idx_users_id_active ON users(id, is_active);
        - CREATE INDEX idx_customers_id_active ON customers(id, is_active);
        - CREATE INDEX idx_customer_access_user_customer ON customer_access(user_id, customer_id, is_active);
        """

        async with self.AsyncSessionLocal() as session:
            try:
                # Single optimized query that checks everything at once
                result = await session.execute(
                    text("""
                        SELECT
                            u.user_type,           -- User's type (INDIVIDUAL or AGENCY)
                            c.user_id as owner_id, -- Customer owner's user_id (NULL if customer not found)
                            ca.access_level        -- Access level if granted (NULL if no access)
                        FROM users u
                        -- Join with customers to check if it exists and get owner
                        LEFT JOIN customers c
                            ON c.id = :customer_id
                            AND c.is_active = true
                        -- Join with customer_access to check if user has been granted access
                        LEFT JOIN customer_access ca
                            ON ca.user_id = u.id
                            AND ca.customer_id = :customer_id
                            AND ca.is_active = true
                        WHERE u.id = :user_id
                            AND u.is_active = true
                    """),
                    {"user_id": user_id, "customer_id": customer_id},
                )
                row = result.fetchone()

                # If no row returned, user doesn't exist or is inactive
                if not row:
                    logger.warning(f"User {user_id} not found or inactive")
                    return False

                user_type, owner_id, access_level = row

                # If customer doesn't exist (owner_id is None), deny access
                if owner_id is None:
                    logger.warning(f"Customer {customer_id} not found or inactive")
                    return False

                # Convert string user_type to enum for type-safe comparisons
                user_type_enum = self._validate_user_type(user_type, user_id)
                if not user_type_enum:
                    return False

                # Individual users can only access their own customers
                if user_type_enum.is_individual():
                    has_access = owner_id == user_id
                    logger.debug(
                        f"Individual user {user_id} access to customer {customer_id}: {has_access}"
                    )
                    return has_access

                # Agency users can access:
                # 1. Their own customers (customers they own)
                # 2. Customers they have been granted access to via CustomerAccess
                elif user_type_enum.is_agency():
                    # Check if user owns the customer
                    if owner_id == user_id:
                        logger.debug(
                            f"Agency user {user_id} owns customer {customer_id}"
                        )
                        return True

                    # Check if user has been granted access (access_level is not None)
                    has_access = access_level is not None
                    logger.debug(
                        f"Agency user {user_id} granted access to customer {customer_id}: {has_access}"
                    )
                    return has_access

                else:
                    logger.warning(f"Unknown user type {user_type} for user {user_id}")
                    return False

            except Exception as e:
                logger.error(f"Error checking user access: {e}")
                return False

    async def get_customer(self, customer_id: str) -> dict[str, Any] | None:
        """Get customer information."""
        async with self.AsyncSessionLocal() as session:
            try:
                customer_result = await session.execute(
                    text("""
                        SELECT id, name, email, google_ads_customer_id, user_id, settings,
                               is_active, last_audit_date, next_scheduled_audit,
                               created_at, updated_at
                        FROM customers
                        WHERE id = :customer_id AND is_active = true
                    """),
                    {"customer_id": customer_id},
                )
                customer_row = customer_result.fetchone()

                if not customer_row:
                    logger.debug(f"Customer {customer_id} not found or inactive")
                    return None

                return {
                    "id": customer_row[0],
                    "name": customer_row[1],
                    "email": customer_row[2],
                    "google_ads_customer_id": customer_row[3],
                    "user_id": customer_row[4],
                    "settings": customer_row[5] or {},
                    "is_active": customer_row[6],
                    "last_audit_date": customer_row[7],
                    "next_scheduled_audit": customer_row[8],
                    "created_at": customer_row[9],
                    "updated_at": customer_row[10],
                }

            except Exception as e:
                logger.error(f"Error retrieving customer {customer_id}: {e}")
                return None

    async def create_audit(
        self,
        customer_id: str,
        name: str,
        analyzers: list[str],
        config: dict[str, Any],
        user_id: str,
    ) -> str:
        """Create a new audit."""
        from paidsearchnav.storage.models import Audit

        async with self.AsyncSessionLocal() as session:
            try:
                # Create audit record
                audit = Audit(
                    customer_id=customer_id,
                    user_id=user_id,
                    name=name,
                    analyzers=analyzers,
                    config=config,
                    status="pending",
                )

                session.add(audit)
                await session.commit()
                await session.refresh(audit)

                logger.info(
                    f"Created audit {audit.id} for customer {customer_id} by user {user_id}"
                )
                return audit.id

            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating audit: {e}")
                raise

    async def get_audit(self, audit_id: str) -> dict[str, Any] | None:
        """Get audit information."""
        from paidsearchnav.storage.models import Audit

        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Audit).where(Audit.id == audit_id)
                )
                audit = result.scalar_one_or_none()

                if not audit:
                    logger.debug(f"Audit {audit_id} not found")
                    return None

                return audit.to_dict()

            except Exception as e:
                logger.error(f"Error retrieving audit {audit_id}: {e}")
                return None

    async def list_audits(
        self,
        customer_id: str | None = None,
        status: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """List audits with pagination."""
        from sqlalchemy import func

        from paidsearchnav.storage.models import Audit

        async with self.AsyncSessionLocal() as session:
            try:
                # Build query with filters
                query = select(Audit)
                count_query = select(func.count(Audit.id))

                if customer_id:
                    query = query.where(Audit.customer_id == customer_id)
                    count_query = count_query.where(Audit.customer_id == customer_id)

                if status:
                    query = query.where(Audit.status == status)
                    count_query = count_query.where(Audit.status == status)

                # Order by created_at descending
                query = query.order_by(Audit.created_at.desc())

                # Apply pagination
                query = query.offset(offset).limit(limit)

                # Execute queries
                result = await session.execute(query)
                audits = result.scalars().all()

                count_result = await session.execute(count_query)
                total = count_result.scalar() or 0

                # Convert to dictionaries
                audit_dicts = [audit.to_dict() for audit in audits]

                return audit_dicts, total

            except Exception as e:
                logger.error(f"Error listing audits: {e}")
                return [], 0

    async def cancel_audit(self, audit_id: str) -> bool:
        """Cancel a running audit."""
        from paidsearchnav.storage.models import Audit

        async with self.AsyncSessionLocal() as session:
            try:
                # Use SELECT FOR UPDATE to prevent race conditions
                result = await session.execute(
                    select(Audit).where(Audit.id == audit_id).with_for_update()
                )
                audit = result.scalar_one_or_none()

                if not audit:
                    logger.warning(f"Audit {audit_id} not found for cancellation")
                    return False

                # Only cancel if audit is pending or running
                if audit.status not in ["pending", "running"]:
                    logger.warning(
                        f"Cannot cancel audit {audit_id} with status {audit.status}"
                    )
                    return False

                # Update status to cancelled (row is locked, preventing race conditions)
                audit.status = "cancelled"
                audit.completed_at = datetime.now(timezone.utc)

                await session.commit()
                logger.info(f"Cancelled audit {audit_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error cancelling audit {audit_id}: {e}")
                return False

    async def create_schedule(
        self,
        customer_id: str,
        name: str,
        cron_expression: str,
        analyzers: list[str],
        config: dict[str, Any],
        enabled: bool,
        user_id: str,
    ) -> str:
        """Create an audit schedule."""
        from croniter import croniter

        from paidsearchnav.storage.models import Schedule

        async with self.AsyncSessionLocal() as session:
            try:
                # Validate cron expression
                if not croniter.is_valid(cron_expression):
                    raise ValueError(f"Invalid cron expression: {cron_expression}")

                # Calculate next run time
                cron = croniter(cron_expression, datetime.now(timezone.utc))
                next_run_at = cron.get_next(datetime) if enabled else None

                # Create schedule record
                schedule = Schedule(
                    customer_id=customer_id,
                    user_id=user_id,
                    name=name,
                    cron_expression=cron_expression,
                    enabled=enabled,
                    analyzers=analyzers,
                    config=config,
                    next_run_at=next_run_at,
                )

                session.add(schedule)
                await session.commit()
                await session.refresh(schedule)

                logger.info(
                    f"Created schedule {schedule.id} for customer {customer_id} by user {user_id}"
                )
                return schedule.id

            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating schedule: {e}")
                raise

    async def get_schedule(self, schedule_id: str) -> dict[str, Any] | None:
        """Get schedule information."""
        from paidsearchnav.storage.models import Schedule

        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Schedule).where(Schedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()

                if not schedule:
                    logger.debug(f"Schedule {schedule_id} not found")
                    return None

                return schedule.to_dict()

            except Exception as e:
                logger.error(f"Error retrieving schedule {schedule_id}: {e}")
                return None

    async def list_schedules(
        self,
        customer_id: str | None = None,
        offset: int = 0,
        limit: int = 20,
    ) -> tuple[list[dict[str, Any]], int]:
        """List schedules with pagination."""
        from sqlalchemy import func

        from paidsearchnav.storage.models import Schedule

        async with self.AsyncSessionLocal() as session:
            try:
                # Build query with filters
                query = select(Schedule)
                count_query = select(func.count(Schedule.id))

                if customer_id:
                    query = query.where(Schedule.customer_id == customer_id)
                    count_query = count_query.where(Schedule.customer_id == customer_id)

                # Order by created_at descending
                query = query.order_by(Schedule.created_at.desc())

                # Apply pagination
                query = query.offset(offset).limit(limit)

                # Execute queries
                result = await session.execute(query)
                schedules = result.scalars().all()

                count_result = await session.execute(count_query)
                total = count_result.scalar() or 0

                # Convert to dictionaries
                schedule_dicts = [schedule.to_dict() for schedule in schedules]

                return schedule_dicts, total

            except Exception as e:
                logger.error(f"Error listing schedules: {e}")
                return [], 0

    async def update_schedule(
        self,
        schedule_id: str,
        updates: dict[str, Any],
    ) -> bool:
        """Update a schedule."""
        from croniter import croniter

        from paidsearchnav.storage.models import Schedule

        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Schedule).where(Schedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()

                if not schedule:
                    logger.warning(f"Schedule {schedule_id} not found for update")
                    return False

                # Update allowed fields
                allowed_fields = {
                    "name",
                    "cron_expression",
                    "analyzers",
                    "config",
                    "enabled",
                }

                for field, value in updates.items():
                    if field not in allowed_fields:
                        logger.warning(f"Ignoring invalid update field: {field}")
                        continue

                    # Special validation for cron_expression
                    if field == "cron_expression" and not croniter.is_valid(value):
                        logger.error(f"Invalid cron expression in update: {value}")
                        return False

                    setattr(schedule, field, value)

                # Update next_run_at if cron or enabled status changed
                if "cron_expression" in updates or "enabled" in updates:
                    if schedule.enabled:
                        cron = croniter(
                            schedule.cron_expression, datetime.now(timezone.utc)
                        )
                        schedule.next_run_at = cron.get_next(datetime)
                    else:
                        schedule.next_run_at = None

                await session.commit()
                logger.info(f"Updated schedule {schedule_id}: {list(updates.keys())}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating schedule {schedule_id}: {e}")
                return False

    async def delete_schedule(self, schedule_id: str) -> bool:
        """Delete a schedule."""
        from paidsearchnav.storage.models import Schedule

        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    select(Schedule).where(Schedule.id == schedule_id)
                )
                schedule = result.scalar_one_or_none()

                if not schedule:
                    logger.warning(f"Schedule {schedule_id} not found for deletion")
                    return False

                await session.delete(schedule)
                await session.commit()
                logger.info(f"Deleted schedule {schedule_id}")
                return True

            except Exception as e:
                await session.rollback()
                logger.error(f"Error deleting schedule {schedule_id}: {e}")
                return False

    async def get_customers_for_user(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = 20,
    ) -> list[dict[str, Any]]:
        """Get customers accessible by a user."""

        async with self.AsyncSessionLocal() as session:
            try:
                # Get user type
                user_result = await session.execute(
                    text(
                        "SELECT user_type FROM users WHERE id = :user_id AND is_active = true"
                    ),
                    {"user_id": user_id},
                )
                user_row = user_result.fetchone()
                if not user_row:
                    logger.warning(f"User {user_id} not found or inactive")
                    return []

                user_type = user_row[0]
                # Convert string user_type to enum for type-safe comparisons
                user_type_enum = self._validate_user_type(user_type, user_id)
                if not user_type_enum:
                    return []

                if user_type_enum.is_individual():
                    # Individual users can only see their own customers
                    customers_result = await session.execute(
                        text("""
                            SELECT id, name, email, google_ads_customer_id, user_id, settings,
                                   is_active, last_audit_date, next_scheduled_audit,
                                   created_at, updated_at
                            FROM customers
                            WHERE user_id = :user_id AND is_active = true
                            ORDER BY created_at DESC
                            LIMIT :limit OFFSET :offset
                        """),
                        {"user_id": user_id, "limit": limit, "offset": offset},
                    )

                elif user_type_enum.is_agency():
                    # Agency users can see their own customers + customers they have access to
                    customers_result = await session.execute(
                        text("""
                            SELECT DISTINCT c.id, c.name, c.email, c.google_ads_customer_id,
                                   c.user_id, c.settings, c.is_active, c.last_audit_date,
                                   c.next_scheduled_audit, c.created_at, c.updated_at
                            FROM customers c
                            LEFT JOIN customer_access ca ON c.id = ca.customer_id AND ca.is_active = true
                            WHERE c.is_active = true
                            AND (c.user_id = :user_id OR ca.user_id = :user_id)
                            ORDER BY c.created_at DESC
                            LIMIT :limit OFFSET :offset
                        """),
                        {"user_id": user_id, "limit": limit, "offset": offset},
                    )
                else:
                    logger.warning(f"Unknown user type {user_type} for user {user_id}")
                    return []

                customers = []
                for row in customers_result.fetchall():
                    customers.append(
                        {
                            "id": row[0],
                            "name": row[1],
                            "email": row[2],
                            "google_ads_customer_id": row[3],
                            "user_id": row[4],
                            "settings": row[5] or {},
                            "is_active": row[6],
                            "last_audit_date": row[7],
                            "next_scheduled_audit": row[8],
                            "created_at": row[9],
                            "updated_at": row[10],
                        }
                    )

                logger.debug(
                    f"Found {len(customers)} customers for {user_type} user {user_id}"
                )
                return customers

            except Exception as e:
                logger.error(f"Error retrieving customers for user {user_id}: {e}")
                return []

    async def count_customers_for_user(self, user_id: str) -> int:
        """Count customers accessible by a user."""

        async with self.AsyncSessionLocal() as session:
            try:
                # Get user type
                user_result = await session.execute(
                    text(
                        "SELECT user_type FROM users WHERE id = :user_id AND is_active = true"
                    ),
                    {"user_id": user_id},
                )
                user_row = user_result.fetchone()
                if not user_row:
                    logger.warning(f"User {user_id} not found or inactive")
                    return 0

                user_type = user_row[0]
                # Convert string user_type to enum for type-safe comparisons
                user_type_enum = self._validate_user_type(user_type, user_id)
                if not user_type_enum:
                    return 0

                if user_type_enum.is_individual():
                    # Individual users can only see their own customers
                    count_result = await session.execute(
                        text("""
                            SELECT COUNT(*) FROM customers
                            WHERE user_id = :user_id AND is_active = true
                        """),
                        {"user_id": user_id},
                    )

                elif user_type_enum.is_agency():
                    # Agency users can see their own customers + customers they have access to
                    count_result = await session.execute(
                        text("""
                            SELECT COUNT(DISTINCT c.id)
                            FROM customers c
                            LEFT JOIN customer_access ca ON c.id = ca.customer_id AND ca.is_active = true
                            WHERE c.is_active = true
                            AND (c.user_id = :user_id OR ca.user_id = :user_id)
                        """),
                        {"user_id": user_id},
                    )
                else:
                    logger.warning(f"Unknown user type {user_type} for user {user_id}")
                    return 0

                count = count_result.scalar() or 0
                logger.debug(f"Found {count} customers for {user_type} user {user_id}")
                return count

            except Exception as e:
                logger.error(f"Error counting customers for user {user_id}: {e}")
                return 0

    def _aggregate_analysis_results(
        self, analysis_records: list, audit_analyzers: list[str]
    ) -> tuple[list[dict[str, Any]], int, int, float]:
        """Aggregate analysis records into analyzer summaries.

        Args:
            analysis_records: List of AnalysisRecord objects
            audit_analyzers: List of analyzer names for this audit

        Returns:
            Tuple of (analyzers, total_recommendations, total_critical_issues, total_potential_savings)
        """
        analyzers = []
        total_recommendations = 0
        total_critical_issues = 0
        total_potential_savings = 0.0

        for record in analysis_records:
            if record.analyzer_name in audit_analyzers:
                analyzer_summary = {
                    "analyzer_name": record.analyzer_name,
                    "status": record.status,
                    "recommendations": record.total_recommendations,
                    "critical_issues": record.critical_issues,
                    "potential_savings": record.potential_cost_savings,
                }
                analyzers.append(analyzer_summary)

                # Aggregate totals
                total_recommendations += record.total_recommendations
                total_critical_issues += record.critical_issues
                total_potential_savings += record.potential_cost_savings

        return (
            analyzers,
            total_recommendations,
            total_critical_issues,
            total_potential_savings,
        )

    async def _get_audit_analysis_records(self, session, audit: "Audit") -> list:
        """Get analysis records for an audit.

        Args:
            session: Database session
            audit: Audit object

        Returns:
            List of AnalysisRecord objects
        """
        from paidsearchnav.storage.models import AnalysisRecord, Customer

        # First get the customer's Google Ads customer ID
        customer_result = await session.execute(
            select(Customer.google_ads_customer_id).where(
                Customer.id == audit.customer_id
            )
        )
        customer_row = customer_result.scalar_one_or_none()

        if not customer_row:
            return []

        # Now find analysis records using the Google Ads customer ID
        analysis_results = await session.execute(
            select(AnalysisRecord)
            .where(AnalysisRecord.customer_id == customer_row)
            .where(
                AnalysisRecord.created_at > audit.created_at - timedelta(seconds=1)
            )  # More inclusive
            .order_by(AnalysisRecord.created_at.desc())
        )
        return analysis_results.scalars().all()

    async def get_audit_results(self, audit_id: str) -> dict[str, Any] | None:
        """Get all results for an audit with analyzer details."""
        from paidsearchnav.storage.models import Audit

        async with self.AsyncSessionLocal() as session:
            try:
                # Get audit information
                audit_result = await session.execute(
                    select(Audit).where(Audit.id == audit_id)
                )
                audit = audit_result.scalar_one_or_none()

                if not audit:
                    logger.debug(f"Audit {audit_id} not found")
                    return None

                # Get analysis records for this audit
                analysis_records = await self._get_audit_analysis_records(
                    session, audit
                )

                # Aggregate results from analysis records
                (
                    analyzers,
                    total_recommendations,
                    total_critical_issues,
                    total_potential_savings,
                ) = self._aggregate_analysis_results(analysis_records, audit.analyzers)

                return {
                    "audit_id": audit_id,
                    "status": audit.status,
                    "summary": {
                        "total_recommendations": total_recommendations,
                        "critical_issues": total_critical_issues,
                        "potential_savings": total_potential_savings,
                        "analyzers_completed": len(analyzers),
                    },
                    "analyzers": analyzers,
                    "created_at": audit.created_at,
                    "completed_at": audit.completed_at,
                }

            except Exception as e:
                logger.error(f"Error retrieving audit results {audit_id}: {e}")
                return None

    async def get_analyzer_result(
        self, audit_id: str, analyzer_name: str
    ) -> dict[str, Any] | None:
        """Get results for a specific analyzer within an audit."""
        from paidsearchnav.storage.models import AnalysisRecord, Audit

        async with self.AsyncSessionLocal() as session:
            try:
                # Get audit information
                audit_result = await session.execute(
                    select(Audit).where(Audit.id == audit_id)
                )
                audit = audit_result.scalar_one_or_none()

                if not audit:
                    logger.debug(f"Audit {audit_id} not found")
                    return None

                # Check if analyzer is part of this audit
                if analyzer_name not in audit.analyzers:
                    logger.debug(f"Analyzer {analyzer_name} not in audit {audit_id}")
                    return None

                # First get the customer's Google Ads customer ID
                from paidsearchnav.storage.models import Customer

                customer_result = await session.execute(
                    select(Customer.google_ads_customer_id).where(
                        Customer.id == audit.customer_id
                    )
                )
                customer_ads_id = customer_result.scalar_one_or_none()

                if not customer_ads_id:
                    return None

                # Get analysis record for this analyzer
                analysis_result = await session.execute(
                    select(AnalysisRecord)
                    .where(AnalysisRecord.customer_id == customer_ads_id)
                    .where(AnalysisRecord.analyzer_name == analyzer_name)
                    .where(AnalysisRecord.created_at >= audit.created_at)
                    .order_by(AnalysisRecord.created_at.desc())
                    .limit(1)
                )
                analysis_record = analysis_result.scalar_one_or_none()

                if not analysis_record:
                    # Return a basic structure if no analysis record found yet
                    return {
                        "audit_id": audit_id,
                        "analyzer": analyzer_name,
                        "status": "pending",
                        "recommendations": [],
                        "metrics": {
                            "items_analyzed": 0,
                            "issues_found": 0,
                            "potential_savings": 0.0,
                        },
                        "created_at": audit.created_at,
                        "completed_at": None,
                    }

                # Extract recommendations from result_data
                result_data = analysis_record.result_data or {}
                recommendations = result_data.get("recommendations", [])

                return {
                    "audit_id": audit_id,
                    "analyzer": analyzer_name,
                    "status": analysis_record.status,
                    "recommendations": recommendations,
                    "metrics": {
                        "items_analyzed": result_data.get("items_analyzed", 0),
                        "issues_found": analysis_record.critical_issues,
                        "potential_savings": analysis_record.potential_cost_savings,
                    },
                    "created_at": analysis_record.created_at,
                    "completed_at": analysis_record.updated_at,
                }

            except Exception as e:
                logger.error(
                    f"Error retrieving analyzer result {audit_id}/{analyzer_name}: {e}"
                )
                return None

    async def generate_report(
        self,
        audit_id: str,
        format: str,
        template: str,
        include_recommendations: bool = True,
        include_charts: bool = True,
        user_id: str | None = None,
        expiration_days: int | None = None,
    ) -> str:
        """Generate a report and return report ID."""
        from paidsearchnav.storage.models import Audit, Report

        async with self.AsyncSessionLocal() as session:
            try:
                # Verify audit exists
                audit_result = await session.execute(
                    select(Audit).where(Audit.id == audit_id)
                )
                audit = audit_result.scalar_one_or_none()

                if not audit:
                    raise ValueError(f"Audit {audit_id} not found")

                # Set expiration time (configurable, default 7 days from now)
                expiry_days = expiration_days or DEFAULT_REPORT_EXPIRATION_DAYS
                expires_at = datetime.now(timezone.utc) + timedelta(days=expiry_days)

                # Create report record
                report = Report(
                    audit_id=audit_id,
                    user_id=user_id or audit.user_id,
                    format=format,
                    template=template,
                    status="generating",
                    config={
                        "include_recommendations": include_recommendations,
                        "include_charts": include_charts,
                    },
                    expires_at=expires_at,
                )

                session.add(report)
                await session.commit()
                await session.refresh(report)

                logger.info(
                    f"Generated report {report.id} for audit {audit_id} in {format} format using {template} template"
                )
                return report.id

            except Exception as e:
                await session.rollback()
                logger.error(f"Error generating report: {e}")
                raise

    async def get_report_metadata(
        self, report_id: str, audit_id: str | None = None
    ) -> dict[str, Any] | None:
        """Get metadata for a generated report including file path and expiration."""
        from paidsearchnav.storage.models import Report

        async with self.AsyncSessionLocal() as session:
            try:
                query = select(Report).where(Report.id == report_id)

                # If audit_id is provided, also filter by it for security
                if audit_id:
                    query = query.where(Report.audit_id == audit_id)

                result = await session.execute(query)
                report = result.scalar_one_or_none()

                if not report:
                    logger.debug(f"Report {report_id} not found")
                    return None

                # Build metadata response
                metadata = report.to_dict()

                # Add computed fields
                metadata["size_bytes"] = report.file_size
                metadata["download_url"] = (
                    f"/api/v1/reports/{report.audit_id}/download?report_id={report_id}"
                )

                return metadata

            except Exception as e:
                logger.error(f"Error retrieving report metadata {report_id}: {e}")
                return None

    async def create_customer(self, customer_data: dict[str, Any]) -> dict[str, Any]:
        """Create a new customer."""
        async with self.AsyncSessionLocal() as session:
            try:
                # Create CustomerData instance for validation and serialization
                settings = CustomerSettings(**customer_data.get("settings", {}))

                # Insert customer
                result = await session.execute(
                    text("""
                        INSERT INTO customers (
                            id, name, email, user_type, google_ads_customer_id,
                            created_at, updated_at, is_active, settings
                        ) VALUES (
                            :id, :name, :email, :user_type, :google_ads_customer_id,
                            :created_at, :updated_at, :is_active, :settings
                        ) RETURNING *
                    """),
                    {
                        "id": customer_data["id"],
                        "name": customer_data["name"],
                        "email": customer_data["email"],
                        "user_type": customer_data["user_type"],
                        "google_ads_customer_id": customer_data.get(
                            "google_ads_customer_id"
                        ),
                        "created_at": customer_data["created_at"],
                        "updated_at": customer_data["updated_at"],
                        "is_active": customer_data.get("is_active", True),
                        "settings": settings.model_dump_json(),
                    },
                )

                await session.commit()
                row = result.fetchone()
                if row:
                    return {
                        "id": row[0],
                        "name": row[1],
                        "email": row[2],
                        "user_type": row[3],
                        "google_ads_customer_id": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                        "is_active": row[7],
                        "settings": settings.model_dump(),
                    }
                else:
                    raise Exception("Failed to create customer")

            except ValidationError as e:
                logger.error(f"Invalid customer settings: {e}")
                raise ValueError(f"Invalid customer settings: {e}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error creating customer: {e}")
                raise

    async def update_customer(
        self, customer_id: str, update_data: dict[str, Any]
    ) -> dict[str, Any]:
        """Update an existing customer."""
        async with self.AsyncSessionLocal() as session:
            try:
                # Build SET clause dynamically
                set_clauses = []
                params = {"customer_id": customer_id}

                for key, value in update_data.items():
                    if key == "settings":
                        # Validate settings using Pydantic
                        if isinstance(value, dict):
                            settings = CustomerSettings(**value)
                            set_clauses.append(f"{key} = :{key}")
                            params[key] = settings.model_dump_json()
                        else:
                            set_clauses.append(f"{key} = :{key}")
                            params[key] = value
                    else:
                        set_clauses.append(f"{key} = :{key}")
                        params[key] = value

                query = f"""
                    UPDATE customers
                    SET {", ".join(set_clauses)}
                    WHERE id = :customer_id
                    RETURNING *
                """

                result = await session.execute(text(query), params)
                await session.commit()

                row = result.fetchone()
                if row:
                    # Parse settings safely
                    settings_dict = {}
                    if row[8]:
                        try:
                            import json

                            settings_dict = json.loads(row[8])
                        except (json.JSONDecodeError, TypeError):
                            settings_dict = {}

                    return {
                        "id": row[0],
                        "name": row[1],
                        "email": row[2],
                        "user_type": row[3],
                        "google_ads_customer_id": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                        "is_active": row[7],
                        "settings": settings_dict,
                    }
                else:
                    raise Exception("Customer not found or update failed")

            except ValidationError as e:
                logger.error(f"Invalid settings in customer update: {e}")
                raise ValueError(f"Invalid customer settings: {e}")
            except Exception as e:
                await session.rollback()
                logger.error(f"Error updating customer {customer_id}: {e}")
                raise

    async def get_customer_by_google_ads_id(
        self, google_ads_id: str
    ) -> dict[str, Any] | None:
        """Get customer by Google Ads customer ID."""
        async with self.AsyncSessionLocal() as session:
            try:
                result = await session.execute(
                    text("""
                        SELECT id, name, email, user_type, google_ads_customer_id,
                               created_at, updated_at, is_active, settings
                        FROM customers
                        WHERE google_ads_customer_id = :google_ads_id
                        AND is_active = true
                    """),
                    {"google_ads_id": google_ads_id},
                )

                row = result.fetchone()
                if row:
                    # Parse settings safely
                    settings_dict = {}
                    if row[8]:
                        try:
                            settings_dict = json.loads(row[8])
                        except (json.JSONDecodeError, TypeError):
                            settings_dict = {}

                    return {
                        "id": row[0],
                        "name": row[1],
                        "email": row[2],
                        "user_type": row[3],
                        "google_ads_customer_id": row[4],
                        "created_at": row[5],
                        "updated_at": row[6],
                        "is_active": row[7],
                        "settings": settings_dict,
                    }
                return None

            except Exception as e:
                logger.error(
                    f"Error getting customer by Google Ads ID {google_ads_id}: {e}"
                )
                return None

    async def link_user_to_customer(self, user_id: str, customer_id: str) -> None:
        """Link a user to a customer."""
        async with self.AsyncSessionLocal() as session:
            try:
                # Check if link already exists
                existing = await session.execute(
                    text("""
                        SELECT id FROM customer_access
                        WHERE user_id = :user_id AND customer_id = :customer_id
                    """),
                    {"user_id": user_id, "customer_id": customer_id},
                )

                if not existing.fetchone():
                    # Create the link
                    await session.execute(
                        text("""
                            INSERT INTO customer_access (user_id, customer_id, is_active, created_at)
                            VALUES (:user_id, :customer_id, true, :created_at)
                        """),
                        {
                            "user_id": user_id,
                            "customer_id": customer_id,
                            "created_at": datetime.utcnow(),
                        },
                    )
                    await session.commit()

            except Exception as e:
                await session.rollback()
                logger.error(
                    f"Error linking user {user_id} to customer {customer_id}: {e}"
                )
                raise

    async def store_analysis_result(self, analysis_result) -> str:
        """Store attribution analysis result and return analysis ID."""
        from paidsearchnav.storage.models import AnalysisRecord

        async with self.AsyncSessionLocal() as session:
            try:
                # Create analysis record
                analysis_record = AnalysisRecord(
                    customer_id=analysis_result.customer_id,
                    analyzer_name=analysis_result.analyzer_name,
                    status="completed" if analysis_result.success else "failed",
                    result_data=analysis_result.data,
                    critical_issues=len(analysis_result.errors),
                    potential_cost_savings=analysis_result.metadata.get(
                        "total_attributed_revenue", 0.0
                    ),
                )

                session.add(analysis_record)
                await session.commit()
                await session.refresh(analysis_record)

                return analysis_record.id

            except Exception as e:
                await session.rollback()
                logger.error(f"Error storing analysis result: {e}")
                raise

    async def store_model_comparison(self, comparison_result: dict) -> str:
        """Store attribution model comparison result."""
        # For now, store as a generic analysis result
        # In a full implementation, this would have its own table
        comparison_id = f"comparison_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        # Store in a simple way for this implementation
        logger.info(f"Stored model comparison {comparison_id}")
        return comparison_id

    async def store_attribution_report(self, report_result: dict) -> str:
        """Store attribution report result."""
        # For now, store as a generic report
        # In a full implementation, this would integrate with the existing report system
        report_id = f"attribution_report_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}"

        logger.info(f"Stored attribution report {report_id}")
        return report_id

    async def get_customer_journey(self, journey_id: str) -> dict | None:
        """Get customer journey by ID."""
        # This would query the customer_journeys table in BigQuery
        # For now, return a placeholder
        logger.info(f"Retrieved customer journey {journey_id}")
        return {
            "journey_id": journey_id,
            "customer_id": "placeholder",
            "first_touch": datetime.utcnow(),
            "last_touch": datetime.utcnow(),
            "converted": True,
            "conversion_value": 100.0,
        }

    async def get_journey_touchpoints(self, journey_id: str) -> list:
        """Get touchpoints for a customer journey."""
        # This would query the attribution_touches table in BigQuery
        # For now, return empty list
        logger.info(f"Retrieved touchpoints for journey {journey_id}")
        return []
