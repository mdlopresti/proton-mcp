"""Tests for BulkOperations service."""

from unittest.mock import MagicMock, call, patch

import pytest

from proton_mcp.services.bulk import BulkOperations


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_raw_email(
    subject="Test Subject",
    from_addr="sender@example.com",
    to_addr="recipient@example.com",
    date="Mon, 01 Jan 2024 12:00:00 +0000",
    body="Hello, world!",
):
    """Build a minimal RFC822 email as bytes."""
    return (
        f"Subject: {subject}\r\n"
        f"From: {from_addr}\r\n"
        f"To: {to_addr}\r\n"
        f"Date: {date}\r\n"
        f"Content-Type: text/plain; charset=utf-8\r\n"
        f"\r\n"
        f"{body}"
    ).encode()


def _make_email_dict(uid, subject="Test Subject", from_addr="sender@example.com",
                     to_addr="recipient@example.com", date="Mon, 01 Jan 2024 12:00:00 +0000",
                     body="Hello, world!"):
    """Build a parsed email dict as returned by IMAPClient."""
    return {
        "id": uid,
        "subject": subject,
        "from": from_addr,
        "to": to_addr,
        "date": date,
        "body": body,
    }


def _mock_imap_client():
    """Create a mock IMAPClient that works as a context manager."""
    mock_imap = MagicMock()
    mock_imap.__enter__ = MagicMock(return_value=mock_imap)
    mock_imap.__exit__ = MagicMock(return_value=False)
    # Sensible defaults
    mock_imap.search.return_value = []
    mock_imap.copy.return_value = True
    mock_imap.store_flags.return_value = True
    mock_imap.expunge.return_value = True
    mock_imap.fetch_batch.return_value = {}
    return mock_imap


# ===========================================================================
# BulkOperations.__init__ tests
# ===========================================================================


class TestBulkOperationsInit:
    """Test BulkOperations initialization."""

    def test_init_stores_config(self, mock_config):
        bulk = BulkOperations(mock_config)
        assert bulk._config is mock_config


# ===========================================================================
# bulk_move_emails tests
# ===========================================================================


