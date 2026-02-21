"""Tests for EmailService — core email operations."""

from __future__ import annotations

from datetime import UTC, datetime, timedelta
from unittest.mock import MagicMock, patch

from proton_mcp.models.email import EmailSummary, FullEmail
from proton_mcp.services.email_ops import _BODY_PREVIEW_LENGTH, EmailService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _email_dict(
    uid: str = "100",
    subject: str = "Test Subject",
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@example.com",
    date: str = "Mon, 01 Jan 2024 12:00:00 +0000",
    body: str = "Hello, world!",
) -> dict:
    """Build an email dict matching IMAPClient's parsed output."""
    return {
        "id": uid,
        "subject": subject,
        "from": from_addr,
        "to": to_addr,
        "date": date,
        "body": body,
    }


# ===========================================================================
# __init__ tests
# ===========================================================================


class TestEmailServiceInit:
    """Test EmailService construction."""

    def test_stores_config(self, mock_config):
        service = EmailService(mock_config)
        assert service._config is mock_config


# ===========================================================================
# search_emails tests
# ===========================================================================


class TestSearchEmails:
    """Test EmailService.search_emails."""

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_basic_search_returns_email_summaries(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100", "200"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", subject="First", body="Body one"),
            "200": _email_dict(uid="200", subject="Second", body="Body two"),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL")

        assert len(results) == 2
        assert all(isinstance(r, EmailSummary) for r in results)
        assert results[0].id == "100"
        assert results[0].subject == "First"
        assert results[0].from_addr == "sender@example.com"
        assert results[0].body_preview == "Body one"
        assert results[1].id == "200"
        assert results[1].subject == "Second"

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_respects_max_results_limit(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Return 5 UIDs but ask for max 2
        mock_imap.search.return_value = ["1", "2", "3", "4", "5"]
        # Only the last 2 (most recent) should be fetched
        mock_imap.fetch_batch.return_value = {
            "4": _email_dict(uid="4", subject="Fourth"),
            "5": _email_dict(uid="5", subject="Fifth"),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL", max_results=2)

        assert len(results) == 2
        # Verify fetch_batch was called with only the last 2 UIDs
        mock_imap.fetch_batch.assert_called_once_with(["4", "5"], "INBOX")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_include_body_false_sets_empty_preview(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", body="This body should not appear"),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL", include_body=False)

        assert len(results) == 1
        assert results[0].body_preview == ""

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_include_body_true_truncates_to_200_chars(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        long_body = "x" * 500
        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", body=long_body),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL", include_body=True)

        assert len(results) == 1
        assert len(results[0].body_preview) == _BODY_PREVIEW_LENGTH
        assert results[0].body_preview == "x" * _BODY_PREVIEW_LENGTH

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_empty_search_returns_empty_list(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = []

        service = EmailService(mock_config)
        results = service.search_emails("ALL")

        assert results == []
        # fetch_batch should NOT be called when search returns empty
        mock_imap.fetch_batch.assert_not_called()

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_correct_mailbox_is_passed_through(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100"),
        }

        service = EmailService(mock_config)
        service.search_emails("ALL", mailbox="Sent")

        mock_imap.search.assert_called_once_with("ALL", "Sent")
        mock_imap.fetch_batch.assert_called_once_with(["100"], "Sent")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_handles_partial_fetch_results(self, mock_imap_cls, mock_config):
        """If fetch_batch does not return all UIDs, only include fetched ones."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100", "200", "300"]
        # Only 2 of 3 UIDs returned by fetch_batch
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", subject="First"),
            "300": _email_dict(uid="300", subject="Third"),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL")

        assert len(results) == 2
        assert results[0].id == "100"
        assert results[1].id == "300"

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_preserves_uid_order(self, mock_imap_cls, mock_config):
        """Results should be in the same order as the UIDs from search."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["300", "100", "200"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", subject="A"),
            "200": _email_dict(uid="200", subject="B"),
            "300": _email_dict(uid="300", subject="C"),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL")

        assert [r.id for r in results] == ["300", "100", "200"]

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_imap_client_used_as_context_manager(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = []

        service = EmailService(mock_config)
        service.search_emails("ALL")

        mock_imap_cls.return_value.__enter__.assert_called_once()
        mock_imap_cls.return_value.__exit__.assert_called_once()

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_body_preview_empty_body(self, mock_imap_cls, mock_config):
        """When body is empty or None, preview should be empty string."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", body=""),
        }

        service = EmailService(mock_config)
        results = service.search_emails("ALL", include_body=True)

        assert len(results) == 1
        assert results[0].body_preview == ""


# ===========================================================================
# get_full_email tests
# ===========================================================================


class TestGetFullEmail:
    """Test EmailService.get_full_email."""

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_returns_full_email_for_existing_uid(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.fetch_one.return_value = _email_dict(
            uid="42",
            subject="Important",
            from_addr="boss@company.com",
            to_addr="me@proton.me",
            date="Tue, 02 Jan 2024 09:00:00 +0000",
            body="Meeting at 3pm.",
        )

        service = EmailService(mock_config)
        result = service.get_full_email("42")

        assert result is not None
        assert isinstance(result, FullEmail)
        assert result.id == "42"
        assert result.subject == "Important"
        assert result.from_addr == "boss@company.com"
        assert result.to_addr == "me@proton.me"
        assert result.date == "Tue, 02 Jan 2024 09:00:00 +0000"
        assert result.body == "Meeting at 3pm."

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_returns_none_for_missing_uid(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.fetch_one.return_value = None

        service = EmailService(mock_config)
        result = service.get_full_email("999")

        assert result is None

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_all_fields_mapped_correctly(self, mock_imap_cls, mock_config):
        """Verify the key mapping: dict 'from' -> model 'from_addr', dict 'to' -> model 'to_addr'."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.fetch_one.return_value = {
            "id": "7",
            "subject": "Subj",
            "from": "alice@example.com",
            "to": "bob@example.com",
            "date": "Wed, 03 Jan 2024 10:00:00 +0000",
            "body": "Body content",
        }

        service = EmailService(mock_config)
        result = service.get_full_email("7")

        assert result is not None
        assert result.id == "7"
        assert result.subject == "Subj"
        assert result.from_addr == "alice@example.com"  # mapped from "from"
        assert result.to_addr == "bob@example.com"  # mapped from "to"
        assert result.date == "Wed, 03 Jan 2024 10:00:00 +0000"
        assert result.body == "Body content"

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_correct_mailbox_passed_through(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.fetch_one.return_value = _email_dict(uid="10")

        service = EmailService(mock_config)
        service.get_full_email("10", mailbox="Archive")

        mock_imap.fetch_one.assert_called_once_with("10", "Archive")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_imap_client_used_as_context_manager(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.fetch_one.return_value = None

        service = EmailService(mock_config)
        service.get_full_email("1")

        mock_imap_cls.return_value.__enter__.assert_called_once()
        mock_imap_cls.return_value.__exit__.assert_called_once()

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_handles_missing_optional_fields(self, mock_imap_cls, mock_config):
        """If dict has missing keys, defaults to empty strings."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Minimal dict — only 'id' is present
        mock_imap.fetch_one.return_value = {"id": "50"}

        service = EmailService(mock_config)
        result = service.get_full_email("50")

        assert result is not None
        assert result.id == "50"
        assert result.subject == ""
        assert result.from_addr == ""
        assert result.to_addr == ""
        assert result.date == ""
        assert result.body == ""


# ===========================================================================
# send_email tests
# ===========================================================================


class TestSendEmail:
    """Test EmailService.send_email."""

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_returns_true_on_success(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_smtp.send_email.return_value = True

        service = EmailService(mock_config)
        result = service.send_email("to@example.com", "Subject", "Body")

        assert result is True

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_returns_false_on_failure(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_smtp.send_email.return_value = False

        service = EmailService(mock_config)
        result = service.send_email("to@example.com", "Subject", "Body")

        assert result is False

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_reply_to_id_passed_through(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_smtp.send_email.return_value = True

        service = EmailService(mock_config)
        service.send_email("to@example.com", "Re: Thread", "Reply body", reply_to_id="<msg-id@example.com>")

        mock_smtp.send_email.assert_called_once_with(
            "to@example.com", "Re: Thread", "Reply body", "<msg-id@example.com>"
        )

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_reply_to_id_defaults_to_none(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_smtp.send_email.return_value = True

        service = EmailService(mock_config)
        service.send_email("to@example.com", "Subject", "Body")

        mock_smtp.send_email.assert_called_once_with("to@example.com", "Subject", "Body", None)

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_smtp_client_used_as_context_manager(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_smtp.send_email.return_value = True

        service = EmailService(mock_config)
        service.send_email("to@example.com", "Subject", "Body")

        mock_smtp_cls.return_value.__enter__.assert_called_once()
        mock_smtp_cls.return_value.__exit__.assert_called_once()

    @patch("proton_mcp.services.email_ops.SMTPClient")
    def test_config_passed_to_smtp_client(self, mock_smtp_cls, mock_config):
        mock_smtp = MagicMock()
        mock_smtp_cls.return_value.__enter__ = MagicMock(return_value=mock_smtp)
        mock_smtp_cls.return_value.__exit__ = MagicMock(return_value=False)
        mock_smtp.send_email.return_value = True

        service = EmailService(mock_config)
        service.send_email("to@example.com", "Subject", "Body")

        mock_smtp_cls.assert_called_once_with(mock_config)


# ===========================================================================
# get_recent_emails tests
# ===========================================================================


class TestGetRecentEmails:
    """Test EmailService.get_recent_emails."""

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_builds_correct_since_query(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = []

        service = EmailService(mock_config)
        service.get_recent_emails(hours=24)

        # Verify the SINCE query was built with the correct date format
        call_args = mock_imap.search.call_args
        query = call_args[0][0]
        assert query.startswith("SINCE ")
        # The date part should match IMAP date format: DD-Mon-YYYY
        date_part = query.replace("SINCE ", "")
        # Verify it parses as a valid date
        parsed = datetime.strptime(date_part, "%d-%b-%Y")
        assert parsed is not None

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_hours_parameter_affects_date(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = []

        service = EmailService(mock_config)

        # 168 hours = 7 days
        service.get_recent_emails(hours=168)

        expected_date = (datetime.now(tz=UTC) - timedelta(hours=168)).strftime("%d-%b-%Y")
        expected_query = f"SINCE {expected_date}"

        mock_imap.search.assert_called_once_with(expected_query, "INBOX")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_passes_through_to_search_emails(self, mock_imap_cls, mock_config):
        """get_recent_emails delegates to search_emails with correct args."""
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", subject="Recent"),
        }

        service = EmailService(mock_config)
        results = service.get_recent_emails(hours=48, mailbox="Sent", max_results=10, include_body=False)

        assert len(results) == 1
        assert results[0].subject == "Recent"
        # Verify search was called with "Sent" mailbox
        mock_imap.search.assert_called_once()
        call_args = mock_imap.search.call_args
        assert call_args[0][1] == "Sent"

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_include_body_passed_through(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100", body="Some body text"),
        }

        service = EmailService(mock_config)
        results = service.get_recent_emails(include_body=False)

        assert len(results) == 1
        assert results[0].body_preview == ""

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_max_results_passed_through(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        # Return more UIDs than max_results
        mock_imap.search.return_value = ["1", "2", "3", "4", "5"]
        mock_imap.fetch_batch.return_value = {
            "4": _email_dict(uid="4"),
            "5": _email_dict(uid="5"),
        }

        service = EmailService(mock_config)
        results = service.get_recent_emails(max_results=2)

        assert len(results) == 2
        # Should have been limited to last 2 UIDs
        mock_imap.fetch_batch.assert_called_once_with(["4", "5"], "INBOX")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_default_hours_is_24(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = []

        service = EmailService(mock_config)
        service.get_recent_emails()

        expected_date = (datetime.now(tz=UTC) - timedelta(hours=24)).strftime("%d-%b-%Y")
        expected_query = f"SINCE {expected_date}"

        mock_imap.search.assert_called_once_with(expected_query, "INBOX")

    @patch("proton_mcp.services.email_ops.IMAPClient")
    def test_returns_email_summary_list(self, mock_imap_cls, mock_config):
        mock_imap = MagicMock()
        mock_imap_cls.return_value.__enter__ = MagicMock(return_value=mock_imap)
        mock_imap_cls.return_value.__exit__ = MagicMock(return_value=False)

        mock_imap.search.return_value = ["100"]
        mock_imap.fetch_batch.return_value = {
            "100": _email_dict(uid="100"),
        }

        service = EmailService(mock_config)
        results = service.get_recent_emails()

        assert len(results) == 1
        assert isinstance(results[0], EmailSummary)
