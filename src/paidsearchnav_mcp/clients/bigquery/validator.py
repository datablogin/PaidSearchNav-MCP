import re
from typing import Any


class QueryValidator:
    """Validates BigQuery SQL queries for safety."""

    # Disallowed patterns for security
    DISALLOWED_PATTERNS = [
        r"DROP\s+TABLE",
        r"DROP\s+DATASET",
        r"DELETE\s+FROM",
        r"TRUNCATE\s+TABLE",
        r"CREATE\s+TABLE",
        r"ALTER\s+TABLE",
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
    def validate_query(query: str) -> dict[str, Any]:
        """
        Validate a BigQuery SQL query for safety.

        Returns:
            Dict with 'valid' (bool), 'errors' (list), 'warnings' (list)
        """
        errors = []
        warnings = []

        # Check for disallowed patterns
        for pattern in QueryValidator.DISALLOWED_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                errors.append(f"Query contains disallowed operation: {pattern}")

        # Check for warning patterns
        for pattern, message in QueryValidator.WARNING_PATTERNS:
            if re.search(pattern, query, re.IGNORECASE):
                warnings.append(message)

        # Check for LIMIT clause (cost control)
        if not re.search(r"\bLIMIT\s+\d+", query, re.IGNORECASE):
            warnings.append("Query has no LIMIT clause - may return large results")

        return {"valid": len(errors) == 0, "errors": errors, "warnings": warnings}
