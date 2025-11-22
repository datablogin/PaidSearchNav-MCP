"""PaidSearchNav MCP Server.

A Model Context Protocol server providing access to Google Ads and BigQuery data.
"""

__version__ = "1.0.0"

from paidsearchnav_mcp.server import create_mcp_server

__all__ = ["create_mcp_server"]
