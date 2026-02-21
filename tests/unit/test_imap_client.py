"""Tests for IMAPClient with UID-based operations."""

import imaplib
from unittest.mock import MagicMock, call, patch

import pytest

from proton_mcp.clients.imap import IMAPClient

# Capture the real IMAP4.error class before any patching takes place.
_IMAP4Error = imaplib.IMAP4.error


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


def _make_fetch_response(uid, raw_email):
    """Build an IMAP FETCH response tuple for a single UID."""
    header = f"1 (UID {uid} RFC822 {{{len(raw_email)}}})".encode()
    return [(header, raw_email), b")"]


def _make_batch_fetch_response(uid_email_pairs):
    """Build an IMAP FETCH response for multiple UIDs."""
    result = []
    for seq, (uid, raw_email) in enumerate(uid_email_pairs, start=1):
        header = f"{seq} (UID {uid} RFC822 {{{len(raw_email)}}})".encode()
        result.append((header, raw_email))
        result.append(b")")
    return result


# ===========================================================================
# Context manager tests
# ===========================================================================


class TestIMAPClientContextManager:
    """Test connect / STARTTLS / login / close / logout lifecycle."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_enter_connects_with_starttls_and_login(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn

        client = IMAPClient(mock_config)
        result = client.__enter__()

        mock_imap4_cls.assert_called_once_with(mock_config.imap_host, mock_config.imap_port)
        mock_conn.starttls.assert_called_once()
        mock_conn.login.assert_called_once_with(mock_config.email, mock_config.password)
        assert result is client

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_exit_calls_close_and_logout(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn

        with IMAPClient(mock_config):
            pass

        mock_conn.close.assert_called_once()
        mock_conn.logout.assert_called_once()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_full_lifecycle(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn

        with IMAPClient(mock_config) as client:
            assert client._mail is mock_conn

        mock_imap4_cls.assert_called_once()
        mock_conn.starttls.assert_called_once()
        mock_conn.login.assert_called_once()
        mock_conn.close.assert_called_once()
        mock_conn.logout.assert_called_once()
        assert client._mail is None

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_connection_failure_raises(self, mock_imap4_cls, mock_config):
        mock_imap4_cls.side_effect = OSError("Connection refused")

        client = IMAPClient(mock_config)
        with pytest.raises(OSError, match="Connection refused"):
            client.__enter__()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_starttls_failure_raises(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.starttls.side_effect = _IMAP4Error("STARTTLS failed")

        client = IMAPClient(mock_config)
        with pytest.raises(_IMAP4Error):
            client.__enter__()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_login_failure_raises(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.login.side_effect = _IMAP4Error("LOGIN failed")

        client = IMAPClient(mock_config)
        with pytest.raises(_IMAP4Error):
            client.__enter__()

    def test_exit_handles_no_connection_gracefully(self, mock_config):
        """__exit__ should not raise if connection was never established."""
        client = IMAPClient(mock_config)
        client.__exit__(None, None, None)  # Should not raise

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_exit_handles_already_disconnected(self, mock_imap4_cls, mock_config):
        """__exit__ should handle IMAP4.abort/error on close gracefully."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.close.side_effect = imaplib.IMAP4.abort("Already closed")
        mock_conn.logout.side_effect = imaplib.IMAP4.abort("Already logged out")

        with IMAPClient(mock_config):
            pass
        # Should not raise

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_exit_handles_oserror_on_logout(self, mock_imap4_cls, mock_config):
        """__exit__ handles OSError on logout (connection dropped)."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.logout.side_effect = OSError("Connection reset")

        with IMAPClient(mock_config):
            pass
        # Should not raise

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_exit_handles_close_failure_with_oserror(self, mock_imap4_cls, mock_config):
        """__exit__ handles OSError on close() (no mailbox selected)."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.close.side_effect = OSError("No mailbox selected")

        with IMAPClient(mock_config):
            pass
        # Should not raise; logout should still be called
        mock_conn.logout.assert_called_once()


