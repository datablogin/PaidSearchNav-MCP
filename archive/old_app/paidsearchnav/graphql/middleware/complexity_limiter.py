"""Complexity limiting middleware for GraphQL queries."""

from graphql import GraphQLError
from strawberry.extensions import Extension

from paidsearchnav.graphql.config import GraphQLConfig


class ComplexityLimiterMiddleware(Extension):
    """Middleware to limit query complexity."""

    def __init__(self, max_complexity: int = None):
        self.max_complexity = max_complexity or GraphQLConfig.MAX_QUERY_COMPLEXITY
        # Use configurable complexity scores
        self.field_complexity = GraphQLConfig.FIELD_COMPLEXITY_SCORES

    def on_validate(self):
        """Calculate and validate query complexity."""
        complexity = self._calculate_complexity(self.execution_context.query)

        if complexity > self.max_complexity:
            raise GraphQLError(
                f"Query complexity {complexity} exceeds maximum allowed complexity of {self.max_complexity}"
            )

    def _calculate_complexity(self, selection_set, multiplier: int = 1) -> int:
        """Calculate the complexity of a query."""
        if not selection_set:
            return 0

        total_complexity = 0

        for selection in selection_set.selections:
            field_name = selection.name.value

            # Get base complexity for this field
            base_complexity = self.field_complexity.get(field_name, 1)

            # Check for list multipliers in arguments
            if hasattr(selection, "arguments"):
                for arg in selection.arguments:
                    if arg.name.value in ["limit", "first", "last"]:
                        base_complexity *= min(arg.value.value, 100)

            # Add field complexity
            total_complexity += base_complexity * multiplier

            # Recursively calculate nested selections
            if hasattr(selection, "selection_set"):
                total_complexity += self._calculate_complexity(
                    selection.selection_set, multiplier * base_complexity
                )

        return total_complexity
