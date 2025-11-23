"""Tests for GraphQL schema."""

from strawberry import Schema

from paidsearchnav_mcp.graphql import schema
from paidsearchnav_mcp.graphql.resolvers import Mutation, Query, Subscription


class TestGraphQLSchema:
    """Test GraphQL schema configuration."""

    def test_schema_creation(self):
        """Test that schema is created correctly."""
        assert isinstance(schema, Schema)
        assert schema.query is Query
        assert schema.mutation is Mutation
        assert schema.subscription is Subscription

    def test_schema_introspection(self):
        """Test schema introspection query."""
        introspection_query = """
        query {
            __schema {
                queryType {
                    name
                    fields {
                        name
                        type {
                            name
                        }
                    }
                }
            }
        }
        """

        result = schema.execute_sync(introspection_query)
        assert not result.errors
        assert result.data["__schema"]["queryType"]["name"] == "Query"

        # Check that expected fields exist
        field_names = [
            field["name"] for field in result.data["__schema"]["queryType"]["fields"]
        ]
        assert "customer" in field_names
        assert "customers" in field_names
        assert "audit" in field_names
        assert "audits" in field_names
        assert "analysisResults" in field_names
        assert "recommendations" in field_names

    def test_type_introspection(self):
        """Test type introspection."""
        query = """
        query {
            __type(name: "Customer") {
                name
                kind
                fields {
                    name
                    type {
                        name
                    }
                }
            }
        }
        """

        result = schema.execute_sync(query)
        assert not result.errors
        assert result.data["__type"]["name"] == "Customer"
        assert result.data["__type"]["kind"] == "OBJECT"

        # Check fields
        field_names = [field["name"] for field in result.data["__type"]["fields"]]
        assert "id" in field_names
        assert "name" in field_names
        assert "googleAdsAccountId" in field_names
        # Note: audits and latestAudit fields removed to avoid circular imports
