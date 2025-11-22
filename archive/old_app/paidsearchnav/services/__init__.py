"""Service layer for business logic."""

import logging
from typing import Any

from croniter import croniter

from paidsearchnav.core.exceptions import (
    AuthorizationError,
    ResourceNotFoundError,
    ValidationError,
)
from paidsearchnav.storage.api_repository import APIRepository

logger = logging.getLogger(__name__)


# Configuration constants
class ServiceConfig:
    """Configuration constants for service layer."""

    MAX_CUSTOMER_NAME_LENGTH = 255
    MAX_AUDIT_NAME_LENGTH = 255
    MAX_SCHEDULE_NAME_LENGTH = 255
    DEFAULT_LIMIT = 20
    MAX_LIMIT = 100
    MAX_RECOMMENDATIONS_LIMIT = 100
    AUDIT_HISTORY_LIMIT = 10


def _validate_cron_expression(cron_expr: str) -> bool:
    """Validate cron expression format using croniter."""
    try:
        croniter(cron_expr)
        return True
    except (ValueError, TypeError):
        return False


def _validate_string_length(value: str, field_name: str, max_length: int) -> None:
    """Validate string length and raise ValidationError if too long."""
    if len(value) > max_length:
        raise ValidationError(
            f"{field_name} cannot exceed {max_length} characters (got {len(value)})"
        )


def _validate_name_content(value: str, field_name: str) -> None:
    """Validate name content for basic safety checks."""
    if not value.strip():
        raise ValidationError(f"{field_name} cannot be empty or whitespace only")

    # Basic safety: prevent control characters and common injection patterns
    dangerous_chars = ["\n", "\r", "\t", "\0", "<", ">", '"', "'", "\\"]
    if any(char in value for char in dangerous_chars):
        raise ValidationError(f"{field_name} contains invalid characters")


class CustomerService:
    """Service for managing customer operations."""

    def __init__(self, repository: APIRepository):
        """Initialize with repository."""
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    async def get_by_id(self, customer_id: str, user_id: str) -> dict[str, Any] | None:
        """Get customer by ID with access control."""
        if not customer_id or not customer_id.strip():
            raise ValidationError("Customer ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        has_access = await self.repository.user_has_customer_access(
            user_id, customer_id
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this customer"
            )

        customer = await self.repository.get_customer(customer_id)
        if not customer:
            raise ResourceNotFoundError(f"Customer {customer_id} not found")

        self.logger.debug(f"Retrieved customer {customer_id} for user {user_id}")
        return customer

    async def get_by_ids(
        self, customer_ids: list[str], user_id: str
    ) -> list[dict[str, Any]]:
        """Get multiple customers by ID with access control.

        Note: This method currently uses individual access checks per customer.
        When repository supports batch operations, this should be optimized
        to reduce database calls.
        """
        if not customer_ids:
            return []

        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Get all customers user has access to first, then filter by requested IDs
        # This reduces N+1 queries when dealing with many customer IDs
        accessible_customers = await self.repository.get_customers_for_user(
            user_id=user_id, offset=0, limit=ServiceConfig.MAX_LIMIT
        )

        # Create lookup for requested customer IDs
        requested_ids = set(customer_ids)
        customers = [
            customer
            for customer in accessible_customers
            if customer["id"] in requested_ids
        ]

        self.logger.debug(f"Retrieved {len(customers)} customers for user {user_id}")
        return customers

    async def get_filtered(
        self,
        user_id: str,
        offset: int = 0,
        limit: int = ServiceConfig.DEFAULT_LIMIT,
        filters: dict[str, Any] | None = None,
    ) -> tuple[list[dict[str, Any]], int]:
        """Get filtered customers with pagination."""
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")
        if offset < 0:
            raise ValidationError("Offset cannot be negative")
        if limit < 1 or limit > ServiceConfig.MAX_LIMIT:
            raise ValidationError(
                f"Limit must be between 1 and {ServiceConfig.MAX_LIMIT}"
            )

        customers = await self.repository.get_customers_for_user(
            user_id=user_id, offset=offset, limit=limit
        )

        total = await self.repository.count_customers_for_user(user_id=user_id)

        if filters:
            customers = self._apply_filters(customers, filters)

        self.logger.debug(
            f"Retrieved {len(customers)} customers (total: {total}) for user {user_id}"
        )
        return customers, total

    def _apply_filters(
        self, customers: list[dict[str, Any]], filters: dict[str, Any]
    ) -> list[dict[str, Any]]:
        """Apply client-side filters to customer list.

        Note: This is a temporary solution. In production, these filters
        should be moved to the repository layer for better performance
        to avoid loading unnecessary data from the database.
        """
        filtered_customers = customers

        if "is_active" in filters:
            is_active = filters["is_active"]
            if isinstance(is_active, bool):
                filtered_customers = [
                    c for c in filtered_customers if c.get("is_active") == is_active
                ]

        if "name" in filters and filters["name"]:
            name_filter = filters["name"].lower()
            filtered_customers = [
                c
                for c in filtered_customers
                if name_filter in c.get("name", "").lower()
            ]

        if "google_ads_customer_id" in filters and filters["google_ads_customer_id"]:
            ads_id = filters["google_ads_customer_id"]
            filtered_customers = [
                c
                for c in filtered_customers
                if c.get("google_ads_customer_id") == ads_id
            ]

        return filtered_customers


