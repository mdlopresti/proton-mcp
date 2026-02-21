"""Unsubscribe detection and management MCP tools."""

from __future__ import annotations

import json
import logging
from datetime import UTC, datetime, timedelta
from typing import Any

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.bulk import BulkOperations
from proton_mcp.services.email_ops import EmailService
from proton_mcp.services.unsubscribe import UnsubscribeService

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register unsubscribe tools with the MCP server."""
    email_service = EmailService(config)
    unsub_service = UnsubscribeService(config)
    bulk_ops = BulkOperations(config)

    @mcp.tool()
    def find_unsubscribe_links(email_id: str, mailbox: str = "INBOX") -> str:
        """Find unsubscribe links and methods in a specific email.

        Args:
            email_id: The ID of the email to analyze
            mailbox: Mailbox containing the email (default: INBOX)

        Returns:
            Dictionary with unsubscribe methods found
        """
        try:
            # Get full email content with HTML for unsubscribe detection
            full_emails = bulk_ops.bulk_get_emails_with_html([email_id], mailbox)
            email_data = full_emails.get(email_id)
            if not email_data:
                return json.dumps({"error": "Email not found"})

            methods = unsub_service.find_unsubscribe_links(email_data)
            return json.dumps(
                {
                    "email_id": email_id,
                    "total_methods": len(methods),
                    "has_one_click": any(m.one_click for m in methods),
                    "unsubscribe_methods": [m.to_dict() for m in methods],
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to find unsubscribe links: {e}"})

    @mcp.tool()
    def unsubscribe_from_email(email_id: str, mailbox: str = "INBOX", confirm: bool = False) -> str:
        """Unsubscribe from a mailing list using links found in an email.

        Args:
            email_id: The ID of the email containing unsubscribe links
            mailbox: Mailbox containing the email (default: INBOX)
            confirm: Must be True to actually execute unsubscribe (safety measure)

        Returns:
            Result of unsubscribe attempt
        """
        try:
            if not confirm:
                return json.dumps(
                    {
                        "error": "Safety measure: set confirm=True to execute unsubscribe",
                        "message": "Use find_unsubscribe_links first to see available methods",
                    }
                )

            full_emails = bulk_ops.bulk_get_emails_with_html([email_id], mailbox)
            email_data = full_emails.get(email_id)
            if not email_data:
                return json.dumps({"error": "Email not found"})

            methods = unsub_service.find_unsubscribe_links(email_data)
            if not methods:
                return json.dumps({"error": "No unsubscribe methods found in this email"})

            # Try the first available method (prefer one-click)
            method = next((m for m in methods if m.one_click), methods[0])
            success = unsub_service.execute_unsubscribe(method)

            return json.dumps(
                {
                    "email_info": {
                        "id": email_data.get("id", email_id),
                        "subject": email_data.get("subject", ""),
                        "from": email_data.get("from", ""),
                    },
                    "unsubscribe_result": {
                        "success": success,
                        "method_used": method.to_dict(),
                    },
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to unsubscribe: {e}"})

    @mcp.tool()
    def bulk_find_unsubscribe_opportunities(mailbox: str = "INBOX", max_emails: int = 100) -> str:
        """Scan recent emails to find unsubscribe opportunities from mailing lists.

        Args:
            mailbox: Mailbox to scan (default: INBOX)
            max_emails: Maximum emails to analyze (default: 100)

        Returns:
            List of emails with unsubscribe opportunities
        """
        try:
            since = datetime.now(tz=UTC) - timedelta(days=30)
            date_str = since.strftime("%d-%b-%Y")
            query = f"SINCE {date_str}"

            summaries = email_service.search_emails(query, mailbox, max_emails)
            if not summaries:
                return json.dumps(
                    {"summary": {"emails_analyzed": 0, "unsubscribe_opportunities": 0, "one_click_available": 0}}
                )

            email_ids = [s.id for s in summaries]
            full_emails = bulk_ops.bulk_get_emails_with_html(email_ids, mailbox)

            opportunities: list[dict[str, Any]] = []
            processed = 0

            for summary in summaries:
                email_data = full_emails.get(summary.id)
                if not email_data:
                    continue

                processed += 1
                try:
                    methods = unsub_service.find_unsubscribe_links(email_data)
                    if methods:
                        opportunities.append(
                            {
                                **summary.to_dict(),
                                "unsubscribe_info": {
                                    "total_methods": len(methods),
                                    "has_one_click": any(m.one_click for m in methods),
                                    "unsubscribe_methods": [m.to_dict() for m in methods],
                                },
                            }
                        )
                except Exception as e:
                    logger.warning("Failed to analyze email %s: %s", summary.id, e)
                    continue

            summary_data = {
                "summary": {
                    "emails_analyzed": processed,
                    "unsubscribe_opportunities": len(opportunities),
                    "one_click_available": sum(1 for o in opportunities if o["unsubscribe_info"]["has_one_click"]),
                }
            }

            return json.dumps([summary_data] + opportunities, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to find unsubscribe opportunities: {e}"})

    @mcp.tool()
    def get_mailing_list_senders(mailbox: str = "INBOX", max_emails: int = 200) -> str:
        """Identify frequent senders that might be mailing lists.

        Args:
            mailbox: Mailbox to analyze (default: INBOX)
            max_emails: Maximum emails to analyze (default: 200)

        Returns:
            List of potential mailing list senders with email counts
        """
        try:
            since = datetime.now(tz=UTC) - timedelta(days=30)
            date_str = since.strftime("%d-%b-%Y")
            query = f"SINCE {date_str}"

            summaries = email_service.search_emails(query, mailbox, max_emails, include_body=False)
            if not summaries:
                return json.dumps([])

            # Count emails per sender
            sender_data: dict[str, dict[str, Any]] = {}
            for s in summaries:
                addr = s.from_addr.strip()
                if not addr:
                    continue
                if addr not in sender_data:
                    sender_data[addr] = {"count": 0, "subjects": [], "latest_date": s.date}
                sender_data[addr]["count"] += 1
                sender_data[addr]["subjects"].append(s.subject or "No Subject")

            # Filter for potential mailing lists (min 2 emails)
            mailing_lists: list[dict[str, Any]] = []
            for sender, data in sender_data.items():
                if data["count"] >= 2:
                    is_likely = any(
                        [
                            "newsletter" in sender.lower(),
                            "noreply" in sender.lower(),
                            "marketing" in sender.lower(),
                            "updates" in sender.lower(),
                            "notifications" in sender.lower(),
                            data["count"] >= 5,
                        ]
                    )
                    mailing_lists.append(
                        {
                            "sender": sender,
                            "email_count": data["count"],
                            "likely_mailing_list": is_likely,
                            "latest_date": data["latest_date"],
                            "sample_subjects": data["subjects"][:3],
                        }
                    )

            mailing_lists.sort(key=lambda x: x["email_count"], reverse=True)
            return json.dumps(mailing_lists, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to analyze mailing list senders: {e}"})

    @mcp.tool()
    def add_sender_preference(sender: str, action: str) -> str:
        """Add an unsubscribe preference for a sender.

        Args:
            sender: Email address or domain
            action: "always_unsubscribe" or "never_unsubscribe"

        Returns:
            Status of the operation
        """
        try:
            success = unsub_service.add_sender_preference(sender, action)
            if success:
                return json.dumps({"status": "success", "message": f"Preference added for '{sender}': {action}"})
            return json.dumps({"status": "error", "message": f"Preference for '{sender}' already exists"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to add preference: {e}"})

    @mcp.tool()
    def remove_sender_preference(sender: str) -> str:
        """Remove an unsubscribe preference for a sender.

        Args:
            sender: Email address or domain to remove preference for

        Returns:
            Status of the operation
        """
        try:
            success = unsub_service.remove_sender_preference(sender)
            if success:
                return json.dumps({"status": "success", "message": f"Preference removed for '{sender}'"})
            return json.dumps({"status": "error", "message": f"No preference found for '{sender}'"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to remove preference: {e}"})

    @mcp.tool()
    def add_detection_pattern(name: str, pattern: str, pattern_type: str = "tracker_domain") -> str:
        """Add a detection pattern for tracker URLs used in unsubscribe links.

        Args:
            name: Human-readable pattern name
            pattern: Regular expression pattern
            pattern_type: Pattern type (default: "tracker_domain")

        Returns:
            Created pattern details
        """
        try:
            result = unsub_service.add_detection_pattern(name, pattern, pattern_type)
            return json.dumps(
                {
                    "status": "success",
                    "message": f"Detection pattern '{name}' added",
                    "pattern": result.to_dict(),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to add detection pattern: {e}"})

    @mcp.tool()
    def remove_detection_pattern(pattern_id: str) -> str:
        """Remove a detection pattern by ID.

        Args:
            pattern_id: ID of the pattern to remove

        Returns:
            Status of the operation
        """
        try:
            success = unsub_service.remove_detection_pattern(pattern_id)
            if success:
                return json.dumps({"status": "success", "message": f"Detection pattern '{pattern_id}' removed"})
            return json.dumps({"status": "error", "message": f"Pattern '{pattern_id}' not found"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to remove detection pattern: {e}"})
