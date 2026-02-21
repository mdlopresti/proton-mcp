"""Folder management service."""

from __future__ import annotations

import logging

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.config import Config
from proton_mcp.utils.validation import validate_email_id, validate_folder_name

logger = logging.getLogger(__name__)


class FolderService:
    """Email folder CRUD operations via IMAPClient."""

    def __init__(self, config: Config) -> None:
        self._config = config

    def list_folders(self) -> list[str]:
        """List all available mailboxes/folders."""
        with IMAPClient(self._config) as imap:
            return imap.list_mailboxes()

    def create_folder(self, name: str) -> bool:
        """Create a new folder. Returns True on success.

        Args:
            name: The folder name to create. Must pass validation.

        Returns:
            True if the folder was created successfully, False otherwise.

        Raises:
            ValueError: If the folder name is invalid.
        """
        name = validate_folder_name(name)
        with IMAPClient(self._config) as imap:
            return imap.create_mailbox(name)

    def delete_folder(self, name: str) -> bool:
        """Delete a folder. Returns True on success.

        Args:
            name: The folder name to delete. Must pass validation.

        Returns:
            True if the folder was deleted successfully, False otherwise.

        Raises:
            ValueError: If the folder name is invalid.
        """
        name = validate_folder_name(name)
        with IMAPClient(self._config) as imap:
            return imap.delete_mailbox(name)

    def move_email(self, uid: str, target_folder: str, source_folder: str = "INBOX") -> bool:
        """Move a single email to target folder (copy + delete + expunge).

        Performs an IMAP COPY to the target folder, marks the original as
        deleted, and expunges the source mailbox.

        Args:
            uid: The email UID to move. Must be a valid numeric ID.
            target_folder: Destination folder name.
            source_folder: Source folder name (default: "INBOX").

        Returns:
            True if the email was moved successfully, False otherwise.

        Raises:
            ValueError: If the uid or target_folder is invalid.
        """
        uid = validate_email_id(uid)
        target_folder = validate_folder_name(target_folder)

        with IMAPClient(self._config) as imap:
            # Select the source folder by searching — this also selects
            # the mailbox so that subsequent UID commands operate on it.
            imap.search("ALL", source_folder)

            # Copy to target
            if not imap.copy([uid], target_folder):
                logger.error("Failed to copy UID %s to '%s'", uid, target_folder)
                return False

            # Mark deleted in source
            if not imap.store_flags([uid], "\\Deleted"):
                logger.warning(
                    "Copied UID %s to '%s' but failed to mark deleted in '%s'",
                    uid, target_folder, source_folder,
                )
                return False

            # Expunge
            if not imap.expunge():
                logger.warning(
                    "Copied UID %s to '%s' and marked deleted, but expunge failed",
                    uid, target_folder,
                )
                return False

            return True
