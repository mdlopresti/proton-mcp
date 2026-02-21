"""Tests for FolderService -- folder CRUD and email move operations."""

from __future__ import annotations

from unittest.mock import MagicMock, call, patch

import pytest

from proton_mcp.services.folders import FolderService


# ===========================================================================
# __init__ tests
# ===========================================================================


class TestFolderServiceInit:
    """Test FolderService construction."""

    def test_stores_config(self, mock_config):
        service = FolderService(mock_config)
        assert service._config is mock_config


# ===========================================================================
# list_folders tests
# ===========================================================================


class TestListFolders:
    """Test FolderService.list_folders."""

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_returns_folder_list(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.list_mailboxes.return_value = ["INBOX", "Sent", "Drafts", "Trash"]

        service = FolderService(mock_config)
        result = service.list_folders()

        assert result == ["INBOX", "Sent", "Drafts", "Trash"]
        mock_imap.list_mailboxes.assert_called_once()

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_returns_empty_list(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.list_mailboxes.return_value = []

        service = FolderService(mock_config)
        result = service.list_folders()

        assert result == []

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_uses_imap_as_context_manager(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.list_mailboxes.return_value = ["INBOX"]

        service = FolderService(mock_config)
        service.list_folders()

        # Verify context manager was used
        mock_imap_cls.return_value.__enter__.assert_called_once()
        mock_imap_cls.return_value.__exit__.assert_called_once()

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_passes_config_to_imap_client(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.list_mailboxes.return_value = []

        service = FolderService(mock_config)
        service.list_folders()

        mock_imap_cls.assert_called_once_with(mock_config)


# ===========================================================================
# create_folder tests
# ===========================================================================


class TestCreateFolder:
    """Test FolderService.create_folder."""

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_success(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.create_mailbox.return_value = True

        service = FolderService(mock_config)
        result = service.create_folder("MyFolder")

        assert result is True
        mock_imap.create_mailbox.assert_called_once_with("MyFolder")

    def test_invalid_folder_name_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Invalid folder name"):
            service.create_folder("folder<>with|bad|chars")

    def test_empty_folder_name_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            service.create_folder("")

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_imap_failure_returns_false(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.create_mailbox.return_value = False

        service = FolderService(mock_config)
        result = service.create_folder("NewFolder")

        assert result is False

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_folder_name_is_validated_and_stripped(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.create_mailbox.return_value = True

        service = FolderService(mock_config)
        service.create_folder("  MyFolder  ")

        # validate_folder_name strips whitespace
        mock_imap.create_mailbox.assert_called_once_with("MyFolder")

    def test_path_traversal_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Directory traversal"):
            service.create_folder("../etc/passwd")


# ===========================================================================
# delete_folder tests
# ===========================================================================


class TestDeleteFolder:
    """Test FolderService.delete_folder."""

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_success(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.delete_mailbox.return_value = True

        service = FolderService(mock_config)
        result = service.delete_folder("OldFolder")

        assert result is True
        mock_imap.delete_mailbox.assert_called_once_with("OldFolder")

    def test_invalid_name_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Invalid folder name"):
            service.delete_folder("bad!name@here")

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_failure_returns_false(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.delete_mailbox.return_value = False

        service = FolderService(mock_config)
        result = service.delete_folder("NonExistent")

        assert result is False

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_folder_name_stripped_before_delete(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.delete_mailbox.return_value = True

        service = FolderService(mock_config)
        service.delete_folder("  Trash  ")

        mock_imap.delete_mailbox.assert_called_once_with("Trash")


# ===========================================================================
# move_email tests
# ===========================================================================


class TestMoveEmail:
    """Test FolderService.move_email."""

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_success_copy_delete_expunge(self, mock_imap_cls, mock_config):
        """Successful move calls copy, store_flags(Deleted), and expunge."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["42"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = True
        mock_imap.expunge.return_value = True

        service = FolderService(mock_config)
        result = service.move_email("42", "Archive")

        assert result is True
        mock_imap.search.assert_called_once_with("ALL", "INBOX")
        mock_imap.copy.assert_called_once_with(["42"], "Archive")
        mock_imap.store_flags.assert_called_once_with(["42"], "\\Deleted")
        mock_imap.expunge.assert_called_once()

    def test_invalid_email_id_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Invalid email ID"):
            service.move_email("not-a-number", "Archive")

    def test_invalid_target_folder_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Invalid folder name"):
            service.move_email("42", "bad<folder>name")

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_copy_failure_returns_false(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["42"]
        mock_imap.copy.return_value = False

        service = FolderService(mock_config)
        result = service.move_email("42", "Archive")

        assert result is False
        # store_flags and expunge should not be called if copy fails
        mock_imap.store_flags.assert_not_called()
        mock_imap.expunge.assert_not_called()

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_correct_source_folder_used(self, mock_imap_cls, mock_config):
        """When source_folder is specified, it's used to select the mailbox."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["10"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = True
        mock_imap.expunge.return_value = True

        service = FolderService(mock_config)
        result = service.move_email("10", "Trash", source_folder="Sent")

        assert result is True
        mock_imap.search.assert_called_once_with("ALL", "Sent")

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_store_flags_failure_returns_false(self, mock_imap_cls, mock_config):
        """If marking as deleted fails, move returns False."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["42"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = False

        service = FolderService(mock_config)
        result = service.move_email("42", "Archive")

        assert result is False
        mock_imap.expunge.assert_not_called()

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_expunge_failure_returns_false(self, mock_imap_cls, mock_config):
        """If expunge fails, move returns False."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["42"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = True
        mock_imap.expunge.return_value = False

        service = FolderService(mock_config)
        result = service.move_email("42", "Archive")

        assert result is False

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_email_id_stripped(self, mock_imap_cls, mock_config):
        """validate_email_id strips whitespace from UID."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["99"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = True
        mock_imap.expunge.return_value = True

        service = FolderService(mock_config)
        result = service.move_email("  99  ", "Archive")

        assert result is True
        mock_imap.copy.assert_called_once_with(["99"], "Archive")

    def test_empty_target_folder_raises_value_error(self, mock_config):
        service = FolderService(mock_config)

        with pytest.raises(ValueError, match="Folder name cannot be empty"):
            service.move_email("42", "")

    @patch("proton_mcp.services.folders.IMAPClient")
    def test_default_source_folder_is_inbox(self, mock_imap_cls, mock_config):
        """When no source_folder argument is passed, INBOX is used."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_imap.search.return_value = ["1"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = True
        mock_imap.expunge.return_value = True

        service = FolderService(mock_config)
        service.move_email("1", "Spam")

        mock_imap.search.assert_called_once_with("ALL", "INBOX")
