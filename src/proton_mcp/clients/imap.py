"""IMAP client with UID-based operations."""

from __future__ import annotations

from typing import Any

from proton_mcp.config import Config


class IMAPClient:
    """IMAP client using UIDs for all operations. Supports context manager."""

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def __enter__(self) -> IMAPClient:
        raise NotImplementedError

    def __exit__(self, *args: Any) -> None:
        raise NotImplementedError

    def search(self, query: str, mailbox: str = "INBOX") -> list[str]:
        """Search for emails, returns list of UIDs."""
        raise NotImplementedError

    def fetch_one(self, uid: str, mailbox: str = "INBOX") -> dict[str, Any] | None:
        """Fetch a single email by UID."""
        raise NotImplementedError

    def fetch_batch(self, uids: list[str], mailbox: str = "INBOX") -> dict[str, dict[str, Any]]:
        """Fetch multiple emails by UIDs."""
        raise NotImplementedError

    def copy(self, uids: list[str], target_mailbox: str) -> bool:
        """Copy emails to target mailbox."""
        raise NotImplementedError

    def store_flags(self, uids: list[str], flags: str, action: str = "+FLAGS") -> bool:
        """Set/remove flags on emails."""
        raise NotImplementedError

    def expunge(self) -> bool:
        """Expunge deleted messages."""
        raise NotImplementedError

    def list_mailboxes(self) -> list[str]:
        """List available mailboxes."""
        raise NotImplementedError

    def create_mailbox(self, name: str) -> bool:
        """Create a new mailbox."""
        raise NotImplementedError

    def delete_mailbox(self, name: str) -> bool:
        """Delete a mailbox."""
        raise NotImplementedError
