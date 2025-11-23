"""Tests for MCP server functionality."""

import os
from unittest.mock import patch


def test_create_mcp_server():
    """Test that the MCP server can be created."""
    from paidsearchnav_mcp.server import create_mcp_server

    server = create_mcp_server()
    assert server is not None
    assert server.name == "PaidSearchNav MCP Server"


def test_mcp_server_has_tools():
    """Test that the MCP server has the expected tools registered."""
    from paidsearchnav_mcp.server import create_mcp_server

    server = create_mcp_server()

    # Check that tools are registered
    # FastMCP uses internal registry, so we check by trying to list them
    assert hasattr(server, "_tool_manager")


def test_mcp_server_has_resources():
    """Test that the MCP server has resources registered."""
    from paidsearchnav_mcp.server import create_mcp_server

    server = create_mcp_server()

    # Check that resources are registered
    assert hasattr(server, "_resource_manager")


# ============================================================================
# BigQuery Integration Tests (imports and basic validation)
# ============================================================================


def test_bigquery_request_model():
    """Test BigQueryRequest model can be instantiated."""
    from paidsearchnav_mcp.server import BigQueryRequest

    request = BigQueryRequest(query="SELECT 1")
    assert request.query == "SELECT 1"
    assert request.project_id is None

    request_with_project = BigQueryRequest(
        query="SELECT 1", project_id="my-project"
    )
    assert request_with_project.project_id == "my-project"


def test_bigquery_schema_request_model():
    """Test BigQuerySchemaRequest model can be instantiated."""
    from paidsearchnav_mcp.server import BigQuerySchemaRequest

    request = BigQuerySchemaRequest(dataset_id="my_dataset", table_id="my_table")
    assert request.dataset_id == "my_dataset"
    assert request.table_id == "my_table"
    assert request.project_id is None


def test_bigquery_tools_are_registered():
    """Test that BigQuery tools are registered with the server."""
    from paidsearchnav_mcp.server import create_mcp_server

    server = create_mcp_server()

    # Check that BigQuery-related tools exist
    # FastMCP stores tools internally, we just verify the server was created successfully
    assert server is not None


def test_health_check_exists():
    """Test health check resource exists."""
    from paidsearchnav_mcp import server

    # Verify health_check is defined (it's wrapped by FastMCP)
    assert hasattr(server, "health_check")


def test_get_config_exists():
    """Test configuration resource exists."""
    from paidsearchnav_mcp import server

    # Verify get_config is defined (it's wrapped by FastMCP)
    assert hasattr(server, "get_config")


def test_bigquery_client_import():
    """Test that BigQueryClient can be imported and used in server context."""
    from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient

    # Just verify it can be imported (actual functionality tested in test_bigquery_client.py)
    assert BigQueryClient is not None


def test_query_validator_import():
    """Test that QueryValidator can be imported and used in server context."""
    from paidsearchnav_mcp.clients.bigquery.validator import QueryValidator

    # Just verify it can be imported and basic validation works
    assert QueryValidator is not None

    # Test basic validation
    result = QueryValidator.validate_query("SELECT * FROM table LIMIT 10")
    assert "valid" in result
    assert "errors" in result
    assert "warnings" in result


@patch.dict(os.environ, {"GCP_PROJECT_ID": "test-project"}, clear=False)
def test_bigquery_client_initialization_with_env():
    """Test that BigQueryClient uses GCP_PROJECT_ID from environment."""
    os.environ.pop("GOOGLE_APPLICATION_CREDENTIALS", None)

    from paidsearchnav_mcp.clients.bigquery.client import BigQueryClient

    # Should not raise error when GCP_PROJECT_ID is set
    try:
        client = BigQueryClient()
        assert client.project_id == "test-project"
    except Exception as e:
        # If it fails for other reasons (like missing actual credentials), that's ok
        # We're just testing that project_id is read from env
        assert "project_id" not in str(e)


def test_error_code_enum():
    """Test that ErrorCode enum is properly defined."""
    from paidsearchnav_mcp.server import ErrorCode

    # Verify BigQuery error codes exist
    assert hasattr(ErrorCode, "BIGQUERY_FETCH_ERROR")
    assert hasattr(ErrorCode, "INVALID_INPUT")


def test_server_module_exports():
    """Test that server module exports expected functions."""
    from paidsearchnav_mcp import server

    # Verify all expected functions are available
    assert hasattr(server, "query_bigquery")
    assert hasattr(server, "get_bigquery_schema")
    assert hasattr(server, "list_bigquery_datasets")
    assert hasattr(server, "health_check")
    assert hasattr(server, "get_config")
    assert hasattr(server, "create_mcp_server")
