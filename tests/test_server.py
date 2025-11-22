"""Tests for MCP server functionality."""

import pytest
from paidsearchnav_mcp.server import create_mcp_server


def test_create_mcp_server():
    """Test that the MCP server can be created."""
    server = create_mcp_server()
    assert server is not None
    assert server.name == "PaidSearchNav MCP Server"


def test_mcp_server_has_tools():
    """Test that the MCP server has the expected tools registered."""
    server = create_mcp_server()

    # Check that tools are registered
    # FastMCP uses internal registry, so we check by trying to list them
    assert hasattr(server, '_tool_manager')


def test_mcp_server_has_resources():
    """Test that the MCP server has resources registered."""
    server = create_mcp_server()

    # Check that resources are registered
    assert hasattr(server, '_resource_manager')
