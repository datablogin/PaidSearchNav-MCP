"""GraphQL Query resolvers."""

from typing import List, Optional

import strawberry
from strawberry.types import Info

from paidsearchnav.api.dependencies import get_current_user
from paidsearchnav.graphql.config import GraphQLConfig
from paidsearchnav.graphql.types import (
    AnalysisResult,
    AnalyzerType,
    Audit,
    Customer,
    CustomerFilter,
    DateRange,
    Priority,
    Recommendation,
)
from paidsearchnav.services import (
    customer_service,
    recommendation_service,
)


@strawberry.type
class Query:
    """Root Query type."""

    @strawberry.field
    async def customer(self, info: Info, id: strawberry.ID) -> Optional[Customer]:
        """Get a single customer by ID."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Use DataLoader to fetch customer
        from paidsearchnav.graphql.dataloaders import DataLoaderRegistry

        registry: DataLoaderRegistry = info.context["dataloaders"]
        customer_data = await registry.get_customer_loader().load(id)

        if not customer_data:
            return None

        return Customer(
            id=customer_data.id,
            name=customer_data.name,
            google_ads_account_id=customer_data.google_ads_account_id,
            created_at=customer_data.created_at,
            updated_at=customer_data.updated_at,
            is_active=customer_data.is_active,
        )

    @strawberry.field
    async def customers(
        self,
        info: Info,
        filter: Optional[CustomerFilter] = None,
        limit: int = GraphQLConfig.DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> List[Customer]:
        """Get list of customers with optional filtering and pagination."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Enforce maximum limit
        if limit > GraphQLConfig.MAX_PAGE_SIZE:
            raise Exception(f"Maximum limit is {GraphQLConfig.MAX_PAGE_SIZE} items")

        # Build filter criteria
        criteria = {}
        if filter:
            if filter.is_active is not None:
                criteria["is_active"] = filter.is_active
            if filter.name_contains:
                criteria["name__icontains"] = filter.name_contains
            if filter.created_after:
                criteria["created_at__gte"] = filter.created_after
            if filter.created_before:
                criteria["created_at__lte"] = filter.created_before

        # Fetch customers with pagination
        customers_data = await customer_service.get_filtered(
            **criteria, limit=limit, offset=offset
        )

        return [
            Customer(
                id=c.id,
                name=c.name,
                google_ads_account_id=c.google_ads_account_id,
                created_at=c.created_at,
                updated_at=c.updated_at,
                is_active=c.is_active,
            )
            for c in customers_data
        ]

    @strawberry.field
    async def audit(self, info: Info, id: strawberry.ID) -> Optional[Audit]:
        """Get a single audit by ID."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Use DataLoader to fetch audit
        from paidsearchnav.graphql.dataloaders import DataLoaderRegistry

        registry: DataLoaderRegistry = info.context["dataloaders"]
        audit_data = await registry.get_audit_loader().load(id)

        if not audit_data:
            return None

        return Audit(
            id=audit_data.id,
            customer_id=audit_data.customer_id,
            status=audit_data.status,
            created_at=audit_data.created_at,
            started_at=audit_data.started_at,
            completed_at=audit_data.completed_at,
            error_message=audit_data.error_message,
            total_analyzers=audit_data.total_analyzers,
            completed_analyzers=audit_data.completed_analyzers,
        )

    @strawberry.field
    async def audits(
        self, info: Info, customer_id: strawberry.ID, limit: int = 50
    ) -> List[Audit]:
        """Get audits for a customer with pagination."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Enforce maximum limit (use smaller limit for audits)
        max_audit_limit = min(GraphQLConfig.MAX_PAGE_SIZE, 500)
        if limit > max_audit_limit:
            raise Exception(f"Maximum limit is {max_audit_limit} audits")

        # Use DataLoader to fetch audits
        from paidsearchnav.graphql.dataloaders import DataLoaderRegistry

        registry: DataLoaderRegistry = info.context["dataloaders"]
        audits_data = await registry.get_customer_audits_loader().load(customer_id)

        # Apply limit
        if limit and limit > 0:
            audits_data = audits_data[:limit]

        return [
            Audit(
                id=a.id,
                customer_id=a.customer_id,
                status=a.status,
                created_at=a.created_at,
                started_at=a.started_at,
                completed_at=a.completed_at,
                error_message=a.error_message,
                total_analyzers=a.total_analyzers,
                completed_analyzers=a.completed_analyzers,
            )
            for a in audits_data
        ]

    @strawberry.field
    async def analysis_results(
        self,
        info: Info,
        audit_id: strawberry.ID,
        analyzers: Optional[List[AnalyzerType]] = None,
    ) -> List[AnalysisResult]:
        """Get analysis results for an audit."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Use DataLoader to fetch analysis results
        from paidsearchnav.graphql.dataloaders import DataLoaderRegistry

        registry: DataLoaderRegistry = info.context["dataloaders"]
        results_data = await registry.get_audit_results_loader().load(audit_id)

        # Filter by analyzer type if specified
        if analyzers:
            analyzer_values = [a.value for a in analyzers]
            results_data = [
                r for r in results_data if r.analyzer_type in analyzer_values
            ]

        return [
            AnalysisResult(
                id=r.id,
                audit_id=r.audit_id,
                analyzer_type=r.analyzer_type,
                status=r.status,
                created_at=r.created_at,
                completed_at=r.completed_at,
                findings=r.findings,
                score=r.score,
                impact_level=r.impact_level,
                issues_found=r.issues_found,
                opportunities_identified=r.opportunities_identified,
                potential_savings=r.potential_savings,
            )
            for r in results_data
        ]

    @strawberry.field
    async def recommendations(
        self,
        info: Info,
        customer_id: strawberry.ID,
        priority: Optional[Priority] = None,
        date_range: Optional[DateRange] = None,
        limit: int = GraphQLConfig.DEFAULT_PAGE_SIZE,
        offset: int = 0,
    ) -> List[Recommendation]:
        """Get recommendations for a customer with pagination."""
        # Get current user from context
        user = await get_current_user(info.context["request"])

        # Enforce maximum limit
        if limit > GraphQLConfig.MAX_PAGE_SIZE:
            raise Exception(
                f"Maximum limit is {GraphQLConfig.MAX_PAGE_SIZE} recommendations"
            )

        # Build filter
        criteria = {"customer_id": customer_id}
        if priority:
            criteria["priority"] = priority.value
        if date_range:
            criteria["created_at__gte"] = date_range.start_date
            criteria["created_at__lte"] = date_range.end_date

        # Fetch recommendations with pagination
        recommendations_data = await recommendation_service.get_filtered(
            **criteria, limit=limit, offset=offset
        )

        return [
            Recommendation(
                id=r.id,
                audit_id=r.audit_id,
                analysis_result_id=r.analysis_result_id,
                title=r.title,
                description=r.description,
                priority=r.priority,
                status=r.status,
                estimated_impact=r.estimated_impact,
                estimated_cost_savings=r.estimated_cost_savings,
                implementation_effort=r.implementation_effort,
                action_items=r.action_items,
                implementation_notes=r.implementation_notes,
                created_at=r.created_at,
                updated_at=r.updated_at,
                implemented_at=r.implemented_at,
            )
            for r in recommendations_data
        ]
