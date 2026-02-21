"""Bulk email operations MCP tools."""

from __future__ import annotations

import json
import logging
from typing import Any

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.bulk import BulkOperations
from proton_mcp.utils.validation import validate_email_id, validate_folder_name

logger = logging.getLogger(__name__)


def _parse_email_ids(email_ids: str) -> list[str]:
    """Parse and validate comma-separated email IDs."""
    validated = validate_email_id(email_ids)
    return [eid.strip() for eid in validated.split(",") if eid.strip()]


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register bulk operation tools with the MCP server."""
    bulk_ops = BulkOperations(config)

    @mcp.tool()
    def bulk_move_emails(email_ids: str, target_folder: str, source_folder: str = "INBOX") -> str:
        """Move multiple emails to a folder efficiently using bulk operations.

        Args:
            email_ids: Comma-separated list of email IDs to move
            target_folder: Destination folder name
            source_folder: Source folder name (default: INBOX)

        Returns:
            Dictionary with move operation results
        """
        try:
            id_list = _parse_email_ids(email_ids)
            target_folder = validate_folder_name(target_folder)
            source_folder = validate_folder_name(source_folder)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        if not id_list:
            return json.dumps({"error": "No valid email IDs provided"})

        try:
            result = bulk_ops.bulk_move_emails(id_list, target_folder, source_folder)
            return json.dumps(
                {
                    "status": "success" if result.get("success") else "error",
                    "moved": result.get("moved", 0),
                    "total": len(id_list),
                    "target": target_folder,
                    "error": result.get("error"),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to bulk move emails: {e}"})

    @mcp.tool()
    def bulk_mark_emails_as_read(email_ids: str, mailbox: str = "INBOX", mark_read: bool = True) -> str:
        """Bulk mark emails as read or unread.

        Args:
            email_ids: Comma-separated list of email IDs to mark
            mailbox: Mailbox containing the emails (default: INBOX)
            mark_read: True to mark as read, False to mark as unread

        Returns:
            Dictionary with marking operation results
        """
        try:
            id_list = _parse_email_ids(email_ids)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        if not id_list:
            return json.dumps({"error": "No valid email IDs provided"})

        try:
            result = bulk_ops.bulk_mark_emails(id_list, "\\Seen", mailbox, add=mark_read)
            return json.dumps(
                {
                    "status": "success" if result.get("success") else "error",
                    "marked": result.get("marked", 0),
                    "total": len(id_list),
                    "action": "marked_as_read" if mark_read else "marked_as_unread",
                    "error": result.get("error"),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to bulk mark emails: {e}"})

    @mcp.tool()
    def bulk_mark_emails_as_important(email_ids: str, mailbox: str = "INBOX", mark_important: bool = True) -> str:
        """Bulk mark emails as important/flagged or remove importance.

        Args:
            email_ids: Comma-separated list of email IDs to mark
            mailbox: Mailbox containing the emails (default: INBOX)
            mark_important: True to mark as important, False to remove importance

        Returns:
            Dictionary with marking operation results
        """
        try:
            id_list = _parse_email_ids(email_ids)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        if not id_list:
            return json.dumps({"error": "No valid email IDs provided"})

        try:
            result = bulk_ops.bulk_mark_emails(id_list, "\\Flagged", mailbox, add=mark_important)
            return json.dumps(
                {
                    "status": "success" if result.get("success") else "error",
                    "marked": result.get("marked", 0),
                    "total": len(id_list),
                    "action": "marked_as_important" if mark_important else "removed_importance",
                    "error": result.get("error"),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to bulk mark emails as important: {e}"})

    @mcp.tool()
    def bulk_delete_emails(email_ids: str, mailbox: str = "INBOX", permanent: bool = False) -> str:
        """Bulk delete emails (move to Trash or permanent deletion).

        Args:
            email_ids: Comma-separated list of email IDs to delete
            mailbox: Source mailbox (default: INBOX)
            permanent: If True, permanently delete; if False, move to Trash

        Returns:
            Dictionary with deletion results
        """
        try:
            id_list = _parse_email_ids(email_ids)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        if not id_list:
            return json.dumps({"error": "No valid email IDs provided"})

        try:
            result = bulk_ops.bulk_delete_emails(id_list, mailbox, permanent)
            return json.dumps(
                {
                    "status": "success" if result.get("success") else "error",
                    "deleted": result.get("deleted", 0),
                    "total": len(id_list),
                    "permanent": permanent,
                    "error": result.get("error"),
                },
                indent=2,
            )
        except Exception as e:
            return json.dumps({"error": f"Failed to bulk delete emails: {e}"})

    @mcp.tool()
    def bulk_get_emails(email_ids: str, mailbox: str = "INBOX") -> str:
        """Efficiently retrieve multiple emails in bulk.

        Args:
            email_ids: Comma-separated list of email IDs to retrieve
            mailbox: Mailbox containing the emails (default: INBOX)

        Returns:
            List of email objects with full content
        """
        try:
            id_list = _parse_email_ids(email_ids)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        if not id_list:
            return json.dumps({"error": "No valid email IDs provided"})

        try:
            emails_dict = bulk_ops.bulk_get_emails(id_list, mailbox)

            emails_list: list[dict[str, Any]] = []
            for eid in id_list:
                if eid in emails_dict:
                    emails_list.append(emails_dict[eid])
                else:
                    emails_list.append({"id": eid, "error": "Email not found or could not be retrieved"})

            return json.dumps(emails_list, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to bulk retrieve emails: {e}"})

    @mcp.tool()
    def move_email_to_folder(email_id: str, target_folder: str, source_folder: str = "INBOX") -> str:
        """Move a specific email to a different folder.

        Args:
            email_id: The ID of the email to move
            target_folder: Target folder name (e.g., "Spam", "Trash", "Archive")
            source_folder: Source folder name (default: INBOX)

        Returns:
            Status of the move operation
        """
        try:
            email_id = validate_email_id(email_id)
            target_folder = validate_folder_name(target_folder)
            source_folder = validate_folder_name(source_folder)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        try:
            result = bulk_ops.bulk_move_emails([email_id], target_folder, source_folder)
            if result.get("success"):
                return json.dumps(
                    {
                        "status": "success",
                        "message": f"Email {email_id} moved from {source_folder} to {target_folder}",
                    }
                )
            return json.dumps(
                {
                    "status": "error",
                    "message": f"Failed to move email {email_id}",
                    "error": result.get("error"),
                }
            )
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error moving email: {e}"})