class TestBulkMoveEmails:
    """Test bulk_move_emails method."""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_successful_move(self, mock_imap_cls, mock_config):
        """Successful move: copy + delete flags + expunge all called."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1", "2", "3"]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails(["1", "2", "3"], "Archive")

        assert result["moved"] == 3
        assert result["target"] == "Archive"
        assert result["success"] is True
        mock_imap.copy.assert_called_once_with(["1", "2", "3"], "Archive")
        mock_imap.store_flags.assert_called_once_with(["1", "2", "3"], "\\Deleted")
        mock_imap.expunge.assert_called_once()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_deferred_expunge_called_once(self, mock_imap_cls, mock_config):
        """Expunge should be called exactly once, not per email."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["10", "20", "30", "40", "50"]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails(["10", "20", "30", "40", "50"], "Spam")

        assert result["success"] is True
        assert mock_imap.expunge.call_count == 1

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_empty_uid_list_returns_success(self, mock_imap_cls, mock_config):
        """Empty UID list should return success with moved=0, no IMAP calls."""
        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails([], "Archive")

        assert result["moved"] == 0
        assert result["target"] == "Archive"
        assert result["success"] is True
        mock_imap_cls.assert_not_called()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_copy_failure_returns_error(self, mock_imap_cls, mock_config):
        """When copy fails, return error without proceeding to delete/expunge."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]
        mock_imap.copy.return_value = False

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails(["1"], "Archive")

        assert result["moved"] == 0
        assert result["success"] is False
        assert "error" in result
        # Should not have tried to delete or expunge
        mock_imap.store_flags.assert_not_called()
        mock_imap.expunge.assert_not_called()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_store_flags_failure_returns_error(self, mock_imap_cls, mock_config):
        """When store_flags fails, return error."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]
        mock_imap.copy.return_value = True
        mock_imap.store_flags.return_value = False

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails(["1"], "Archive")

        assert result["moved"] == 0
        assert result["success"] is False
        assert "error" in result

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_correct_source_mailbox_used(self, mock_imap_cls, mock_config):
        """Source mailbox should be passed to search (for select)."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]

        bulk = BulkOperations(mock_config)
        bulk.bulk_move_emails(["1"], "Archive", source_mailbox="Sent")

        mock_imap.search.assert_called_once_with("ALL", "Sent")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_correct_target_mailbox_used(self, mock_imap_cls, mock_config):
        """Target mailbox should be passed to copy."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]

        bulk = BulkOperations(mock_config)
        bulk.bulk_move_emails(["1"], "CustomFolder")

        mock_imap.copy.assert_called_once_with(["1"], "CustomFolder")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_connection_exception_returns_error(self, mock_imap_cls, mock_config):
        """If IMAPClient raises an exception, return error dict."""
        mock_imap_cls.return_value.__enter__ = MagicMock(
            side_effect=OSError("Connection refused")
        )

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_move_emails(["1"], "Archive")

        assert result["moved"] == 0
        assert result["success"] is False
        assert "error" in result

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_default_source_mailbox_is_inbox(self, mock_imap_cls, mock_config):
        """Default source mailbox should be INBOX."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]

        bulk = BulkOperations(mock_config)
        bulk.bulk_move_emails(["1"], "Trash")

        mock_imap.search.assert_called_once_with("ALL", "INBOX")


# ===========================================================================
# bulk_mark_emails tests
# ===========================================================================


class TestBulkMarkEmails:
    """Test bulk_mark_emails method."""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_mark_as_read_adds_seen_flag(self, mock_imap_cls, mock_config):
        """Mark as read should add \\Seen flag."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails(["1", "2"], "\\Seen", add=True)

        assert result["marked"] == 2
        assert result["flag"] == "\\Seen"
        assert result["action"] == "added"
        assert result["success"] is True
        mock_imap.store_flags.assert_called_once_with(["1", "2"], "\\Seen", "+FLAGS")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_mark_as_unread_removes_seen_flag(self, mock_imap_cls, mock_config):
        """Mark as unread should remove \\Seen flag."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails(["1"], "\\Seen", add=False)

        assert result["marked"] == 1
        assert result["flag"] == "\\Seen"
        assert result["action"] == "removed"
        assert result["success"] is True
        mock_imap.store_flags.assert_called_once_with(["1"], "\\Seen", "-FLAGS")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_mark_as_important_adds_flagged(self, mock_imap_cls, mock_config):
        """Mark as important should add \\Flagged flag."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails(["5", "10", "15"], "\\Flagged", add=True)

        assert result["marked"] == 3
        assert result["flag"] == "\\Flagged"
        assert result["action"] == "added"
        assert result["success"] is True
        mock_imap.store_flags.assert_called_once_with(
            ["5", "10", "15"], "\\Flagged", "+FLAGS"
        )

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_flag_operation_failure(self, mock_imap_cls, mock_config):
        """When store_flags fails, return error."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.store_flags.return_value = False

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails(["1"], "\\Seen")

        assert result["marked"] == 0
        assert result["success"] is False
        assert "error" in result

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_empty_uid_list_returns_success(self, mock_imap_cls, mock_config):
        """Empty UID list should return success with marked=0."""
        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails([], "\\Seen")

        assert result["marked"] == 0
        assert result["success"] is True
        mock_imap_cls.assert_not_called()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_selects_correct_mailbox(self, mock_imap_cls, mock_config):
        """Should search in the specified mailbox to select it."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        bulk = BulkOperations(mock_config)
        bulk.bulk_mark_emails(["1"], "\\Seen", mailbox="Sent")

        mock_imap.search.assert_called_once_with("ALL", "Sent")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_connection_exception_returns_error(self, mock_imap_cls, mock_config):
        """If IMAPClient raises, return error dict."""
        mock_imap_cls.return_value.__enter__ = MagicMock(
            side_effect=OSError("Connection refused")
        )

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_mark_emails(["1"], "\\Seen")

        assert result["marked"] == 0
        assert result["success"] is False
        assert "error" in result


# ===========================================================================
# bulk_delete_emails tests
# ===========================================================================


