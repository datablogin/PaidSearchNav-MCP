"""DataLoader implementations for efficient data fetching."""

from typing import Any, Dict, List

from strawberry.dataloader import DataLoader

from paidsearchnav.services import (
    analysis_service,
    audit_service,
    customer_service,
    recommendation_service,
)


def create_customer_loader() -> DataLoader[str, Any]:
    """Create a DataLoader for batch loading customers."""

    async def batch_load_customers(customer_ids: List[str]) -> List[Any]:
        # Fetch all customers in one query
        customers = await customer_service.get_by_ids(customer_ids)

        # Create a mapping of id to customer
        customer_map = {str(c.id): c for c in customers}

        # Return in the same order as requested
        return [customer_map.get(str(cid)) for cid in customer_ids]

    return DataLoader(load_fn=batch_load_customers)


def create_audit_loader() -> DataLoader[str, Any]:
    """Create a DataLoader for batch loading audits."""

    async def batch_load_audits(audit_ids: List[str]) -> List[Any]:
        # Fetch all audits in one query
        audits = await audit_service.get_by_ids(audit_ids)

        # Create a mapping of id to audit
        audit_map = {str(a.id): a for a in audits}

        # Return in the same order as requested
        return [audit_map.get(str(aid)) for aid in audit_ids]

    return DataLoader(load_fn=batch_load_audits)


def create_customer_audits_loader() -> DataLoader[str, List[Any]]:
    """Create a DataLoader for batch loading audits by customer ID."""

    async def batch_load_customer_audits(customer_ids: List[str]) -> List[List[Any]]:
        # Fetch all audits for all customers in one query
        all_audits = await audit_service.get_by_customer_ids(customer_ids)

        # Group audits by customer ID
        audits_by_customer: Dict[str, List[Any]] = {}
        for audit in all_audits:
            customer_id = str(audit.customer_id)
            if customer_id not in audits_by_customer:
                audits_by_customer[customer_id] = []
            audits_by_customer[customer_id].append(audit)

        # Return lists in the same order as requested
        return [audits_by_customer.get(str(cid), []) for cid in customer_ids]

    return DataLoader(load_fn=batch_load_customer_audits)


def create_audit_results_loader() -> DataLoader[str, List[Any]]:
    """Create a DataLoader for batch loading analysis results by audit ID."""

    async def batch_load_audit_results(audit_ids: List[str]) -> List[List[Any]]:
        # Fetch all results for all audits in one query
        all_results = await analysis_service.get_by_audit_ids(audit_ids)

        # Group results by audit ID
        results_by_audit: Dict[str, List[Any]] = {}
        for result in all_results:
            audit_id = str(result.audit_id)
            if audit_id not in results_by_audit:
                results_by_audit[audit_id] = []
            results_by_audit[audit_id].append(result)

        # Return lists in the same order as requested
        return [results_by_audit.get(str(aid), []) for aid in audit_ids]

    return DataLoader(load_fn=batch_load_audit_results)


def create_audit_recommendations_loader() -> DataLoader[str, List[Any]]:
    """Create a DataLoader for batch loading recommendations by audit ID."""

    async def batch_load_audit_recommendations(audit_ids: List[str]) -> List[List[Any]]:
        # Fetch all recommendations for all audits in one query
        all_recommendations = await recommendation_service.get_by_audit_ids(audit_ids)

        # Group recommendations by audit ID
        recommendations_by_audit: Dict[str, List[Any]] = {}
        for rec in all_recommendations:
            audit_id = str(rec.audit_id)
            if audit_id not in recommendations_by_audit:
                recommendations_by_audit[audit_id] = []
            recommendations_by_audit[audit_id].append(rec)

        # Return lists in the same order as requested
        return [recommendations_by_audit.get(str(aid), []) for aid in audit_ids]

    return DataLoader(load_fn=batch_load_audit_recommendations)


class DataLoaderRegistry:
    """Registry for all DataLoaders used in the application."""

    def __init__(self):
        self.customer_loader = create_customer_loader()
        self.audit_loader = create_audit_loader()
        self.customer_audits_loader = create_customer_audits_loader()
        self.audit_results_loader = create_audit_results_loader()
        self.audit_recommendations_loader = create_audit_recommendations_loader()

    def get_customer_loader(self) -> DataLoader[str, Any]:
        """Get the customer DataLoader."""
        return self.customer_loader

    def get_audit_loader(self) -> DataLoader[str, Any]:
        """Get the audit DataLoader."""
        return self.audit_loader

    def get_customer_audits_loader(self) -> DataLoader[str, List[Any]]:
        """Get the customer audits DataLoader."""
        return self.customer_audits_loader

    def get_audit_results_loader(self) -> DataLoader[str, List[Any]]:
        """Get the audit results DataLoader."""
        return self.audit_results_loader

    def get_audit_recommendations_loader(self) -> DataLoader[str, List[Any]]:
        """Get the audit recommendations DataLoader."""
        return self.audit_recommendations_loader
