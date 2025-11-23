import pytest
from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient
from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator

@pytest.mark.asyncio
async def test_bigquery_query_execution():
    """Test BigQuery query execution with sample query."""
    client = BigQueryClient()

    # Simple test query (won't bill if credentials are configured)
    query = "SELECT 1 as test_value LIMIT 1"

    results = await client.execute_query(query)

    assert len(results) == 1
    assert results[0]["test_value"] == 1

def test_query_validator_rejects_drop_table():
    """Test that DROP TABLE queries are rejected."""
    query = "DROP TABLE my_dataset.my_table"

    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0

def test_query_validator_warns_select_star():
    """Test that SELECT * queries generate warnings."""
    query = "SELECT * FROM my_dataset.my_table"

    result = QueryValidator.validate_query(query)

    assert result["valid"] is True  # Warning, not error
    assert len(result["warnings"]) > 0
