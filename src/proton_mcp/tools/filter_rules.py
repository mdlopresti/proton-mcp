"""Filter rules MCP tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.bulk import BulkOperations
from proton_mcp.services.email_ops import EmailService
from proton_mcp.services.filter_rules import FilterRuleEngine

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register filter rule tools with the MCP server."""
    filter_engine = FilterRuleEngine(config)
    email_service = EmailService(config)
    bulk_ops = BulkOperations(config)

    @mcp.tool()
    def create_filter_rule(
        name: str,
        conditions: str,
        actions: str,
        enabled: bool = True,
    ) -> str:
        """Create a new email filtering rule.

        Args:
            name: Unique name for the rule
            conditions: JSON string of conditions (e.g., '{"from": "newsletter@example.com", "subject_contains": "sale"}')
            actions: JSON string of actions (e.g., '{"move_to_folder": "Promotions", "mark_as_read": true}')
            enabled: Whether the rule is active (default: True)

        Returns:
            Status of rule creation
        """
        try:
            conditions_dict = json.loads(conditions)
            actions_dict = json.loads(actions)
        except json.JSONDecodeError as e:
            return json.dumps({"status": "error", "message": f"Invalid JSON format: {e}"})

        try:
            rule = filter_engine.create_rule(name, conditions_dict, actions_dict, enabled)
            return json.dumps({
                "status": "success",
                "message": f"Filter rule '{name}' created successfully",
                "rule": rule.to_dict(),
            }, indent=2)
        except ValueError as e:
            return json.dumps({"status": "error", "message": str(e)})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error creating filter rule: {e}"})

    @mcp.tool()
    def delete_filter_rule(rule_id: str) -> str:
        """Delete a filtering rule by ID.

        Args:
            rule_id: ID of the rule to delete

        Returns:
            Status of rule deletion
        """
        try:
            success = filter_engine.delete_rule(rule_id)
            if success:
                return json.dumps({"status": "success", "message": f"Filter rule '{rule_id}' deleted successfully"})
            return json.dumps({"status": "error", "message": f"Rule '{rule_id}' not found"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error deleting filter rule: {e}"})

    @mcp.tool()
    def update_filter_rule(
        rule_id: str,
        enabled: bool | None = None,
        rule_name: str | None = None,
        conditions: str | None = None,
        actions: str | None = None,
    ) -> str:
        """Update an existing filtering rule.

        Args:
            rule_id: ID of the rule to update
            enabled: Whether the rule should be enabled (optional)
            rule_name: New name for the rule (optional)
            conditions: New conditions JSON string (optional)
            actions: New actions JSON string (optional)

        Returns:
            Status of rule update
        """
        try:
            updates: dict[str, Any] = {}
            if enabled is not None:
                updates["enabled"] = enabled
            if rule_name is not None:
                updates["name"] = rule_name
            if conditions is not None:
                updates["conditions"] = json.loads(conditions)
            if actions is not None:
                updates["actions"] = json.loads(actions)

            if not updates:
                return json.dumps({"status": "error", "message": "No updates provided"})

            success = filter_engine.update_rule(rule_id, **updates)
            if success:
                return json.dumps({
                    "status": "success",
                    "message": f"Filter rule '{rule_id}' updated successfully",
                    "updates": updates,
                }, indent=2)
            return json.dumps({"status": "error", "message": f"Rule '{rule_id}' not found"})
        except json.JSONDecodeError as e:
            return json.dumps({"status": "error", "message": f"Invalid JSON format: {e}"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error updating filter rule: {e}"})

    @mcp.tool()
    def apply_filter_rules(
        mailbox: str = "INBOX",
        max_emails: int = 100,
        chunk_size: int = 50,
    ) -> str:
        """Apply all enabled filtering rules to emails in a mailbox.

        Args:
            mailbox: Mailbox to process (default: INBOX)
            max_emails: Maximum number of emails to process (default: 100)
            chunk_size: Size of processing chunks (default: 50)

        Returns:
            Summary of rules applied and actions taken
        """
        try:
            rules = filter_engine.load_rules()
            enabled_rules = [r for r in rules if r.enabled]
            if not enabled_rules:
                return json.dumps({"message": "No enabled filter rules to apply", "actions_taken": 0})

            summaries = email_service.search_emails("ALL", mailbox, max_emails)
            if not summaries:
                return json.dumps({"message": "No emails to process", "actions_taken": 0})

            # Process in chunks
            email_ids = [s.id for s in summaries]
            total_actions = 0
            rule_stats: dict[str, int] = {}
            actions_log: list[dict[str, Any]] = []

            for i in range(0, len(email_ids), chunk_size):
                chunk_ids = email_ids[i : i + chunk_size]
                full_emails = bulk_ops.bulk_get_emails(chunk_ids, mailbox)

                # Queue actions per rule
                move_queue: dict[str, list[str]] = {}  # folder -> [uids]
                mark_read_queue: list[str] = []
                mark_important_queue: list[str] = []
                delete_queue: list[str] = []

                for uid, email_data in full_emails.items():
                    for rule in enabled_rules:
                        if filter_engine.email_matches_rule(email_data, rule):
                            rule_stats[rule.name] = rule_stats.get(rule.name, 0) + 1
                            total_actions += 1

                            # Queue actions
                            for action_key, action_value in rule.actions.items():
                                if action_key == "move_to_folder" and isinstance(action_value, str):
                                    move_queue.setdefault(action_value, []).append(uid)
                                elif action_key == "mark_as_read" and action_value:
                                    mark_read_queue.append(uid)
                                elif action_key == "mark_as_important" and action_value:
                                    mark_important_queue.append(uid)
                                elif action_key == "delete" and action_value:
                                    delete_queue.append(uid)

                            # Only apply first matching rule per email
                            break

                # Execute queued actions in bulk
                for folder, uids in move_queue.items():
                    result = bulk_ops.bulk_move_emails(uids, folder, mailbox)
                    actions_log.append({
                        "action": "move",
                        "target": folder,
                        "count": result.get("moved", 0),
                    })

                if mark_read_queue:
                    result = bulk_ops.bulk_mark_emails(mark_read_queue, "\\Seen", mailbox)
                    actions_log.append({
                        "action": "mark_read",
                        "count": result.get("marked", 0),
                    })

                if mark_important_queue:
                    result = bulk_ops.bulk_mark_emails(mark_important_queue, "\\Flagged", mailbox)
                    actions_log.append({
                        "action": "mark_important",
                        "count": result.get("marked", 0),
                    })

                if delete_queue:
                    result = bulk_ops.bulk_delete_emails(delete_queue, mailbox)
                    actions_log.append({
                        "action": "delete",
                        "count": result.get("deleted", 0),
                    })

            return json.dumps({
                "emails_processed": len(email_ids),
                "rules_applied": total_actions,
                "rule_match_counts": rule_stats,
                "actions_taken": actions_log,
            }, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to apply filter rules: {e}"})
