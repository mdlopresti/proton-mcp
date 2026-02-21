"""Core email MCP tools: search, get, send, recent."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.email_ops import EmailService
from proton_mcp.services.junk import JunkDetector

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register core email tools with the MCP server."""
    email_service = EmailService(config)
    junk_detector = JunkDetector(config)

    @mcp.tool()
    def search_emails(
        query: str,
        mailbox: str = "INBOX",
        max_results: int = 50,
        exclude_junk: bool = False,
        include_body: bool = True,
    ) -> str:
        """Search emails matching an IMAP query.

        Args:
            query: IMAP search query (e.g., 'FROM "sender@example.com"', 'SUBJECT "important"')
            mailbox: Mailbox to search in (default: INBOX)
            max_results: Maximum number of emails to return (default: 50)
            exclude_junk: If True, filter out likely junk emails (default: False)
            include_body: If True, include body preview (default: True)

        Returns:
            List of email summaries with id, subject, from, date, and body preview
        """
        try:
            fetch_limit = max_results * 2 if exclude_junk else max_results
            results = email_service.search_emails(query, mailbox, fetch_limit, include_body)

            if not exclude_junk:
                return json.dumps([r.to_dict() for r in results[:max_results]], indent=2)

            # Filter out junk emails
            filtered: list[dict[str, Any]] = []
            for email_summary in results:
                if len(filtered) >= max_results:
                    break
                full_email = email_service.get_full_email(email_summary.id, mailbox)
                if full_email:
                    email_data = {
                        "subject": full_email.subject,
                        "from": full_email.from_addr,
                        "body": full_email.body,
                        "id": full_email.id,
                    }
                    analysis = junk_detector.analyze_email(email_data)
                    if not analysis.is_likely_junk:
                        filtered.append(email_summary.to_dict())

            return json.dumps(filtered, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to search emails: {e}"})

    @mcp.tool()
    def get_email_content(email_id: str, mailbox: str = "INBOX") -> str:
        """Get the full content of a specific email.

        Args:
            email_id: The ID of the email to retrieve
            mailbox: Mailbox containing the email (default: INBOX)

        Returns:
            Full email content including subject, from, to, date, and complete body
        """
        try:
            result = email_service.get_full_email(email_id, mailbox)
            if result:
                return json.dumps(result.to_dict(), indent=2)
            return json.dumps({"error": "Email not found"})
        except Exception as e:
            return json.dumps({"error": f"Failed to get email: {e}"})

    @mcp.tool()
    def send_email(to: str, subject: str, body: str, reply_to_id: str | None = None) -> str:
        """Send an email via Proton Mail.

        Args:
            to: Recipient email address
            subject: Email subject
            body: Email body content
            reply_to_id: Optional ID of email being replied to

        Returns:
            Success status and message
        """
        try:
            success = email_service.send_email(to, subject, body, reply_to_id)
            if success:
                return json.dumps({"status": "success", "message": "Email sent successfully"})
            return json.dumps({"status": "error", "message": "Failed to send email"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to send email: {e}"})

    @mcp.tool()
    def get_recent_emails(
        hours: int = 24,
        mailbox: str = "INBOX",
        max_results: int = 50,
        include_body: bool = True,
    ) -> str:
        """Get recent emails from the specified number of hours.

        Args:
            hours: Number of hours back to search (default: 24)
            mailbox: Mailbox to search in (default: INBOX)
            max_results: Maximum number of emails to return (default: 50)
            include_body: If True, include body preview (default: True)

        Returns:
            List of recent emails
        """
        try:
            results = email_service.get_recent_emails(hours, mailbox, max_results, include_body)
            return json.dumps([r.to_dict() for r in results], indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to get recent emails: {e}"})
