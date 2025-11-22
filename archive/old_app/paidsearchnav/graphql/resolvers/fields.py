"""Field resolvers for GraphQL types using DataLoaders."""

from typing import List, Optional

import strawberry
from strawberry.types import Info

from paidsearchnav.graphql.types import (
    AnalysisResult,
    Audit,
    Customer,
    Recommendation,
)


# Customer field resolvers
@strawberry.field
async def resolve_customer_audits(
    self: Customer, info: Info, limit: int = 10
) -> List[Audit]:
    """Resolve audits for a customer using DataLoader."""
    dataloaders = info.context["dataloaders"]
    audits = await dataloaders.get_customer_audits_loader().load(self.id)

    # Apply limit
    if limit and limit > 0:
        audits = audits[:limit]

    # Convert to GraphQL types
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
        for a in audits
    ]


@strawberry.field
async def resolve_customer_latest_audit(self: Customer, info: Info) -> Optional[Audit]:
    """Resolve latest audit for a customer using DataLoader."""
    dataloaders = info.context["dataloaders"]
    audits = await dataloaders.get_customer_audits_loader().load(self.id)

    if not audits:
        return None

    # Get the most recent audit
    latest = max(audits, key=lambda a: a.created_at)

    return Audit(
        id=latest.id,
        customer_id=latest.customer_id,
        status=latest.status,
        created_at=latest.created_at,
        started_at=latest.started_at,
        completed_at=latest.completed_at,
        error_message=latest.error_message,
        total_analyzers=latest.total_analyzers,
        completed_analyzers=latest.completed_analyzers,
    )


# Audit field resolvers
@strawberry.field
async def resolve_audit_customer(self: Audit, info: Info) -> Optional[Customer]:
    """Resolve customer for an audit using DataLoader."""
    dataloaders = info.context["dataloaders"]
    customer = await dataloaders.get_customer_loader().load(self.customer_id)

    if not customer:
        return None

    return Customer(
        id=customer.id,
        name=customer.name,
        google_ads_account_id=customer.google_ads_account_id,
        created_at=customer.created_at,
        updated_at=customer.updated_at,
        is_active=customer.is_active,
    )


@strawberry.field
async def resolve_audit_analysis_results(
    self: Audit, info: Info
) -> List[AnalysisResult]:
    """Resolve analysis results for an audit using DataLoader."""
    dataloaders = info.context["dataloaders"]
    results = await dataloaders.get_audit_results_loader().load(self.id)

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
        for r in results
    ]


@strawberry.field
async def resolve_audit_recommendations(
    self: Audit, info: Info
) -> List[Recommendation]:
    """Resolve recommendations for an audit using DataLoader."""
    dataloaders = info.context["dataloaders"]
    recommendations = await dataloaders.get_audit_recommendations_loader().load(self.id)

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
        for r in recommendations
    ]


# AnalysisResult field resolvers
@strawberry.field
async def resolve_analysis_result_audit(
    self: AnalysisResult, info: Info
) -> Optional[Audit]:
    """Resolve audit for an analysis result using DataLoader."""
    dataloaders = info.context["dataloaders"]
    audit = await dataloaders.get_audit_loader().load(self.audit_id)

    if not audit:
        return None

    return Audit(
        id=audit.id,
        customer_id=audit.customer_id,
        status=audit.status,
        created_at=audit.created_at,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        error_message=audit.error_message,
        total_analyzers=audit.total_analyzers,
        completed_analyzers=audit.completed_analyzers,
    )


# Recommendation field resolvers
@strawberry.field
async def resolve_recommendation_audit(
    self: Recommendation, info: Info
) -> Optional[Audit]:
    """Resolve audit for a recommendation using DataLoader."""
    dataloaders = info.context["dataloaders"]
    audit = await dataloaders.get_audit_loader().load(self.audit_id)

    if not audit:
        return None

    return Audit(
        id=audit.id,
        customer_id=audit.customer_id,
        status=audit.status,
        created_at=audit.created_at,
        started_at=audit.started_at,
        completed_at=audit.completed_at,
        error_message=audit.error_message,
        total_analyzers=audit.total_analyzers,
        completed_analyzers=audit.completed_analyzers,
    )
