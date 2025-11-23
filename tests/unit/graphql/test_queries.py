"""Tests for GraphQL queries."""

from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.graphql.resolvers.query import Query
from paidsearchnav_mcp.graphql.types import AuditStatus, CustomerFilter


class TestGraphQLQueries:
    """Test GraphQL query resolvers."""

    @pytest.fixture
    def mock_info(self):
        """Create mock Info object."""
        mock_request = Mock()
        mock_context = {"request": mock_request, "dataloaders": Mock()}
        return Mock(context=mock_context)

    @pytest.mark.asyncio
    async def test_query_customer(self, mock_info):
        """Test querying a single customer."""
        # Mock dependencies
        mock_user = {"sub": "user123"}
        mock_customer_data = SimpleNamespace(
            id="1",
            name="Test Customer",
            google_ads_account_id="123-456-7890",
            created_at=datetime.now(),
            updated_at=datetime.now(),
            is_active=True,
        )

        # Create async mock for DataLoader
        async def mock_load(customer_id):
            return mock_customer_data

        mock_dataloader = Mock()
        mock_dataloader.load = mock_load
        mock_registry = Mock()
        mock_registry.get_customer_loader = Mock(return_value=mock_dataloader)
        mock_info.context["dataloaders"] = mock_registry

        with patch(
            "paidsearchnav.graphql.resolvers.query.get_current_user",
            return_value=mock_user,
        ):
            query = Query()
            result = await query.customer(mock_info, id="1")

            assert result is not None
            assert result.id == "1"
            assert result.name == "Test Customer"
            assert result.google_ads_account_id == "123-456-7890"
            assert result.is_active is True

    @pytest.mark.asyncio
    async def test_query_customer_not_found(self, mock_info):
        """Test querying a non-existent customer."""
        mock_user = {"sub": "user123"}

        # Create async mock for DataLoader
        async def mock_load(customer_id):
            return None

        mock_dataloader = Mock()
        mock_dataloader.load = mock_load
        mock_registry = Mock()
        mock_registry.get_customer_loader = Mock(return_value=mock_dataloader)
        mock_info.context["dataloaders"] = mock_registry

        with patch(
            "paidsearchnav.graphql.resolvers.query.get_current_user",
            return_value=mock_user,
        ):
            query = Query()
            result = await query.customer(mock_info, id="999")

            assert result is None

    @pytest.mark.asyncio
    async def test_query_customers_with_filter(self, mock_info):
        """Test querying customers with filter."""
        mock_user = {"sub": "user123"}
        mock_customers = [
            SimpleNamespace(
                id="1",
                name="Active Customer",
                google_ads_account_id="123-456-7890",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_active=True,
            ),
            SimpleNamespace(
                id="2",
                name="Another Active",
                google_ads_account_id="098-765-4321",
                created_at=datetime.now(),
                updated_at=datetime.now(),
                is_active=True,
            ),
        ]

        filter_input = CustomerFilter(is_active=True, name_contains="Active")

        with (
            patch(
                "paidsearchnav.graphql.resolvers.query.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.query.customer_service.get_filtered",
                return_value=mock_customers,
            ) as mock_get_filtered,
        ):
            query = Query()
            result = await query.customers(mock_info, filter=filter_input)

            assert len(result) == 2
            assert all(c.is_active for c in result)

            # Check that filter was applied correctly
            mock_get_filtered.assert_called_once_with(
                is_active=True, name__icontains="Active", limit=100, offset=0
            )

    @pytest.mark.asyncio
    async def test_query_audit(self, mock_info):
        """Test querying a single audit."""
        mock_user = {"sub": "user123"}
        mock_audit_data = SimpleNamespace(
            id="1",
            customer_id="cust1",
            status=AuditStatus.COMPLETED,
            created_at=datetime.now(),
            started_at=datetime.now(),
            completed_at=datetime.now(),
            error_message=None,
            total_analyzers=10,
            completed_analyzers=10,
        )

        # Create async mock for DataLoader
        async def mock_load(audit_id):
            return mock_audit_data

        mock_dataloader = Mock()
        mock_dataloader.load = mock_load
        mock_registry = Mock()
        mock_registry.get_audit_loader = Mock(return_value=mock_dataloader)
        mock_info.context["dataloaders"] = mock_registry

        with patch(
            "paidsearchnav.graphql.resolvers.query.get_current_user",
            return_value=mock_user,
        ):
            query = Query()
            result = await query.audit(mock_info, id="1")

            assert result is not None
            assert result.id == "1"
            assert result.customer_id == "cust1"
            assert result.status == AuditStatus.COMPLETED
            assert result.total_analyzers == 10
            assert result.completed_analyzers == 10

    @pytest.mark.asyncio
    async def test_query_audits_by_customer(self, mock_info):
        """Test querying audits for a customer."""
        mock_user = {"sub": "user123"}
        mock_audits = [
            SimpleNamespace(
                id=f"audit{i}",
                customer_id="cust1",
                status=AuditStatus.COMPLETED,
                created_at=datetime.now(),
                started_at=datetime.now(),
                completed_at=datetime.now(),
                error_message=None,
                total_analyzers=10,
                completed_analyzers=10,
            )
            for i in range(3)
        ]

        # Create async mock for DataLoader
        async def mock_load(customer_id):
            return mock_audits

        mock_dataloader = Mock()
        mock_dataloader.load = mock_load
        mock_registry = Mock()
        mock_registry.get_customer_audits_loader = Mock(return_value=mock_dataloader)
        mock_info.context["dataloaders"] = mock_registry

        with patch(
            "paidsearchnav.graphql.resolvers.query.get_current_user",
            return_value=mock_user,
        ):
            query = Query()
            result = await query.audits(mock_info, customer_id="cust1", limit=5)

            assert len(result) == 3
            assert all(a.customer_id == "cust1" for a in result)