class TestBulkDeleteEmails:
    """Test bulk_delete_emails method."""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_non_permanent_moves_to_trash(self, mock_imap_cls, mock_config):
        """Non-permanent delete should delegate to bulk_move_emails with Trash."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1", "2"]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_delete_emails(["1", "2"], permanent=False)

        assert result["deleted"] == 2
        assert result["permanent"] is False
        assert result["success"] is True
        # Should have called copy to Trash
        mock_imap.copy.assert_called_once_with(["1", "2"], "Trash")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_permanent_delete_marks_deleted_and_expunges(self, mock_imap_cls, mock_config):
        """Permanent delete should set \\Deleted flag and expunge."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_delete_emails(["1", "2", "3"], permanent=True)

        assert result["deleted"] == 3
        assert result["permanent"] is True
        assert result["success"] is True
        mock_imap.store_flags.assert_called_once_with(["1", "2", "3"], "\\Deleted")
        mock_imap.expunge.assert_called_once()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_empty_uid_list(self, mock_imap_cls, mock_config):
        """Empty UID list should return success with deleted=0."""
        bulk = BulkOperations(mock_config)

        result_non_perm = bulk.bulk_delete_emails([], permanent=False)
        assert result_non_perm["deleted"] == 0
        assert result_non_perm["success"] is True

        result_perm = bulk.bulk_delete_emails([], permanent=True)
        assert result_perm["deleted"] == 0
        assert result_perm["success"] is True

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_permanent_delete_store_flags_failure(self, mock_imap_cls, mock_config):
        """If store_flags fails during permanent delete, return error."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.store_flags.return_value = False

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_delete_emails(["1"], permanent=True)

        assert result["deleted"] == 0
        assert result["permanent"] is True
        assert result["success"] is False

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_non_permanent_uses_correct_source_mailbox(self, mock_imap_cls, mock_config):
        """Non-permanent delete should pass source mailbox through to move."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.search.return_value = ["1"]

        bulk = BulkOperations(mock_config)
        bulk.bulk_delete_emails(["1"], mailbox="Sent", permanent=False)

        # The move should use "Sent" as source
        mock_imap.search.assert_called_once_with("ALL", "Sent")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_permanent_connection_exception(self, mock_imap_cls, mock_config):
        """If connection fails during permanent delete, return error."""
        mock_imap_cls.return_value.__enter__ = MagicMock(
            side_effect=OSError("Connection refused")
        )

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_delete_emails(["1"], permanent=True)

        assert result["deleted"] == 0
        assert result["success"] is False
        assert "error" in result


# ===========================================================================
# bulk_get_emails tests
# ===========================================================================


