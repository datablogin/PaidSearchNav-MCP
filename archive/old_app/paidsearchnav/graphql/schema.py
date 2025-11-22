"""GraphQL schema definition."""

import strawberry
from strawberry.extensions import MaxAliasesLimiter, QueryDepthLimiter

from .config import GraphQLConfig
from .resolvers import Mutation, Query, Subscription

# Create the schema with security extensions
schema = strawberry.Schema(
    query=Query,
    mutation=Mutation,
    subscription=Subscription,
    extensions=[
        # Prevent deeply nested queries
        QueryDepthLimiter(max_depth=GraphQLConfig.MAX_QUERY_DEPTH),
        # Limit query aliases to prevent abuse
        MaxAliasesLimiter(max_alias_count=GraphQLConfig.MAX_QUERY_ALIASES),
    ],
)
