"""Bulk email operations service."""

from __future__ import annotations

import logging
from typing import Any

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.config import Config

logger = logging.getLogger(__name__)


class BulkOperations:
    """Bulk email operations for efficient batch processing.

    All operations use UID-based IMAPClient with deferred expunge pattern.
    Supports chunked processing for large volumes.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

    def bulk_move_emails(
        self,
        uids: list[str],
        target_mailbox: str,
        source_mailbox: str = "INBOX",
    ) -> dict[str, Any]:
        """Move multiple emails to target folder. Single expunge at end.

        Uses the deferred expunge pattern: COPY all, then mark \\Deleted,
        then a single EXPUNGE at the end for efficiency.

        Args:
            uids: List of email UIDs to move.
            target_mailbox: Destination mailbox.
            source_mailbox: Source mailbox (default INBOX).

        Returns:
            Dict with ``moved``, ``target``, ``success`` keys.
            On failure, includes ``error`` key.
        """
        if not uids:
            return {"moved": 0, "target": target_mailbox, "success": True}

        try:
            with IMAPClient(self._config) as imap:
                # Select source mailbox (search triggers mailbox SELECT)
                imap.search("ALL", source_mailbox)

                # Copy all emails to target
                if not imap.copy(uids, target_mailbox):
                    return {
                        "moved": 0,
                        "success": False,
                        "error": f"Failed to copy emails to {target_mailbox}",
                    }

                # Mark originals as deleted
                if not imap.store_flags(uids, "\\Deleted"):
                    return {
                        "moved": 0,
                        "success": False,
                        "error": "Failed to mark emails as deleted in source",
                    }

                # Single deferred expunge
                imap.expunge()

                return {
                    "moved": len(uids),
                    "target": target_mailbox,
                    "success": True,
                }
        except Exception as e:
            logger.error("bulk_move_emails failed: %s", e, exc_info=True)
            return {"moved": 0, "success": False, "error": str(e)}

    def bulk_mark_emails(
        self,
        uids: list[str],
        flag: str,
        mailbox: str = "INBOX",
        add: bool = True,
    ) -> dict[str, Any]:
        """Set or remove a flag on multiple emails.

        Args:
            uids: List of email UIDs to modify.
            flag: IMAP flag (e.g. ``\\Seen``, ``\\Flagged``).
            mailbox: Mailbox containing the emails.
            add: If True, add the flag; if False, remove it.

        Returns:
            Dict with ``marked``, ``flag``, ``action``, ``success`` keys.
        """
        if not uids:
            return {
                "marked": 0,
                "flag": flag,
                "action": "added" if add else "removed",
                "success": True,
            }

        action = "+FLAGS" if add else "-FLAGS"

        try:
            with IMAPClient(self._config) as imap:
                # Select the mailbox (via search) so IMAP is ready
                imap.search("ALL", mailbox)

                if not imap.store_flags(uids, flag, action):
                    return {
                        "marked": 0,
                        "flag": flag,
                        "action": "added" if add else "removed",
                        "success": False,
                        "error": f"Failed to {action} {flag}",
                    }

                return {
                    "marked": len(uids),
                    "flag": flag,
                    "action": "added" if add else "removed",
                    "success": True,
                }
        except Exception as e:
            logger.error("bulk_mark_emails failed: %s", e, exc_info=True)
            return {
                "marked": 0,
                "flag": flag,
                "action": "added" if add else "removed",
                "success": False,
                "error": str(e),
            }

    def bulk_delete_emails(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        permanent: bool = False,
    ) -> dict[str, Any]:
        """Delete multiple emails (move to Trash or permanent delete).

        Args:
            uids: List of email UIDs to delete.
            mailbox: Mailbox containing the emails.
            permanent: If True, permanently delete (\\Deleted + expunge).
                       If False, move to Trash.

        Returns:
            Dict with ``deleted``, ``permanent``, ``success`` keys.
        """
        if not uids:
            return {"deleted": 0, "permanent": permanent, "success": True}

        if not permanent:
            # Move to Trash folder
            result = self.bulk_move_emails(uids, "Trash", mailbox)
            return {
                "deleted": result.get("moved", 0),
                "permanent": False,
                "success": result.get("success", False),
                "error": result.get("error"),
            }

        # Permanent deletion: mark \\Deleted + expunge
        try:
            with IMAPClient(self._config) as imap:
                # Select mailbox
                imap.search("ALL", mailbox)

                # Mark as deleted
                if not imap.store_flags(uids, "\\Deleted"):
                    return {
                        "deleted": 0,
                        "permanent": True,
                        "success": False,
                        "error": "Failed to mark emails as deleted",
                    }

                # Expunge permanently
                imap.expunge()

                return {
                    "deleted": len(uids),
                    "permanent": True,
                    "success": True,
                }
        except Exception as e:
            logger.error("bulk_delete_emails failed: %s", e, exc_info=True)
            return {
                "deleted": 0,
                "permanent": True,
                "success": False,
                "error": str(e),
            }

    def bulk_get_emails(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        batch_size: int = 50,
    ) -> dict[str, dict[str, Any]]:
        """Efficiently retrieve multiple emails in batches.

        Processes UIDs in chunks of ``batch_size`` to manage memory and
        IMAP connection limits.

        Args:
            uids: List of email UIDs to retrieve.
            mailbox: Mailbox to fetch from.
            batch_size: Number of emails per IMAP fetch call.

        Returns:
            Dict mapping UID to email dict (``{id, subject, from, to, date, body}``).
        """
        if not uids:
            return {}

        all_emails: dict[str, dict[str, Any]] = {}

        try:
            with IMAPClient(self._config) as imap:
                for i in range(0, len(uids), batch_size):
                    chunk = uids[i : i + batch_size]
                    batch_result = imap.fetch_batch(chunk, mailbox)
                    all_emails.update(batch_result)
        except Exception as e:
            logger.error("bulk_get_emails failed: %s", e, exc_info=True)

        return all_emails

    def bulk_get_emails_with_html(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        batch_size: int = 30,
    ) -> dict[str, dict[str, Any]]:
        """Retrieve multiple emails with HTML content in batches.

        Uses ``fetch_batch()`` for basic fields and adds HTML-related
        placeholder fields. The actual HTML extraction is wired at a
        higher level (Phase 4+).

        Args:
            uids: List of email UIDs to retrieve.
            mailbox: Mailbox to fetch from.
            batch_size: Number of emails per batch (smaller than plain
                text due to larger HTML payloads).

        Returns:
            Dict mapping UID to email dict with extra fields:
            ``text_body``, ``html_body``, ``list_unsubscribe``,
            ``list_unsubscribe_post``.
        """
        if not uids:
            return {}

        all_emails: dict[str, dict[str, Any]] = {}

        try:
            with IMAPClient(self._config) as imap:
                for i in range(0, len(uids), batch_size):
                    chunk = uids[i : i + batch_size]
                    batch_result = imap.fetch_batch(chunk, mailbox)

                    # Augment each result with HTML-related fields
                    for uid, email_data in batch_result.items():
                        all_emails[uid] = {
                            "id": email_data.get("id", uid),
                            "subject": email_data.get("subject", ""),
                            "from": email_data.get("from", ""),
                            "to": email_data.get("to", ""),
                            "date": email_data.get("date", ""),
                            "text_body": email_data.get("body", ""),
                            "html_body": "",
                            "list_unsubscribe": "",
                            "list_unsubscribe_post": "",
                        }
        except Exception as e:
            logger.error("bulk_get_emails_with_html failed: %s", e, exc_info=True)

        return all_emails