class TestBulkGetEmails:
    """Test bulk_get_emails method."""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_single_batch_within_batch_size(self, mock_imap_cls, mock_config):
        """When UIDs fit in one batch, fetch_batch is called once."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {
            "1": _make_email_dict("1", subject="Email One"),
            "2": _make_email_dict("2", subject="Email Two"),
        }

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails(["1", "2"], batch_size=50)

        assert len(result) == 2
        assert result["1"]["subject"] == "Email One"
        assert result["2"]["subject"] == "Email Two"
        mock_imap.fetch_batch.assert_called_once_with(["1", "2"], "INBOX")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_multiple_batches(self, mock_imap_cls, mock_config):
        """When UIDs exceed batch_size, multiple fetch_batch calls are made."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        batch1 = {"1": _make_email_dict("1"), "2": _make_email_dict("2")}
        batch2 = {"3": _make_email_dict("3")}
        mock_imap.fetch_batch.side_effect = [batch1, batch2]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails(["1", "2", "3"], batch_size=2)

        assert len(result) == 3
        assert "1" in result
        assert "2" in result
        assert "3" in result
        assert mock_imap.fetch_batch.call_count == 2
        mock_imap.fetch_batch.assert_any_call(["1", "2"], "INBOX")
        mock_imap.fetch_batch.assert_any_call(["3"], "INBOX")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_empty_uid_list(self, mock_imap_cls, mock_config):
        """Empty UID list should return empty dict, no IMAP calls."""
        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails([])

        assert result == {}
        mock_imap_cls.assert_not_called()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_correct_batch_size_used(self, mock_imap_cls, mock_config):
        """Batch size should control chunk boundaries."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {}

        uids = [str(i) for i in range(1, 8)]  # 7 UIDs

        bulk = BulkOperations(mock_config)
        bulk.bulk_get_emails(uids, batch_size=3)

        # 7 UIDs / 3 per batch = 3 calls (3, 3, 1)
        assert mock_imap.fetch_batch.call_count == 3
        calls = mock_imap.fetch_batch.call_args_list
        assert calls[0] == call(["1", "2", "3"], "INBOX")
        assert calls[1] == call(["4", "5", "6"], "INBOX")
        assert calls[2] == call(["7"], "INBOX")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_uses_correct_mailbox(self, mock_imap_cls, mock_config):
        """Should pass mailbox parameter to fetch_batch."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {"1": _make_email_dict("1")}

        bulk = BulkOperations(mock_config)
        bulk.bulk_get_emails(["1"], mailbox="Sent")

        mock_imap.fetch_batch.assert_called_once_with(["1"], "Sent")

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_connection_exception_returns_partial(self, mock_imap_cls, mock_config):
        """If connection fails, return whatever was fetched so far (empty)."""
        mock_imap_cls.return_value.__enter__ = MagicMock(
            side_effect=OSError("Connection refused")
        )

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails(["1", "2"])

        assert result == {}

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_merges_results_from_multiple_batches(self, mock_imap_cls, mock_config):
        """Results from multiple batches should be merged into one dict."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        batch1 = {
            "10": _make_email_dict("10", subject="First"),
            "20": _make_email_dict("20", subject="Second"),
        }
        batch2 = {
            "30": _make_email_dict("30", subject="Third"),
        }
        mock_imap.fetch_batch.side_effect = [batch1, batch2]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails(["10", "20", "30"], batch_size=2)

        assert len(result) == 3
        assert result["10"]["subject"] == "First"
        assert result["20"]["subject"] == "Second"
        assert result["30"]["subject"] == "Third"


# ===========================================================================
# bulk_get_emails_with_html tests
# ===========================================================================


class TestBulkGetEmailsWithHtml:
    """Test bulk_get_emails_with_html method."""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_returns_dicts_with_html_fields(self, mock_imap_cls, mock_config):
        """Each email dict should include html-related fields."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {
            "1": _make_email_dict("1", subject="Newsletter", body="Plain text body"),
        }

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails_with_html(["1"])

        assert "1" in result
        email = result["1"]
        assert email["id"] == "1"
        assert email["subject"] == "Newsletter"
        assert email["text_body"] == "Plain text body"
        assert "html_body" in email
        assert "list_unsubscribe" in email
        assert "list_unsubscribe_post" in email

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_batch_processing_with_html(self, mock_imap_cls, mock_config):
        """Should process UIDs in chunks using the specified batch_size."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap

        batch1 = {
            "1": _make_email_dict("1", body="Body 1"),
            "2": _make_email_dict("2", body="Body 2"),
        }
        batch2 = {
            "3": _make_email_dict("3", body="Body 3"),
        }
        mock_imap.fetch_batch.side_effect = [batch1, batch2]

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails_with_html(["1", "2", "3"], batch_size=2)

        assert len(result) == 3
        assert mock_imap.fetch_batch.call_count == 2
        assert result["1"]["text_body"] == "Body 1"
        assert result["3"]["text_body"] == "Body 3"

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_empty_uid_list_returns_empty(self, mock_imap_cls, mock_config):
        """Empty UID list should return empty dict."""
        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails_with_html([])

        assert result == {}
        mock_imap_cls.assert_not_called()

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_default_batch_size_is_30(self, mock_imap_cls, mock_config):
        """Default batch size should be 30 (smaller than plain text)."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {}

        # Create 35 UIDs to test that batch_size=30 triggers 2 batches
        uids = [str(i) for i in range(1, 36)]

        bulk = BulkOperations(mock_config)
        bulk.bulk_get_emails_with_html(uids)

        assert mock_imap.fetch_batch.call_count == 2
        first_call_uids = mock_imap.fetch_batch.call_args_list[0][0][0]
        second_call_uids = mock_imap.fetch_batch.call_args_list[1][0][0]
        assert len(first_call_uids) == 30
        assert len(second_call_uids) == 5

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_html_fields_have_correct_defaults(self, mock_imap_cls, mock_config):
        """HTML-related fields should have sensible defaults."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {
            "42": _make_email_dict("42", body="The body text"),
        }

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails_with_html(["42"])

        email = result["42"]
        # text_body should come from the 'body' field
        assert email["text_body"] == "The body text"
        # html fields are placeholders until Phase 4
        assert email["html_body"] == ""
        assert email["list_unsubscribe"] == ""
        assert email["list_unsubscribe_post"] == ""

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_connection_exception_returns_empty(self, mock_imap_cls, mock_config):
        """If connection fails, return empty dict."""
        mock_imap_cls.return_value.__enter__ = MagicMock(
            side_effect=OSError("Connection refused")
        )

        bulk = BulkOperations(mock_config)
        result = bulk.bulk_get_emails_with_html(["1"])

        assert result == {}

    @patch("proton_mcp.services.bulk.IMAPClient")
    def test_uses_correct_mailbox(self, mock_imap_cls, mock_config):
        """Should pass mailbox parameter to fetch_batch."""
        mock_imap = _mock_imap_client()
        mock_imap_cls.return_value = mock_imap
        mock_imap.fetch_batch.return_value = {"1": _make_email_dict("1")}

        bulk = BulkOperations(mock_config)
        bulk.bulk_get_emails_with_html(["1"], mailbox="Archive")

        mock_imap.fetch_batch.assert_called_once_with(["1"], "Archive")