# ===========================================================================
# Search tests
# ===========================================================================


class TestIMAPClientSearch:
    """Test search() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_returns_uids(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.uid.return_value = ("OK", [b"101 102 103"])

        with IMAPClient(mock_config) as client:
            result = client.search("ALL")

        assert result == ["101", "102", "103"]
        mock_conn.uid.assert_called_once_with("search", None, "ALL")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_uses_uid_command(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.uid.return_value = ("OK", [b"42"])

        with IMAPClient(mock_config) as client:
            client.search("FROM test@example.com")

        # Verify uid() was called, not search()
        mock_conn.uid.assert_called_with("search", None, "FROM test@example.com")
        mock_conn.search.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_handles_empty_results(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"0"])
        mock_conn.uid.return_value = ("OK", [b""])

        with IMAPClient(mock_config) as client:
            result = client.search("ALL")

        assert result == []

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_handles_none_data(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"0"])
        mock_conn.uid.return_value = ("OK", [None])

        with IMAPClient(mock_config) as client:
            result = client.search("ALL")

        assert result == []

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_selects_correct_mailbox(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"0"])
        mock_conn.uid.return_value = ("OK", [b""])

        with IMAPClient(mock_config) as client:
            client.search("ALL", mailbox="Sent")

        mock_conn.select.assert_called_with("Sent")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_returns_empty_on_select_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("NO", [b"Mailbox not found"])

        with IMAPClient(mock_config) as client:
            result = client.search("ALL", mailbox="Nonexistent")

        assert result == []

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_search_returns_empty_on_search_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.uid.return_value = ("NO", [b"Search failed"])

        with IMAPClient(mock_config) as client:
            result = client.search("INVALID QUERY")

        assert result == []


# ===========================================================================
# fetch_one tests
# ===========================================================================


class TestIMAPClientFetchOne:
    """Test fetch_one() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_parses_email_correctly(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])

        raw = _make_raw_email(
            subject="Important Meeting",
            from_addr="boss@company.com",
            to_addr="me@proton.me",
            date="Tue, 02 Jan 2024 09:00:00 +0000",
            body="Don't forget the meeting at 3pm.",
        )
        mock_conn.uid.return_value = ("OK", _make_fetch_response("42", raw))

        with IMAPClient(mock_config) as client:
            result = client.fetch_one("42")

        assert result is not None
        assert result["id"] == "42"
        assert result["subject"] == "Important Meeting"
        assert result["from"] == "boss@company.com"
        assert result["to"] == "me@proton.me"
        assert result["date"] == "Tue, 02 Jan 2024 09:00:00 +0000"
        assert "meeting at 3pm" in result["body"]

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_uses_uid_command(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        raw = _make_raw_email()
        mock_conn.uid.return_value = ("OK", _make_fetch_response("99", raw))

        with IMAPClient(mock_config) as client:
            client.fetch_one("99")

        mock_conn.uid.assert_called_with("fetch", "99", "(RFC822)")
        mock_conn.fetch.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_returns_none_on_fetch_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.uid.return_value = ("NO", [b"Fetch failed"])

        with IMAPClient(mock_config) as client:
            result = client.fetch_one("999")

        assert result is None

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_returns_none_on_select_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("NO", [b"Mailbox not found"])

        with IMAPClient(mock_config) as client:
            result = client.fetch_one("42", mailbox="Nonexistent")

        assert result is None

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_returns_none_for_empty_data(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        mock_conn.uid.return_value = ("OK", [None])

        with IMAPClient(mock_config) as client:
            result = client.fetch_one("42")

        assert result is None

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_one_selects_correct_mailbox(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])
        raw = _make_raw_email()
        mock_conn.uid.return_value = ("OK", _make_fetch_response("10", raw))

        with IMAPClient(mock_config) as client:
            client.fetch_one("10", mailbox="Sent")

        mock_conn.select.assert_called_with("Sent")


# ===========================================================================
# fetch_batch tests
# ===========================================================================


class TestIMAPClientFetchBatch:
    """Test fetch_batch() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_returns_multiple_emails(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])

        raw1 = _make_raw_email(subject="Email One", from_addr="alice@example.com")
        raw2 = _make_raw_email(subject="Email Two", from_addr="bob@example.com")
        raw3 = _make_raw_email(subject="Email Three", from_addr="charlie@example.com")

        mock_conn.uid.return_value = (
            "OK",
            _make_batch_fetch_response([("101", raw1), ("102", raw2), ("103", raw3)]),
        )

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101", "102", "103"])

        assert len(result) == 3
        assert result["101"]["subject"] == "Email One"
        assert result["102"]["subject"] == "Email Two"
        assert result["103"]["subject"] == "Email Three"

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_uses_comma_separated_uids(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])
        mock_conn.uid.return_value = ("OK", [])

        with IMAPClient(mock_config) as client:
            client.fetch_batch(["10", "20", "30"])

        mock_conn.uid.assert_called_with("fetch", "10,20,30", "(RFC822)")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_returns_empty_dict_for_empty_input(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch([])

        assert result == {}
        # Should not even call select or uid
        mock_conn.select.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_handles_select_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("NO", [b"Mailbox not found"])

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101"], mailbox="Nonexistent")

        assert result == {}

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_falls_back_on_error(self, mock_imap4_cls, mock_config):
        """If batch fetch raises an exception, fall back to individual fetches."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])

        raw1 = _make_raw_email(subject="Fallback Email")

        # First uid() call (batch) raises, subsequent individual calls succeed
        mock_conn.uid.side_effect = [
            Exception("Batch too large"),
            ("OK", _make_fetch_response("101", raw1)),
        ]

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101"])

        assert len(result) == 1
        assert result["101"]["subject"] == "Fallback Email"

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_fallback_handles_individual_failure(self, mock_imap4_cls, mock_config):
        """When batch fails and fallback individual fetch also fails, skip that UID."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])

        # Batch fetch raises, then individual fetch returns NOT OK
        mock_conn.uid.side_effect = [
            Exception("Batch too large"),
            ("NO", [b"Not found"]),
        ]

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101"])

        assert result == {}

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_fallback_handles_individual_exception(self, mock_imap4_cls, mock_config):
        """When batch fails and fallback individual fetch raises, skip that UID."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])

        # Batch fetch raises, then individual fetch also raises
        mock_conn.uid.side_effect = [
            Exception("Batch too large"),
            Exception("Individual fetch failed too"),
        ]

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101"])

        assert result == {}

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_handles_partial_results(self, mock_imap4_cls, mock_config):
        """If some UIDs are missing from batch response, only return available ones."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])

        # Only UID 101 is returned even though we asked for 101, 102
        raw1 = _make_raw_email(subject="Only One")
        mock_conn.uid.return_value = (
            "OK",
            _make_batch_fetch_response([("101", raw1)]),
        )

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101", "102"])

        assert len(result) == 1
        assert "101" in result
        assert "102" not in result

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_returns_empty_on_fetch_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])
        mock_conn.uid.return_value = ("NO", [b"Fetch failed"])

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["101", "102"])

        assert result == {}


# ===========================================================================
# copy tests
# ===========================================================================


class TestIMAPClientCopy:
    """Test copy() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_copy_uses_uid_command(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.copy(["101", "102"], "Archive")

        assert result is True
        mock_conn.uid.assert_called_with("copy", "101,102", "Archive")
        mock_conn.copy.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_copy_single_uid(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.copy(["42"], "Trash")

        assert result is True
        mock_conn.uid.assert_called_with("copy", "42", "Trash")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_copy_returns_false_on_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("NO", [b"Copy failed"])

        with IMAPClient(mock_config) as client:
            result = client.copy(["101"], "Nonexistent")

        assert result is False

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_copy_logs_error_on_failure(self, mock_imap4_cls, mock_config, caplog):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("NO", [b"Copy failed"])

        import logging

        with caplog.at_level(logging.ERROR, logger="proton_mcp.clients.imap"):
            with IMAPClient(mock_config) as client:
                client.copy(["101"], "BadFolder")

        assert "Failed to copy" in caplog.text


# ===========================================================================
# store_flags tests
# ===========================================================================


class TestIMAPClientStoreFlags:
    """Test store_flags() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_add(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.store_flags(["101"], "\\Deleted", "+FLAGS")

        assert result is True
        mock_conn.uid.assert_called_with("store", "101", "+FLAGS", "\\Deleted")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_remove(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.store_flags(["101"], "\\Seen", "-FLAGS")

        assert result is True
        mock_conn.uid.assert_called_with("store", "101", "-FLAGS", "\\Seen")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_uses_uid_command(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            client.store_flags(["10", "20"], "\\Seen", "+FLAGS")

        mock_conn.uid.assert_called_with("store", "10,20", "+FLAGS", "\\Seen")
        mock_conn.store.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_default_action_is_add(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            client.store_flags(["101"], "\\Flagged")

        mock_conn.uid.assert_called_with("store", "101", "+FLAGS", "\\Flagged")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_returns_false_on_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("NO", [b"Store failed"])

        with IMAPClient(mock_config) as client:
            result = client.store_flags(["101"], "\\Deleted")

        assert result is False

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_store_flags_batch(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.uid.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.store_flags(["1", "2", "3", "4", "5"], "\\Seen")

        assert result is True
        mock_conn.uid.assert_called_with("store", "1,2,3,4,5", "+FLAGS", "\\Seen")


# ===========================================================================
# expunge tests
# ===========================================================================


class TestIMAPClientExpunge:
    """Test expunge() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_expunge_calls_expunge(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.expunge.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            result = client.expunge()

        assert result is True
        mock_conn.expunge.assert_called_once()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_expunge_returns_false_on_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.expunge.return_value = ("NO", [b"Expunge failed"])

        with IMAPClient(mock_config) as client:
            result = client.expunge()

        assert result is False


# ===========================================================================
# list_mailboxes tests
# ===========================================================================


class TestIMAPClientListMailboxes:
    """Test list_mailboxes() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_list_mailboxes_parses_response(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.list.return_value = (
            "OK",
            [
                b'(\\HasNoChildren) "/" "INBOX"',
                b'(\\HasNoChildren) "/" "Sent"',
                b'(\\HasNoChildren) "/" "Drafts"',
                b'(\\HasNoChildren) "/" "Trash"',
                b'(\\HasNoChildren) "/" "Archive"',
            ],
        )

        with IMAPClient(mock_config) as client:
            result = client.list_mailboxes()

        assert result == ["INBOX", "Sent", "Drafts", "Trash", "Archive"]

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_list_mailboxes_returns_empty_on_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.list.return_value = ("NO", [b"Failed"])

        with IMAPClient(mock_config) as client:
            result = client.list_mailboxes()

        assert result == []

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_list_mailboxes_returns_empty_on_none_data(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.list.return_value = ("OK", None)

        with IMAPClient(mock_config) as client:
            result = client.list_mailboxes()

        assert result == []

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_list_mailboxes_handles_nested_folders(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.list.return_value = (
            "OK",
            [
                b'(\\HasChildren) "/" "Folders"',
                b'(\\HasNoChildren) "/" "Folders/Work"',
                b'(\\HasNoChildren) "/" "Folders/Personal"',
            ],
        )

        with IMAPClient(mock_config) as client:
            result = client.list_mailboxes()

        assert "Folders" in result
        assert "Folders/Work" in result
        assert "Folders/Personal" in result


# ===========================================================================
# create_mailbox tests
# ===========================================================================


class TestIMAPClientCreateMailbox:
    """Test create_mailbox() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_create_mailbox_success(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.create.return_value = ("OK", [b"Created"])

        with IMAPClient(mock_config) as client:
            result = client.create_mailbox("NewFolder")

        assert result is True
        mock_conn.create.assert_called_once_with("NewFolder")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_create_mailbox_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.create.return_value = ("NO", [b"Already exists"])

        with IMAPClient(mock_config) as client:
            result = client.create_mailbox("INBOX")

        assert result is False

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_create_mailbox_logs_error(self, mock_imap4_cls, mock_config, caplog):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.create.return_value = ("NO", [b"Create failed"])

        import logging

        with caplog.at_level(logging.ERROR, logger="proton_mcp.clients.imap"):
            with IMAPClient(mock_config) as client:
                client.create_mailbox("BadFolder")

        assert "Failed to create mailbox" in caplog.text


# ===========================================================================
# delete_mailbox tests
# ===========================================================================


class TestIMAPClientDeleteMailbox:
    """Test delete_mailbox() method."""

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_delete_mailbox_success(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.delete.return_value = ("OK", [b"Deleted"])

        with IMAPClient(mock_config) as client:
            result = client.delete_mailbox("OldFolder")

        assert result is True
        mock_conn.delete.assert_called_once_with("OldFolder")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_delete_mailbox_failure(self, mock_imap4_cls, mock_config):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.delete.return_value = ("NO", [b"Cannot delete INBOX"])

        with IMAPClient(mock_config) as client:
            result = client.delete_mailbox("INBOX")

        assert result is False

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_delete_mailbox_logs_error(self, mock_imap4_cls, mock_config, caplog):
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.delete.return_value = ("NO", [b"Delete failed"])

        import logging

        with caplog.at_level(logging.ERROR, logger="proton_mcp.clients.imap"):
            with IMAPClient(mock_config) as client:
                client.delete_mailbox("BadFolder")

        assert "Failed to delete mailbox" in caplog.text


# ===========================================================================
# UID stability test — core bug fix verification
# ===========================================================================


class TestUIDStability:
    """Verify that UID-based operations are stable across deletions.

    This is the core regression test for BUG-unstable-email-ids. Sequence
    numbers shift when messages are deleted; UIDs remain constant. These
    tests verify that the client exclusively uses UIDs.
    """

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_operations_use_uid_not_sequence_numbers(self, mock_imap4_cls, mock_config):
        """All fetch/search/copy/store operations must use mail.uid(), never
        mail.fetch(), mail.search(), mail.copy(), or mail.store()."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"10"])
        mock_conn.uid.return_value = ("OK", [b"100 200 300"])
        mock_conn.expunge.return_value = ("OK", [b"Done"])

        with IMAPClient(mock_config) as client:
            # Search
            client.search("ALL")
            # Fetch
            raw = _make_raw_email()
            mock_conn.uid.return_value = ("OK", _make_fetch_response("100", raw))
            client.fetch_one("100")
            # Copy
            mock_conn.uid.return_value = ("OK", [b"Done"])
            client.copy(["100"], "Archive")
            # Store flags
            mock_conn.uid.return_value = ("OK", [b"Done"])
            client.store_flags(["100"], "\\Deleted")
            # Expunge (uses mail.expunge(), not mail.uid())
            client.expunge()

        # Assert: sequence-based methods were NEVER called
        mock_conn.search.assert_not_called()
        mock_conn.fetch.assert_not_called()
        mock_conn.copy.assert_not_called()
        mock_conn.store.assert_not_called()

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_uids_stable_after_deletion(self, mock_imap4_cls, mock_config):
        """Simulate deleting a message and verify that the remaining UIDs
        are still valid and unchanged."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"3"])
        mock_conn.expunge.return_value = ("OK", [b"Done"])

        # Initial state: 3 emails with UIDs 100, 200, 300
        mock_conn.uid.return_value = ("OK", [b"100 200 300"])

        with IMAPClient(mock_config) as client:
            uids_before = client.search("ALL")
            assert uids_before == ["100", "200", "300"]

            # Delete UID 200 (mark + expunge)
            mock_conn.uid.return_value = ("OK", [b"Done"])
            client.store_flags(["200"], "\\Deleted")
            client.expunge()

            # After deletion: UIDs 100 and 300 remain (unlike sequence numbers
            # where the third message would have shifted from seq 3 to seq 2)
            mock_conn.uid.return_value = ("OK", [b"100 300"])
            uids_after = client.search("ALL")
            assert uids_after == ["100", "300"]

            # Fetching by the original UID 100 still works
            raw = _make_raw_email(subject="First Email")
            mock_conn.uid.return_value = ("OK", _make_fetch_response("100", raw))
            result = client.fetch_one("100")

            assert result is not None
            assert result["id"] == "100"
            assert result["subject"] == "First Email"

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_batch_fetch_preserves_uid_mapping(self, mock_imap4_cls, mock_config):
        """Batch fetch should correctly map each email to its UID, not to a
        sequence number that might shift."""
        mock_conn = MagicMock()
        mock_imap4_cls.return_value = mock_conn
        mock_conn.select.return_value = ("OK", [b"5"])

        raw_a = _make_raw_email(subject="Alpha")
        raw_b = _make_raw_email(subject="Bravo")
        mock_conn.uid.return_value = (
            "OK",
            _make_batch_fetch_response([("500", raw_a), ("700", raw_b)]),
        )

        with IMAPClient(mock_config) as client:
            result = client.fetch_batch(["500", "700"])

        # UIDs must be preserved exactly — not mapped to sequence numbers 1, 2
        assert "500" in result
        assert "700" in result
        assert result["500"]["id"] == "500"
        assert result["700"]["id"] == "700"
        assert result["500"]["subject"] == "Alpha"
        assert result["700"]["subject"] == "Bravo"


# ===========================================================================
# _extract_uid_from_header tests
# ===========================================================================


class TestExtractUIDFromHeader:
    """Test the UID extraction helper."""

    def test_standard_format(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._extract_uid_from_header("1 (UID 123 RFC822 {456})") == "123"

    def test_uid_at_end(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._extract_uid_from_header("1 (RFC822 {456} UID 789)") == "789"

    def test_no_uid_present(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._extract_uid_from_header("1 (RFC822 {456})") is None

    def test_non_numeric_uid(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._extract_uid_from_header("1 (UID abc RFC822 {456})") is None

    def test_large_uid(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._extract_uid_from_header("1 (UID 999999999 RFC822 {456})") == "999999999"


# ===========================================================================
# Edge cases
# ===========================================================================


class TestIMAPClientEdgeCases:
    """Test edge cases and error handling."""

    def test_init_sets_mail_to_none(self, mock_config):
        client = IMAPClient(mock_config)
        assert client._mail is None
        assert client._config is mock_config

    def test_search_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.search("ALL")

    def test_fetch_one_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.fetch_one("42")

    def test_copy_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.copy(["42"], "Archive")

    def test_store_flags_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.store_flags(["42"], "\\Seen")

    def test_expunge_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.expunge()

    def test_list_mailboxes_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.list_mailboxes()

    def test_create_mailbox_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.create_mailbox("Test")

    def test_delete_mailbox_without_connection_raises(self, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.delete_mailbox("Test")

    @patch("proton_mcp.clients.imap.imaplib.IMAP4")
    def test_fetch_batch_without_connection_raises(self, mock_imap4_cls, mock_config):
        client = IMAPClient(mock_config)
        with pytest.raises(AssertionError, match="Not connected"):
            client.fetch_batch(["42"])
