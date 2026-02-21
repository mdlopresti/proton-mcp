"""FastMCP server setup and tool/resource/prompt registration."""

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.prompts import create_filter_rule as create_filter_rule_prompt
from proton_mcp.prompts import email_triage as email_triage_prompt
from proton_mcp.resources import filter_rules as filter_rules_resource
from proton_mcp.resources import inbox as inbox_resource
from proton_mcp.resources import junk as junk_resource
from proton_mcp.resources import mailboxes as mailboxes_resource
from proton_mcp.resources import unsubscribe as unsubscribe_resource
from proton_mcp.tools import bulk as bulk_tools
from proton_mcp.tools import core as core_tools
from proton_mcp.tools import filter_rules as filter_rules_tools
from proton_mcp.tools import folders as folder_tools
from proton_mcp.tools import junk as junk_tools
from proton_mcp.tools import unsubscribe as unsubscribe_tools


def create_server() -> FastMCP:
    """Create and configure the MCP server with all tools, resources, and prompts."""
    mcp = FastMCP("ProtonEmailServer")
    config = Config.from_env()

    # Register tools
    core_tools.register_tools(mcp, config)
    junk_tools.register_tools(mcp, config)
    unsubscribe_tools.register_tools(mcp, config)
    folder_tools.register_tools(mcp, config)
    filter_rules_tools.register_tools(mcp, config)
    bulk_tools.register_tools(mcp, config)

    # Register resources
    inbox_resource.register_resources(mcp, config)
    mailboxes_resource.register_resources(mcp, config)
    filter_rules_resource.register_resources(mcp, config)
    junk_resource.register_resources(mcp, config)
    unsubscribe_resource.register_resources(mcp, config)

    # Register prompts
    create_filter_rule_prompt.register_prompts(mcp, config)
    email_triage_prompt.register_prompts(mcp, config)

    return mcp
