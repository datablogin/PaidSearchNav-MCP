"""Configuration for GraphQL settings."""

import os
from typing import Dict


class GraphQLConfig:
    """GraphQL configuration settings."""

    # Environment settings
    ENVIRONMENT = os.getenv("ENVIRONMENT", "development")
    IS_DEVELOPMENT = ENVIRONMENT == "development"

    # Query limits
    MAX_QUERY_DEPTH = int(os.getenv("GRAPHQL_MAX_QUERY_DEPTH", "10"))
    MAX_QUERY_COMPLEXITY = int(os.getenv("GRAPHQL_MAX_QUERY_COMPLEXITY", "1000"))
    MAX_QUERY_ALIASES = int(os.getenv("GRAPHQL_MAX_QUERY_ALIASES", "15"))

    # Pagination defaults
    DEFAULT_PAGE_SIZE = int(os.getenv("GRAPHQL_DEFAULT_PAGE_SIZE", "100"))
    MAX_PAGE_SIZE = int(os.getenv("GRAPHQL_MAX_PAGE_SIZE", "1000"))

    # Field complexity scores for query analysis
    FIELD_COMPLEXITY_SCORES: Dict[str, int] = {
        # Scalar fields - low complexity
        "id": int(os.getenv("GRAPHQL_COMPLEXITY_ID", "1")),
        "name": int(os.getenv("GRAPHQL_COMPLEXITY_NAME", "1")),
        "created_at": int(os.getenv("GRAPHQL_COMPLEXITY_CREATED_AT", "1")),
        "updated_at": int(os.getenv("GRAPHQL_COMPLEXITY_UPDATED_AT", "1")),
        "status": int(os.getenv("GRAPHQL_COMPLEXITY_STATUS", "1")),
        "title": int(os.getenv("GRAPHQL_COMPLEXITY_TITLE", "2")),
        "description": int(os.getenv("GRAPHQL_COMPLEXITY_DESCRIPTION", "2")),
        # List fields - higher complexity due to potential N+1 issues
        "customers": int(os.getenv("GRAPHQL_COMPLEXITY_CUSTOMERS", "10")),
        "audits": int(os.getenv("GRAPHQL_COMPLEXITY_AUDITS", "10")),
        "analysis_results": int(os.getenv("GRAPHQL_COMPLEXITY_ANALYSIS_RESULTS", "20")),
        "recommendations": int(os.getenv("GRAPHQL_COMPLEXITY_RECOMMENDATIONS", "15")),
        # Nested object fields - moderate complexity
        "customer": int(os.getenv("GRAPHQL_COMPLEXITY_CUSTOMER", "5")),
        "audit": int(os.getenv("GRAPHQL_COMPLEXITY_AUDIT", "5")),
        "latest_audit": int(os.getenv("GRAPHQL_COMPLEXITY_LATEST_AUDIT", "10")),
        "analysis_result": int(os.getenv("GRAPHQL_COMPLEXITY_ANALYSIS_RESULT", "8")),
        # JSON fields - higher complexity for processing
        "findings": int(os.getenv("GRAPHQL_COMPLEXITY_FINDINGS", "15")),
        "action_items": int(os.getenv("GRAPHQL_COMPLEXITY_ACTION_ITEMS", "10")),
    }

    @classmethod
    def get_field_complexity(cls, field_name: str) -> int:
        """Get complexity score for a field, with default fallback."""
        return cls.FIELD_COMPLEXITY_SCORES.get(
            field_name, int(os.getenv("GRAPHQL_COMPLEXITY_DEFAULT", "5"))
        )
