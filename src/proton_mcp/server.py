"""FastMCP server setup and tool/resource/prompt registration."""

from mcp.server.fastmcp import FastMCP


def create_server() -> FastMCP:
    """Create and configure the MCP server with all tools, resources, and prompts."""
    mcp = FastMCP("ProtonEmailServer")
    # Tools, resources, and prompts will be registered here as modules are extracted
    return mcp
