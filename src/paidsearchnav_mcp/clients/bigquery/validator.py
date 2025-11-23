import re
from typing import Any


class QueryValidator:
    """Validates BigQuery SQL queries for safety.

    Note:
        This validator uses regex patterns which can be bypassed with careful
        formatting. For production use with untrusted queries, consider using
        a proper SQL parser like sqlparse for more robust validation.
    """

    # Disallowed patterns for security
    # Note: These patterns handle multiple whitespace and newlines
    DISALLOWED_PATTERNS = [
        r"DROP\s+TABLE",
        r"DROP\s+DATASET",
        r"DELETE\s+FROM",
        r"TRUNCATE\s+TABLE",
        r"CREATE\s+TABLE",
        r"CREATE\s+VIEW",
        r"CREATE\s+FUNCTION",
        r"CREATE\s+PROCEDURE",
        r"ALTER\s+TABLE",
        r"ALTER\s+DATASET",
        r"GRANT\s+",
        r"REVOKE\s+",
    ]

    # Expensive query patterns to warn about
    WARNING_PATTERNS = [
        (r"SELECT\s+\*\s+FROM", "SELECT * queries can be expensive"),
        (r"CROSS\s+JOIN", "CROSS JOIN can produce very large results"),
        (r"(?i)WHERE.*!=", "!= operators can prevent index usage"),
    ]

    @staticmethod
    def _normalize_query(query: str) -> str:
        """Normalize query by removing comments and normalizing whitespace."""
        # Remove SQL comments (-- style)
        query = re.sub(r"--[^\n]*", " ", query)
        # Remove /* */ style comments
        query = re.sub(r"/\*.*?\*/", " ", query, flags=re.DOTALL)
        # Normalize whitespace (including newlines) to single spaces
        query = re.sub(r"\s+", " ", query)
        return query.strip()

    @staticmethod
    def validate_query(query: str) -> dict[str, Any]:
        """
        Validate a BigQuery SQL query for safety.

        Args:
            query: SQL query to validate

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)

        Example:
            >>> result = QueryValidator.validate_query("SELECT * FROM table")
            >>> print(result['warnings'])
            ['SELECT * queries can be expensive', 'Query has no LIMIT clause']
        """
        errors = []
        warnings = []

        # Normalize query to handle comments and whitespace tricks
        normalized_query = QueryValidator._normalize_query(query)

        # Check for disallowed patterns
        for pattern in QueryValidator.DISALLOWED_PATTERNS:
            if re.search(pattern, normalized_query, re.IGNORECASE):
                operation = pattern.replace(r"\s+", " ").replace(r"\+", "")
                errors.append(f"Query contains disallowed operation: {operation}")

        # Check for warning patterns
        for pattern, message in QueryValidator.WARNING_PATTERNS:
            if re.search(pattern, normalized_query, re.IGNORECASE):
                warnings.append(message)

        # Check for LIMIT clause (cost control)
        if not re.search(r"\bLIMIT\s+\d+", normalized_query, re.IGNORECASE):
            warnings.append("Query has no LIMIT clause - may return large results")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
