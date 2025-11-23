"""Entry point for running paidsearchnav_mcp as a module."""

from paidsearchnav_mcp.server import mcp

if __name__ == "__main__":
    # Run the MCP server
    mcp.run()
