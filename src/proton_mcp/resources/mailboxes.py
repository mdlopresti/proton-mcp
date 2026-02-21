"""Mailboxes/folders MCP resource."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.config import Config

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, config: Config) -> None:
    """Register mailbox resources with the MCP server."""

    @mcp.resource("proton://mailboxes")
    def mailboxes() -> str:
        """Get list of available mailboxes/folders."""
        try:
            with IMAPClient(config) as imap:
                folders = imap.list_mailboxes()
            return json.dumps(folders, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to list mailboxes: {e}"})
