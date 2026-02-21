"""Inbox summary MCP resource."""

from __future__ import annotations

import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.email_ops import EmailService

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, config: Config) -> None:
    """Register inbox resources with the MCP server."""
    email_service = EmailService(config)

    @mcp.resource("proton://inbox-summary")
    def inbox_summary() -> str:
        """Get a summary of your inbox including recent senders and unread count."""
        try:
            recent = email_service.search_emails("ALL", "INBOX", 10, include_body=False)
            summary = "Recent emails in your Proton inbox:\n\n"
            for email_item in recent:
                summary += f"{email_item.subject} - From: {email_item.from_addr} ({email_item.date})\n"
            summary += f"\nTotal shown: {len(recent)}"
            return summary
        except Exception as e:
            return f"Error: {e}"
