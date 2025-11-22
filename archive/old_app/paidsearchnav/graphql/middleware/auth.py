"""Authentication middleware for GraphQL."""

from strawberry.extensions import Extension


class AuthMiddleware(Extension):
    """Middleware to handle authentication for GraphQL requests."""

    def on_request_start(self):
        """Authenticate the request before processing."""
        request = self.execution_context.request

        # Skip auth for introspection queries in development
        if self._is_introspection_query() and self._is_development():
            return

        # All other queries require authentication
        # Authentication is handled in individual resolvers
        # This is just for logging/metrics
        pass

    def on_request_end(self):
        """Log request completion."""
        # Could add metrics/logging here
        pass

    def _is_introspection_query(self) -> bool:
        """Check if this is an introspection query."""
        query = self.execution_context.query
        if not query:
            return False

        # Simple check for __schema or __type in query
        query_str = str(query)
        return "__schema" in query_str or "__type" in query_str

    def _is_development(self) -> bool:
        """Check if running in development mode."""
        from paidsearchnav.graphql.config import GraphQLConfig

        return GraphQLConfig.IS_DEVELOPMENT