class AuditService:
    """Service for managing audit operations."""

    def __init__(self, repository: APIRepository):
        """Initialize with repository."""
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    async def get_by_id(self, audit_id: str, user_id: str) -> dict[str, Any] | None:
        """Get audit by ID with access control."""
        if not audit_id or not audit_id.strip():
            raise ValidationError("Audit ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        audit = await self.repository.get_audit(audit_id)
        if not audit:
            raise ResourceNotFoundError(f"Audit {audit_id} not found")

        # Check if user has access to this audit's customer
        has_access = await self.repository.user_has_customer_access(
            user_id, audit["customer_id"]
        )
        if not has_access:
            raise AuthorizationError("You don't have permission to access this audit")

        self.logger.debug(f"Retrieved audit {audit_id} for user {user_id}")
        return audit

    async def get_by_ids(
        self, audit_ids: list[str], user_id: str
    ) -> list[dict[str, Any]]:
        """Get multiple audits by ID with access control."""
        if not audit_ids:
            return []

        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Process audits individually for now, but collect access check results
        # to avoid redundant customer access checks
        audits = []
        customer_access_cache = {}

        for audit_id in audit_ids:
            try:
                audit = await self.repository.get_audit(audit_id)
                if not audit:
                    self.logger.debug(f"Audit {audit_id} not found")
                    continue

                customer_id = audit["customer_id"]

                # Cache customer access checks to avoid redundant calls
                if customer_id not in customer_access_cache:
                    customer_access_cache[
                        customer_id
                    ] = await self.repository.user_has_customer_access(
                        user_id, customer_id
                    )

                if customer_access_cache[customer_id]:
                    audits.append(audit)
                else:
                    self.logger.debug(
                        f"Skipping audit {audit_id} - no access to customer {customer_id}"
                    )

            except Exception as e:
                self.logger.error(f"Error retrieving audit {audit_id}: {e}")
                continue

        self.logger.debug(f"Retrieved {len(audits)} audits for user {user_id}")
        return audits

    async def get_by_customer_id(
        self, customer_id: str, user_id: str, limit: int | None = None
    ) -> list[dict[str, Any]]:
        """Get audits for a customer with access control."""
        if not customer_id or not customer_id.strip():
            raise ValidationError("Customer ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer
        has_access = await self.repository.user_has_customer_access(
            user_id, customer_id
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this customer"
            )

        # Get audits for customer
        audits, _ = await self.repository.list_audits(
            customer_id=customer_id, limit=limit or ServiceConfig.DEFAULT_LIMIT
        )

        self.logger.debug(f"Retrieved {len(audits)} audits for customer {customer_id}")
        return audits

    async def get_by_customer_ids(
        self, customer_ids: list[str], user_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Get audits for multiple customers with access control."""
        if not customer_ids:
            return {}

        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        result = {}
        for customer_id in customer_ids:
            try:
                audits = await self.get_by_customer_id(customer_id, user_id)
                result[customer_id] = audits
            except (AuthorizationError, ResourceNotFoundError):
                self.logger.debug(f"Skipping customer {customer_id} - no access")
                continue

        return result

    async def create_audit(
        self,
        customer_id: str,
        name: str,
        analyzers: list[str],
        user_id: str,
        config: dict[str, Any] | None = None,
    ) -> str:
        """Create a new audit."""
        if not customer_id or not customer_id.strip():
            raise ValidationError("Customer ID is required")
        if not name or not name.strip():
            raise ValidationError("Audit name is required")

        # Enhanced validation
        _validate_name_content(name, "Audit name")
        _validate_string_length(name, "Audit name", ServiceConfig.MAX_AUDIT_NAME_LENGTH)
        if not analyzers:
            raise ValidationError("At least one analyzer is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer
        has_access = await self.repository.user_has_customer_access(
            user_id, customer_id
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this customer"
            )

        # Create audit
        audit_id = await self.repository.create_audit(
            customer_id=customer_id,
            name=name,
            analyzers=analyzers,
            config=config or {},
            user_id=user_id,
        )

        self.logger.info(f"Created audit {audit_id} for customer {customer_id}")
        return audit_id

    async def start_audit(self, audit_id: str, user_id: str) -> bool:
        """Start an audit execution."""
        if not audit_id or not audit_id.strip():
            raise ValidationError("Audit ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to audit
        audit = await self.get_by_id(audit_id, user_id)
        if not audit:
            raise ResourceNotFoundError(f"Audit {audit_id} not found")

        # TODO: Integrate with actual audit execution system
        self.logger.info(f"Started audit {audit_id} execution")
        return True

    async def cancel_audit(self, audit_id: str, user_id: str) -> bool:
        """Cancel a running audit."""
        if not audit_id or not audit_id.strip():
            raise ValidationError("Audit ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to audit
        audit = await self.get_by_id(audit_id, user_id)
        if not audit:
            raise ResourceNotFoundError(f"Audit {audit_id} not found")

        # Check if audit can be cancelled
        if audit["status"] not in ["pending", "running"]:
            raise ValidationError("Can only cancel pending or running audits")

        # Cancel audit
        success = await self.repository.cancel_audit(audit_id)
        if success:
            self.logger.info(f"Cancelled audit {audit_id}")
        return success


class AnalysisService:
    """Service for managing analysis operations."""

    def __init__(self, repository: APIRepository):
        """Initialize with repository."""
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    async def get_by_audit_ids(
        self, audit_ids: list[str], user_id: str
    ) -> dict[str, dict[str, Any]]:
        """Get analysis results for multiple audits with access control."""
        if not audit_ids:
            return {}

        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        results = {}
        for audit_id in audit_ids:
            try:
                # Check access to audit first
                audit = await self.repository.get_audit(audit_id)
                if not audit:
                    continue

                has_access = await self.repository.user_has_customer_access(
                    user_id, audit["customer_id"]
                )
                if not has_access:
                    self.logger.debug(f"No access to audit {audit_id}")
                    continue

                # Get analysis results
                analysis_results = await self.repository.get_audit_results(audit_id)
                if analysis_results:
                    results[audit_id] = analysis_results

            except Exception as e:
                self.logger.error(f"Error getting analysis for audit {audit_id}: {e}")
                continue

        self.logger.debug(f"Retrieved analysis for {len(results)} audits")
        return results

    async def get_filtered(
        self,
        user_id: str,
        customer_id: str | None = None,
        analyzer_name: str | None = None,
        limit: int = ServiceConfig.DEFAULT_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get filtered analysis results."""
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer if specified
        if customer_id:
            has_access = await self.repository.user_has_customer_access(
                user_id, customer_id
            )
            if not has_access:
                raise AuthorizationError(
                    "You don't have permission to access this customer"
                )

        # Get analyses from repository
        analyses = await self.repository.list_analyses(
            customer_id=customer_id,
            analysis_type=analyzer_name,
            limit=limit,
        )

        # Filter based on user access
        accessible_analyses = []
        for analysis in analyses:
            try:
                has_access = await self.repository.user_has_customer_access(
                    user_id, analysis.customer_id
                )
                if has_access:
                    accessible_analyses.append(analysis.model_dump())
            except Exception as e:
                self.logger.error(
                    f"Error checking access for analysis {analysis.analysis_id}: {e}"
                )
                continue

        self.logger.debug(f"Retrieved {len(accessible_analyses)} accessible analyses")
        return accessible_analyses


class RecommendationService:
    """Service for managing recommendations."""

    def __init__(self, repository: APIRepository):
        """Initialize with repository."""
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    async def get_by_audit_ids(
        self, audit_ids: list[str], user_id: str
    ) -> dict[str, list[dict[str, Any]]]:
        """Get recommendations for multiple audits with access control."""
        if not audit_ids:
            return {}

        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        results = {}
        for audit_id in audit_ids:
            try:
                # Check access to audit first
                audit = await self.repository.get_audit(audit_id)
                if not audit:
                    continue

                has_access = await self.repository.user_has_customer_access(
                    user_id, audit["customer_id"]
                )
                if not has_access:
                    self.logger.debug(f"No access to audit {audit_id}")
                    continue

                # Get recommendations from audit results
                audit_results = await self.repository.get_audit_results(audit_id)
                if audit_results and "analyzers" in audit_results:
                    recommendations = []
                    for analyzer in audit_results["analyzers"]:
                        analyzer_result = await self.repository.get_analyzer_result(
                            audit_id, analyzer["analyzer_name"]
                        )
                        if analyzer_result and "recommendations" in analyzer_result:
                            recommendations.extend(analyzer_result["recommendations"])

                    results[audit_id] = recommendations

            except Exception as e:
                self.logger.error(
                    f"Error getting recommendations for audit {audit_id}: {e}"
                )
                continue

        self.logger.debug(f"Retrieved recommendations for {len(results)} audits")
        return results

    async def get_filtered(
        self,
        user_id: str,
        customer_id: str | None = None,
        priority: str | None = None,
        recommendation_type: str | None = None,
        limit: int = ServiceConfig.MAX_RECOMMENDATIONS_LIMIT,
    ) -> list[dict[str, Any]]:
        """Get filtered recommendations."""
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer if specified
        if customer_id:
            has_access = await self.repository.user_has_customer_access(
                user_id, customer_id
            )
            if not has_access:
                raise AuthorizationError(
                    "You don't have permission to access this customer"
                )

        # Get recent audits to extract recommendations from
        audits, _ = await self.repository.list_audits(
            customer_id=customer_id, limit=ServiceConfig.AUDIT_HISTORY_LIMIT
        )

        recommendations = []
        for audit in audits:
            audit_recommendations = await self.get_by_audit_ids([audit["id"]], user_id)
            if audit["id"] in audit_recommendations:
                for rec in audit_recommendations[audit["id"]]:
                    # Apply filters
                    if priority and rec.get("priority") != priority:
                        continue
                    if recommendation_type and rec.get("type") != recommendation_type:
                        continue

                    # Add audit context
                    rec["audit_id"] = audit["id"]
                    rec["customer_id"] = audit["customer_id"]
                    recommendations.append(rec)

        # Limit results
        recommendations = recommendations[:limit]

        self.logger.debug(f"Retrieved {len(recommendations)} filtered recommendations")
        return recommendations


class SchedulerService:
    """Service for managing audit scheduling."""

    def __init__(self, repository: APIRepository):
        """Initialize with repository."""
        self.repository = repository
        self.logger = logging.getLogger(__name__)

    async def schedule_audit(
        self,
        customer_id: str,
        name: str,
        cron_expression: str,
        analyzers: list[str],
        user_id: str,
        config: dict[str, Any] | None = None,
        enabled: bool = True,
    ) -> str:
        """Schedule a recurring audit."""
        if not customer_id or not customer_id.strip():
            raise ValidationError("Customer ID is required")
        if not name or not name.strip():
            raise ValidationError("Schedule name is required")

        # Enhanced validation
        _validate_name_content(name, "Schedule name")
        _validate_string_length(
            name, "Schedule name", ServiceConfig.MAX_SCHEDULE_NAME_LENGTH
        )

        if not cron_expression or not cron_expression.strip():
            raise ValidationError("Cron expression is required")
        if not analyzers:
            raise ValidationError("At least one analyzer is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer
        has_access = await self.repository.user_has_customer_access(
            user_id, customer_id
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this customer"
            )

        # Validate cron expression format
        if not _validate_cron_expression(cron_expression):
            raise ValidationError("Invalid cron expression format")

        # Create schedule
        schedule_id = await self.repository.create_schedule(
            customer_id=customer_id,
            name=name,
            cron_expression=cron_expression,
            analyzers=analyzers,
            config=config or {},
            enabled=enabled,
            user_id=user_id,
        )

        self.logger.info(f"Created schedule {schedule_id} for customer {customer_id}")
        return schedule_id

    async def get_schedule(
        self, schedule_id: str, user_id: str
    ) -> dict[str, Any] | None:
        """Get schedule by ID with access control."""
        if not schedule_id or not schedule_id.strip():
            raise ValidationError("Schedule ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        schedule = await self.repository.get_schedule(schedule_id)
        if not schedule:
            raise ResourceNotFoundError(f"Schedule {schedule_id} not found")

        # Check access to customer
        has_access = await self.repository.user_has_customer_access(
            user_id, schedule["customer_id"]
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this schedule"
            )

        self.logger.debug(f"Retrieved schedule {schedule_id} for user {user_id}")
        return schedule

    async def list_schedules(
        self, customer_id: str, user_id: str, limit: int = ServiceConfig.DEFAULT_LIMIT
    ) -> list[dict[str, Any]]:
        """List schedules for a customer with access control."""
        if not customer_id or not customer_id.strip():
            raise ValidationError("Customer ID is required")
        if not user_id or not user_id.strip():
            raise ValidationError("User ID is required")

        # Check access to customer
        has_access = await self.repository.user_has_customer_access(
            user_id, customer_id
        )
        if not has_access:
            raise AuthorizationError(
                "You don't have permission to access this customer"
            )

        # Get schedules
        schedules, _ = await self.repository.list_schedules(
            customer_id=customer_id, limit=limit
        )

        self.logger.debug(
            f"Retrieved {len(schedules)} schedules for customer {customer_id}"
        )
        return schedules


# Service factory functions
def create_customer_service(repository: APIRepository) -> CustomerService:
    """Create CustomerService instance."""
    return CustomerService(repository)


def create_audit_service(repository: APIRepository) -> AuditService:
    """Create AuditService instance."""
    return AuditService(repository)


def create_analysis_service(repository: APIRepository) -> AnalysisService:
    """Create AnalysisService instance."""
    return AnalysisService(repository)


def create_recommendation_service(repository: APIRepository) -> RecommendationService:
    """Create RecommendationService instance."""
    return RecommendationService(repository)


def create_scheduler_service(repository: APIRepository) -> SchedulerService:
    """Create SchedulerService instance."""
    return SchedulerService(repository)


# Backward compatibility - create placeholder instances
# These will need to be properly initialized with repository in production
class _PlaceholderRepository:
    """Placeholder repository for backward compatibility."""

    pass


# Service instances for backward compatibility
customer_service = CustomerService(_PlaceholderRepository())
audit_service = AuditService(_PlaceholderRepository())
analysis_service = AnalysisService(_PlaceholderRepository())
recommendation_service = RecommendationService(_PlaceholderRepository())
scheduler_service = SchedulerService(_PlaceholderRepository())

__all__ = [
    "CustomerService",
    "AuditService",
    "AnalysisService",
    "RecommendationService",
    "SchedulerService",
    "create_customer_service",
    "create_audit_service",
    "create_analysis_service",
    "create_recommendation_service",
    "create_scheduler_service",
    "customer_service",
    "audit_service",
    "analysis_service",
    "recommendation_service",
    "scheduler_service",
]
