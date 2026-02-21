"""Bulk email operations service."""

from __future__ import annotations

from typing import Any

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.config import Config
from proton_mcp.models.email import EmailSummary, EmailWithHtml


class BulkOperations:
    """Bulk email operations for efficient batch processing.

    All operations use UID-based IMAPClient with deferred expunge pattern.
    Supports chunked processing for large volumes.
    """

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def bulk_move_emails(
        self,
        uids: list[str],
        target_mailbox: str,
        source_mailbox: str = "INBOX",
    ) -> dict[str, Any]:
        """Move multiple emails to target folder. Single expunge at end."""
        raise NotImplementedError

    def bulk_mark_emails(
        self,
        uids: list[str],
        flag: str,
        mailbox: str = "INBOX",
        add: bool = True,
    ) -> dict[str, Any]:
        """Set or remove a flag on multiple emails."""
        raise NotImplementedError

    def bulk_delete_emails(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        permanent: bool = False,
    ) -> dict[str, Any]:
        """Delete multiple emails (move to Trash or permanent delete)."""
        raise NotImplementedError

    def bulk_get_emails(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        batch_size: int = 50,
    ) -> dict[str, dict[str, Any]]:
        """Efficiently retrieve multiple emails in batches."""
        raise NotImplementedError

    def bulk_get_emails_with_html(
        self,
        uids: list[str],
        mailbox: str = "INBOX",
        batch_size: int = 30,
    ) -> dict[str, dict[str, Any]]:
        """Retrieve multiple emails with HTML content in batches."""
        raise NotImplementedError
