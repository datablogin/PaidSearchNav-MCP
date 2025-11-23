"""Integration tests for GraphQL API."""

from types import SimpleNamespace
from unittest.mock import Mock, patch

import pytest
from httpx import ASGITransport, AsyncClient

from paidsearchnav_mcp.api.main import create_app


class TestGraphQLIntegration:
    """Test GraphQL API integration."""

    @pytest.fixture
    async def client(self):
        """Create test client."""
        app = create_app()

        # Override the dependency for testing
        from paidsearchnav.api.dependencies import get_current_user

        async def mock_get_current_user(request):
            return {"sub": "user123", "id": "user123"}

        app.dependency_overrides[get_current_user] = mock_get_current_user

        transport = ASGITransport(app=app)
        async with AsyncClient(transport=transport, base_url="http://test") as client:
            yield client

        # Clean up
        app.dependency_overrides.clear()

    @pytest.fixture
    def auth_headers(self):
        """Create authorization headers."""
        return {"Authorization": "Bearer test-token"}

    @pytest.mark.asyncio
    async def test_graphql_query_endpoint(self, client, auth_headers):
        """Test GraphQL query endpoint."""
        query = """
        query GetCustomer($id: ID!) {
            customer(id: $id) {
                id
                name
                googleAdsAccountId
                isActive
            }
        }
        """

        variables = {"id": "1"}

        mock_customer = SimpleNamespace(
            id="1",
            name="Test Customer",
            google_ads_account_id="123-456-7890",
            is_active=True,
            created_at=Mock(),
            updated_at=Mock(),
        )

        # Mock DataLoader with async method
        async def mock_load(customer_id):
            return mock_customer

        mock_dataloader = Mock()
        mock_dataloader.load = mock_load
        mock_registry = Mock()
        mock_registry.get_customer_loader = Mock(return_value=mock_dataloader)

        with (
            patch(
                "paidsearchnav.graphql.dataloaders.customer_service.get_by_ids",
                return_value=[mock_customer],
            ),
            patch(
                "paidsearchnav.graphql.resolvers.query.get_current_user",
                return_value={"sub": "user123", "id": "user123"},
            ),
        ):
            response = await client.post(
                "/api/v1/graphql",
                json={"query": query, "variables": variables},
                headers=auth_headers,
            )

            print(f"Response status: {response.status_code}")
            print(f"Response body: {response.text}")
            assert response.status_code == 200
            data = response.json()

            assert "data" in data
            assert "customer" in data["data"]
            assert data["data"]["customer"]["id"] == "1"
            assert data["data"]["customer"]["name"] == "Test Customer"
            assert data["data"]["customer"]["googleAdsAccountId"] == "123-456-7890"
            assert data["data"]["customer"]["isActive"] is True

    @pytest.mark.asyncio
    async def test_graphql_mutation_endpoint(self, client, auth_headers):
        """Test GraphQL mutation endpoint."""
        mutation = """
        mutation TriggerAudit($input: TriggerAuditInput!) {
            triggerAudit(input: $input) {
                id
                customerId
                status
                totalAnalyzers
                completedAnalyzers
            }
        }
        """

        variables = {
            "input": {
                "customerId": "cust1",
                "analyzers": ["keyword_performance"],
                "forceRefresh": True,
            }
        }

        mock_user = {"sub": "user123"}
        mock_audit = SimpleNamespace(
            id="audit1",
            customer_id="cust1",
            status="IN_PROGRESS",
            total_analyzers=1,
            completed_analyzers=0,
            created_at=Mock(),
            started_at=Mock(),
            completed_at=None,
            error_message=None,
        )

        with (
            patch(
                "paidsearchnav.graphql.resolvers.mutation.get_current_user",
                return_value=mock_user,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.create_audit",
                return_value=mock_audit,
            ),
            patch(
                "paidsearchnav.graphql.resolvers.mutation.audit_service.start_audit",
                return_value=None,
            ),
        ):
            response = await client.post(
                "/api/v1/graphql",
                json={"query": mutation, "variables": variables},
                headers=auth_headers,
            )

            assert response.status_code == 200
            data = response.json()

            assert "data" in data
            assert "triggerAudit" in data["data"]
            assert data["data"]["triggerAudit"]["id"] == "audit1"
            assert data["data"]["triggerAudit"]["customerId"] == "cust1"
            assert data["data"]["triggerAudit"]["status"] == "IN_PROGRESS"

    @pytest.mark.asyncio
    async def test_graphql_error_handling(self, client, auth_headers):
        """Test GraphQL error handling."""
        # Invalid query
        query = """
        query {
            invalidField
        }
        """

        mock_user = {"sub": "user123"}

        with patch(
            "paidsearchnav.graphql.resolvers.query.get_current_user",
            return_value=mock_user,
        ):
            response = await client.post(
                "/api/v1/graphql", json={"query": query}, headers=auth_headers
            )

            assert response.status_code == 200  # GraphQL returns 200 even for errors
            data = response.json()

            assert "errors" in data
            assert len(data["errors"]) > 0
            assert "invalidField" in data["errors"][0]["message"]

    @pytest.mark.asyncio
    async def test_graphql_auth_required(self, client):
        """Test that GraphQL endpoint requires authentication."""
        query = """
        query {
            customers {
                id
                name
            }
        }
        """

        # No auth headers
        response = await client.post("/api/v1/graphql", json={"query": query})

        # GraphQL returns 200 with errors in the response
        assert response.status_code == 200
        data = response.json()

        # Should have errors for authentication
        assert "errors" in data
        assert len(data["errors"]) > 0
