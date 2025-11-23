"""Unit tests for BigQuery client and validator.

Note: These tests use mocks to avoid requiring real BigQuery credentials
and to ensure deterministic, fast test execution.
"""

import os
from unittest.mock import Mock, patch

import pytest

from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient
from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator

# ============================================================================
# BigQueryClient Tests
# ============================================================================


@pytest.mark.asyncio
@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
async def test_execute_query_success(mock_bigquery_client):
    """Test successful query execution."""
    # Clear GOOGLE_APPLICATION_CREDENTIALS to use mock client
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Setup mock
    mock_query_job = Mock()
    mock_row = {"test_value": 1, "test_string": "hello"}
    mock_query_job.result.return_value = [mock_row]
    mock_bigquery_client.return_value.query.return_value = mock_query_job

    # Execute test
    client = BigQueryClient()
    results = await client.execute_query("SELECT 1 as test_value")

    # Verify
    assert len(results) == 1
    assert results[0]["test_value"] == 1
    assert results[0]["test_string"] == "hello"
    mock_bigquery_client.return_value.query.assert_called_once()


@pytest.mark.asyncio
@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
async def test_execute_query_with_timeout(mock_bigquery_client):
    """Test query execution respects timeout parameter."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Setup mock
    mock_query_job = Mock()
    mock_query_job.result.return_value = []
    mock_bigquery_client.return_value.query.return_value = mock_query_job

    # Execute with custom timeout
    client = BigQueryClient()
    await client.execute_query("SELECT 1", timeout=60)

    # Verify timeout was passed to result()
    mock_query_job.result.assert_called_once()
    call_kwargs = mock_query_job.result.call_args[1]
    assert call_kwargs["timeout"] == 60


@pytest.mark.asyncio
@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
async def test_get_table_schema_success(mock_bigquery_client):
    """Test successful table schema retrieval."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Setup mock table
    mock_field_1 = Mock()
    mock_field_1.name = "id"
    mock_field_1.field_type = "INTEGER"
    mock_field_1.mode = "REQUIRED"
    mock_field_1.description = "User ID"

    mock_field_2 = Mock()
    mock_field_2.name = "name"
    mock_field_2.field_type = "STRING"
    mock_field_2.mode = "NULLABLE"
    mock_field_2.description = "User name"

    mock_table = Mock()
    mock_table.schema = [mock_field_1, mock_field_2]
    mock_table.num_rows = 1000
    mock_table.num_bytes = 50000

    mock_bigquery_client.return_value.get_table.return_value = mock_table

    # Execute test
    client = BigQueryClient()
    schema_info = await client.get_table_schema("my_dataset", "my_table")

    # Verify
    assert schema_info["table"] == "test-project.my_dataset.my_table"
    assert len(schema_info["schema"]) == 2
    assert schema_info["schema"][0]["name"] == "id"
    assert schema_info["schema"][0]["type"] == "INTEGER"
    assert schema_info["schema"][1]["name"] == "name"
    assert schema_info["num_rows"] == 1000
    assert schema_info["size_bytes"] == 50000


@pytest.mark.asyncio
@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
async def test_estimate_query_cost_success(mock_bigquery_client):
    """Test query cost estimation."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Setup mock
    mock_query_job = Mock()
    mock_query_job.total_bytes_processed = 1024**3  # 1 GB
    mock_query_job.total_bytes_billed = 1024**3 * 10  # 10 GB (minimum billing)

    mock_bigquery_client.return_value.query.return_value = mock_query_job

    # Execute test
    client = BigQueryClient()
    cost_info = await client.estimate_query_cost("SELECT * FROM large_table")

    # Verify
    assert cost_info["bytes_processed"] == 1024**3
    assert cost_info["bytes_billed"] == 1024**3 * 10
    assert "estimated_cost_usd" in cost_info
    assert "is_cached" in cost_info
    assert cost_info["is_cached"] is False


@pytest.mark.asyncio
@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
async def test_estimate_query_cost_cached(mock_bigquery_client):
    """Test cost estimation for cached queries."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    # Setup mock for cached query (0 bytes processed)
    mock_query_job = Mock()
    mock_query_job.total_bytes_processed = 0
    mock_query_job.total_bytes_billed = 0

    mock_bigquery_client.return_value.query.return_value = mock_query_job

    # Execute test
    client = BigQueryClient()
    cost_info = await client.estimate_query_cost("SELECT * FROM cached_table")

    # Verify cached query is detected
    assert cost_info["is_cached"] is True
    assert cost_info["estimated_cost_usd"] == 0


def test_bigquery_client_requires_project_id():
    """Test that BigQueryClient raises ValueError without project_id."""
    # Clear env var
    if "GCP_PROJECT_ID" in os.environ:
        del os.environ["GCP_PROJECT_ID"]

    # Should raise ValueError
    with pytest.raises(ValueError, match="project_id must be provided"):
        BigQueryClient()


