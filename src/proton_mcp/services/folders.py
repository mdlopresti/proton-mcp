"""Folder management service."""

from __future__ import annotations

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.config import Config


class FolderService:
    """Email folder CRUD operations via IMAPClient."""

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def list_folders(self) -> list[str]:
        """List all available mailboxes/folders."""
        raise NotImplementedError

    def create_folder(self, name: str) -> bool:
        """Create a new folder. Returns True on success."""
        raise NotImplementedError

    def delete_folder(self, name: str) -> bool:
        """Delete a folder. Returns True on success."""
        raise NotImplementedError

    def move_email(self, uid: str, target_folder: str, source_folder: str = "INBOX") -> bool:
        """Move a single email to target folder (copy + delete + expunge)."""
        raise NotImplementedError
