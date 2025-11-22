"""Depth limiting middleware for GraphQL queries."""

from graphql import GraphQLError
from strawberry.extensions import Extension


class DepthLimiterMiddleware(Extension):
    """Middleware to limit query depth."""

    def __init__(self, max_depth: int = 10):
        self.max_depth = max_depth

    def on_validate(self):
        """Validate query depth before execution."""
        # Get the query depth
        depth = self._calculate_depth(self.execution_context.query)

        if depth > self.max_depth:
            raise GraphQLError(
                f"Query depth {depth} exceeds maximum allowed depth of {self.max_depth}"
            )

    def _calculate_depth(self, selection_set, current_depth: int = 0) -> int:
        """Calculate the depth of a query."""
        if not selection_set:
            return current_depth

        max_depth = current_depth

        for selection in selection_set.selections:
            if hasattr(selection, "selection_set"):
                depth = self._calculate_depth(
                    selection.selection_set, current_depth + 1
                )
                max_depth = max(max_depth, depth)

        return max_depth