@patch("paidsearchnav_mcp.clients.bigquery.client.bigquery.Client")
def test_bigquery_client_accepts_explicit_project_id(mock_bigquery_client):
    """Test that explicit project_id works without env var."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)
    client = BigQueryClient(project_id="explicit-project")
    assert client.project_id == "explicit-project"


# ============================================================================
# QueryValidator Tests
# ============================================================================


def test_validator_rejects_drop_table():
    """Test that DROP TABLE queries are rejected."""
    query = "DROP TABLE my_dataset.my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0
    assert any("DROP" in error for error in result["errors"])


def test_validator_rejects_drop_dataset():
    """Test that DROP DATASET queries are rejected."""
    query = "DROP DATASET my_dataset"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_delete_from():
    """Test that DELETE FROM queries are rejected."""
    query = "DELETE FROM my_table WHERE id = 1"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_truncate():
    """Test that TRUNCATE queries are rejected."""
    query = "TRUNCATE TABLE my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_create_table():
    """Test that CREATE TABLE queries are rejected."""
    query = "CREATE TABLE my_table (id INT64)"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_create_view():
    """Test that CREATE VIEW queries are rejected."""
    query = "CREATE VIEW my_view AS SELECT * FROM my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_create_function():
    """Test that CREATE FUNCTION queries are rejected."""
    query = "CREATE FUNCTION my_function() RETURNS INT64 AS (42)"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_alter_table():
    """Test that ALTER TABLE queries are rejected."""
    query = "ALTER TABLE my_table ADD COLUMN new_col STRING"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_rejects_grant():
    """Test that GRANT queries are rejected."""
    query = "GRANT SELECT ON my_table TO user@example.com"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_warns_select_star():
    """Test that SELECT * queries generate warnings."""
    query = "SELECT * FROM my_dataset.my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is True  # Warning, not error
    assert len(result["warnings"]) > 0
    assert any("SELECT *" in warning for warning in result["warnings"])


def test_validator_warns_no_limit():
    """Test that queries without LIMIT generate warnings."""
    query = "SELECT id, name FROM my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is True
    assert any("LIMIT" in warning for warning in result["warnings"])


def test_validator_warns_cross_join():
    """Test that CROSS JOIN queries generate warnings."""
    query = "SELECT * FROM table1 CROSS JOIN table2 LIMIT 100"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is True
    assert any("CROSS JOIN" in warning for warning in result["warnings"])


def test_validator_accepts_safe_query():
    """Test that safe SELECT queries are accepted."""
    query = "SELECT id, name FROM my_table WHERE id = 1 LIMIT 10"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is True
    assert len(result["errors"]) == 0


def test_validator_handles_comments():
    """Test that validator handles SQL comments correctly."""
    # Comments should not bypass validation
    query = "-- This is a comment\nDROP TABLE my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_handles_multiline_comments():
    """Test that validator handles /* */ style comments."""
    query = "/* Comment */ DROP /* inline */ TABLE my_table"
    result = QueryValidator.validate_query(query)

    assert result["valid"] is False
    assert len(result["errors"]) > 0


def test_validator_handles_whitespace_tricks():
    """Test that validator handles whitespace bypass attempts."""
    # Multiple spaces
    query = "DROP    TABLE my_table"
    result = QueryValidator.validate_query(query)
    assert result["valid"] is False

    # Newlines
    query = "DROP\nTABLE my_table"
    result = QueryValidator.validate_query(query)
    assert result["valid"] is False

    # Tabs
    query = "DROP\tTABLE my_table"
    result = QueryValidator.validate_query(query)
    assert result["valid"] is False


def test_validator_normalize_query():
    """Test the query normalization helper method."""
    query = """
    -- Comment line
    SELECT /* inline comment */ *
    FROM    table
    WHERE id = 1
    """
    normalized = QueryValidator._normalize_query(query)

    # Should have comments removed and normalized whitespace
    assert "--" not in normalized
    assert "/*" not in normalized
    assert "\n" not in normalized
    assert "  " not in normalized  # No double spaces


# ============================================================================
# Integration Test Marker
# ============================================================================


@pytest.mark.integration
@pytest.mark.asyncio
async def test_bigquery_real_connection():
    """Integration test with real BigQuery (requires credentials).

    This test is marked as 'integration' and will only run when explicitly
    requested with: pytest -m integration

    Requires:
    - GCP_PROJECT_ID environment variable
    - Valid BigQuery credentials (gcloud auth or service account)
    """
    client = BigQueryClient()

    # Simple query that won't bill much
    query = "SELECT 1 as test_value LIMIT 1"
    results = await client.execute_query(query)

    assert len(results) == 1
    assert results[0]["test_value"] == 1
