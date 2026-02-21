"""Junk email detection and management MCP tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.bulk import BulkOperations
from proton_mcp.services.email_ops import EmailService
from proton_mcp.services.junk import JunkDetector

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register junk email tools with the MCP server."""
    email_service = EmailService(config)
    junk_detector = JunkDetector(config)
    bulk_ops = BulkOperations(config)

    @mcp.tool()
    def filter_junk_emails(
        mailbox: str = "INBOX",
        max_emails: int = 100,
        move_to_spam: bool = False,
    ) -> str:
        """Filter and analyze emails for junk/spam content using bulk operations.

        Args:
            mailbox: Mailbox to analyze (default: INBOX)
            max_emails: Maximum number of emails to analyze (default: 100)
            move_to_spam: If True, move detected junk to Spam folder (default: False)

        Returns:
            List of emails with junk analysis results and summary
        """
        try:
            # Get recent emails
            summaries = email_service.search_emails("ALL", mailbox, max_emails)
            if not summaries:
                return json.dumps({"summary": {"total_analyzed": 0, "junk_detected": 0, "moved_to_spam": 0}})

            # Bulk retrieve full email content
            email_ids = [s.id for s in summaries]
            full_emails = bulk_ops.bulk_get_emails(email_ids, mailbox)

            filtered_results: list[dict[str, Any]] = []
            junk_email_ids: list[str] = []

            for summary in summaries:
                full_email = full_emails.get(summary.id)
                if not full_email:
                    continue

                analysis = junk_detector.analyze_email(full_email)
                result: dict[str, Any] = {
                    **summary.to_dict(),
                    "junk_analysis": analysis.to_dict(),
                }

                if move_to_spam and analysis.is_likely_junk:
                    junk_email_ids.append(summary.id)
                    result["action_queued"] = "move_to_spam"

                filtered_results.append(result)

            # Bulk move junk emails if requested
            moved_count = 0
            if move_to_spam and junk_email_ids:
                move_result = bulk_ops.bulk_move_emails(junk_email_ids, "Spam", mailbox)
                moved_count = move_result.get("moved", 0)

                for result in filtered_results:
                    if result.get("action_queued") == "move_to_spam":
                        eid = result["id"]
                        if eid in junk_email_ids[:moved_count]:
                            result["action_taken"] = "moved_to_spam"
                        else:
                            result["action_taken"] = "move_failed"
                        result.pop("action_queued", None)

            junk_count = sum(1 for r in filtered_results if r["junk_analysis"]["is_likely_junk"])
            summary_data = {
                "summary": {
                    "total_analyzed": len(filtered_results),
                    "junk_detected": junk_count,
                    "moved_to_spam": moved_count if move_to_spam else 0,
                }
            }

            return json.dumps([summary_data] + filtered_results, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to filter junk emails: {e}"})

    @mcp.tool()
    def analyze_email_for_junk(email_id: str, mailbox: str = "INBOX") -> str:
        """Analyze a specific email for junk/spam indicators.

        Args:
            email_id: The ID of the email to analyze
            mailbox: Mailbox containing the email (default: INBOX)

        Returns:
            Detailed junk analysis for the email
        """
        try:
            full_email = email_service.get_full_email(email_id, mailbox)
            if not full_email:
                return json.dumps({"error": "Email not found"})

            email_data = {
                "subject": full_email.subject,
                "from": full_email.from_addr,
                "body": full_email.body,
                "id": full_email.id,
            }
            analysis = junk_detector.analyze_email(email_data)

            return json.dumps({
                "email": {
                    "id": full_email.id,
                    "subject": full_email.subject,
                    "from": full_email.from_addr,
                    "date": full_email.date,
                },
                "junk_analysis": analysis.to_dict(),
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to analyze email: {e}"})

    @mcp.tool()
    def create_junk_rule(
        name: str, field: str, pattern: str, score: int = 2
    ) -> str:
        """Create a custom junk detection rule.

        Args:
            name: Human-readable rule name
            field: Field to match against ("subject", "sender", "body")
            pattern: Regular expression pattern
            score: Points to add when matched (default: 2)

        Returns:
            Created rule details
        """
        try:
            rule = junk_detector.create_rule(name, field, pattern, score)
            return json.dumps({
                "status": "success",
                "message": f"Junk rule '{name}' created",
                "rule": rule.to_dict(),
            }, indent=2)
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to create junk rule: {e}"})

    @mcp.tool()
    def update_junk_rule(
        rule_id: str,
        name: str | None = None,
        field: str | None = None,
        pattern: str | None = None,
        score: int | None = None,
        enabled: bool | None = None,
    ) -> str:
        """Update an existing custom junk detection rule.

        Args:
            rule_id: ID of the rule to update
            name: New rule name (optional)
            field: New field to match (optional)
            pattern: New regex pattern (optional)
            score: New score value (optional)
            enabled: Enable/disable the rule (optional)

        Returns:
            Status of the update
        """
        try:
            updates: dict[str, Any] = {}
            if name is not None:
                updates["name"] = name
            if field is not None:
                updates["field"] = field
            if pattern is not None:
                updates["pattern"] = pattern
            if score is not None:
                updates["score"] = score
            if enabled is not None:
                updates["enabled"] = enabled

            if not updates:
                return json.dumps({"status": "error", "message": "No updates provided"})

            success = junk_detector.update_rule(rule_id, **updates)
            if success:
                return json.dumps({
                    "status": "success",
                    "message": f"Junk rule '{rule_id}' updated",
                    "updates": updates,
                })
            return json.dumps({"status": "error", "message": f"Rule '{rule_id}' not found"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to update junk rule: {e}"})

    @mcp.tool()
    def delete_junk_rule(rule_id: str) -> str:
        """Delete a custom junk detection rule.

        Args:
            rule_id: ID of the rule to delete

        Returns:
            Status of the deletion
        """
        try:
            success = junk_detector.delete_rule(rule_id)
            if success:
                return json.dumps({"status": "success", "message": f"Junk rule '{rule_id}' deleted"})
            return json.dumps({"status": "error", "message": f"Rule '{rule_id}' not found"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Failed to delete junk rule: {e}"})
