"""Tests for proton_mcp.utils.mime module."""

import email
from email.message import Message
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from pathlib import Path

import pytest

from proton_mcp.utils.mime import (
    decode_mime_words,
    get_email_body,
    get_html_body,
    get_text_and_html,
)


FIXTURES_DIR = Path(__file__).parent.parent / "fixtures" / "sample_emails"


def _load_eml(name: str) -> Message:
    """Load an .eml file from the fixtures directory and return a Message."""
    path = FIXTURES_DIR / name
    with open(path, "rb") as f:
        return email.message_from_bytes(f.read())


# ---------------------------------------------------------------------------
# decode_mime_words
# ---------------------------------------------------------------------------


class TestDecodeMimeWords:
    def test_plain_ascii(self):
        assert decode_mime_words("Hello World") == "Hello World"

    def test_none_returns_empty(self):
        assert decode_mime_words(None) == ""

    def test_empty_string(self):
        assert decode_mime_words("") == ""

    def test_rfc2047_base64_utf8(self):
        # =?UTF-8?B?V2Vla2x5IE5ld3NsZXR0ZXI=?= decodes to "Weekly Newsletter"
        encoded = "=?UTF-8?B?V2Vla2x5IE5ld3NsZXR0ZXI=?="
        assert decode_mime_words(encoded) == "Weekly Newsletter"

    def test_rfc2047_quoted_printable(self):
        encoded = "=?utf-8?Q?Hello_World?="
        assert decode_mime_words(encoded) == "Hello World"

    def test_mixed_encoded_and_plain(self):
        encoded = "Re: =?UTF-8?B?V2Vla2x5IE5ld3NsZXR0ZXI=?="
        result = decode_mime_words(encoded)
        assert "Weekly Newsletter" in result
        assert "Re:" in result

    def test_from_simple_eml_fixture(self):
        msg = _load_eml("simple.eml")
        assert decode_mime_words(msg["Subject"]) == "Test Email"

    def test_from_multipart_eml_fixture(self):
        msg = _load_eml("multipart.eml")
        assert decode_mime_words(msg["Subject"]) == "Weekly Newsletter"

    def test_from_spam_eml_fixture(self):
        msg = _load_eml("spam.eml")
        result = decode_mime_words(msg["Subject"])
        assert "CONGRATULATIONS" in result


# ---------------------------------------------------------------------------
# get_email_body
# ---------------------------------------------------------------------------


class TestGetEmailBody:
    def test_simple_text_email(self):
        msg = _load_eml("simple.eml")
        body = get_email_body(msg)
        assert "simple test email body" in body

    def test_multipart_extracts_plain_text(self):
        msg = _load_eml("multipart.eml")
        body = get_email_body(msg)
        assert "plain text version" in body
        # Should NOT contain HTML tags
        assert "<html>" not in body

    def test_spam_email_body(self):
        msg = _load_eml("spam.eml")
        body = get_email_body(msg)
        assert "URGENT" in body
        assert "lottery" in body

    def test_empty_payload(self):
        msg = Message()
        msg["Subject"] = "Empty"
        msg.set_payload("")
        body = get_email_body(msg)
        assert body == ""

    def test_multipart_with_only_html(self):
        """If there is no text/plain part, get_email_body returns empty."""
        outer = MIMEMultipart()
        html_part = MIMEText("<p>Only HTML</p>", "html")
        outer.attach(html_part)
        body = get_email_body(outer)
        assert body == ""

    def test_multipart_skips_attachments(self):
        outer = MIMEMultipart()
        text_attach = MIMEText("Attached text", "plain")
        text_attach.add_header("Content-Disposition", "attachment", filename="readme.txt")
        outer.attach(text_attach)

        inline_text = MIMEText("Inline body", "plain")
        outer.attach(inline_text)

        body = get_email_body(outer)
        assert "Inline body" in body
        assert "Attached text" not in body

    def test_single_part_bytes_payload(self):
        msg = Message()
        msg["Content-Type"] = "text/plain; charset=utf-8"
        msg.set_payload(b"Hello bytes", "utf-8")
        body = get_email_body(msg)
        # Should handle bytes or string payload gracefully
        assert isinstance(body, str)


# ---------------------------------------------------------------------------
# get_html_body
# ---------------------------------------------------------------------------


class TestGetHtmlBody:
    def test_simple_text_email_no_html(self):
        msg = _load_eml("simple.eml")
        html = get_html_body(msg)
        assert html == ""

    def test_multipart_extracts_html(self):
        msg = _load_eml("multipart.eml")
        html = get_html_body(msg)
        assert "<html>" in html
        assert "Weekly Newsletter" in html

    def test_single_part_html_message(self):
        msg = MIMEText("<p>Hello</p>", "html")
        html = get_html_body(msg)
        assert "<p>Hello</p>" in html

    def test_single_part_text_message_no_html(self):
        msg = MIMEText("Just text", "plain")
        html = get_html_body(msg)
        assert html == ""

    def test_multipart_skips_html_attachment(self):
        outer = MIMEMultipart()
        html_attach = MIMEText("<p>Attached HTML</p>", "html")
        html_attach.add_header("Content-Disposition", "attachment", filename="page.html")
        outer.attach(html_attach)

        html_inline = MIMEText("<p>Inline HTML</p>", "html")
        outer.attach(html_inline)

        html = get_html_body(outer)
        assert "Inline HTML" in html
        assert "Attached HTML" not in html


# ---------------------------------------------------------------------------
# get_text_and_html
# ---------------------------------------------------------------------------


class TestGetTextAndHtml:
    def test_simple_text_email(self):
        msg = _load_eml("simple.eml")
        text, html = get_text_and_html(msg)
        assert "simple test email body" in text
        assert html == ""

    def test_multipart_both_parts(self):
        msg = _load_eml("multipart.eml")
        text, html = get_text_and_html(msg)
        assert "plain text version" in text
        assert "<html>" in html
        assert "Weekly Newsletter" in html

    def test_single_part_html_only(self):
        msg = MIMEText("<p>Only HTML</p>", "html")
        text, html = get_text_and_html(msg)
        assert text == ""
        assert "<p>Only HTML</p>" in html

    def test_single_part_text_only(self):
        msg = MIMEText("Only text", "plain")
        text, html = get_text_and_html(msg)
        assert "Only text" in text
        assert html == ""

    def test_spam_email_text_only(self):
        msg = _load_eml("spam.eml")
        text, html = get_text_and_html(msg)
        assert "URGENT" in text
        assert html == ""

    def test_empty_message(self):
        msg = Message()
        msg.set_payload("")
        text, html = get_text_and_html(msg)
        assert text == ""
        assert html == ""


# ---------------------------------------------------------------------------
# Edge cases: exception handling in payload decoding
# ---------------------------------------------------------------------------


class TestMimeExceptionHandling:
    """Test exception paths in payload decoding."""

    def test_get_email_body_single_part_exception_fallback(self):
        """When get_payload(decode=True) raises, falls back to str(get_payload())."""
        msg = Message()
        msg["Content-Type"] = "text/plain"
        # Set a non-bytes payload that will cause decode=True to fail on older paths
        # Use a payload that is a list (simulates a broken single-part message)
        msg._payload = "fallback text"
        msg["Content-Transfer-Encoding"] = "invalid-encoding-that-will-fail"
        body = get_email_body(msg)
        # Should get something back (either decoded or the fallback)
        assert isinstance(body, str)

    def test_get_email_body_multipart_bad_part_skipped(self):
        """If a multipart text/plain part fails to decode, skip to next."""
        from unittest.mock import MagicMock, patch

        outer = MIMEMultipart()

        # Create a bad part that raises on get_payload
        bad_part = MagicMock()
        bad_part.get_content_type.return_value = "text/plain"
        bad_part.get.return_value = None  # No Content-Disposition
        bad_part.get_payload.side_effect = Exception("decode error")

        good_part = MIMEText("Good body text", "plain")

        # Patch walk to return our custom parts
        with patch.object(outer, "walk", return_value=[bad_part, good_part]):
            with patch.object(outer, "is_multipart", return_value=True):
                body = get_email_body(outer)
        assert "Good body text" in body

    def test_get_html_body_multipart_bad_html_part_skipped(self):
        """If a multipart text/html part fails to decode, skip to next."""
        from unittest.mock import MagicMock, patch

        outer = MIMEMultipart()

        bad_part = MagicMock()
        bad_part.get_content_type.return_value = "text/html"
        bad_part.get.return_value = None
        bad_part.get_payload.side_effect = Exception("decode error")

        good_part = MIMEText("<p>Good HTML</p>", "html")

        with patch.object(outer, "walk", return_value=[bad_part, good_part]):
            with patch.object(outer, "is_multipart", return_value=True):
                html = get_html_body(outer)
        assert "Good HTML" in html

    def test_get_html_body_single_part_exception(self):
        """Single part HTML message with decode failure returns empty."""
        msg = Message()
        msg["Content-Type"] = "text/html"
        msg.set_payload("not really decodable")
        # This should work normally, but let's test the exception path
        # by mocking get_payload to raise
        from unittest.mock import patch
        with patch.object(msg, "get_payload", side_effect=Exception("fail")):
            html = get_html_body(msg)
        assert html == ""

    def test_get_text_and_html_multipart_bad_part_skipped(self):
        """If a multipart part fails to decode in get_text_and_html, skip it."""
        from unittest.mock import MagicMock, patch

        outer = MIMEMultipart()

        bad_part = MagicMock()
        bad_part.get_content_type.return_value = "text/plain"
        bad_part.get.return_value = None
        bad_part.get_payload.side_effect = Exception("decode error")

        good_text = MIMEText("Good text", "plain")
        good_html = MIMEText("<p>Good HTML</p>", "html")

        with patch.object(outer, "walk", return_value=[bad_part, good_text, good_html]):
            with patch.object(outer, "is_multipart", return_value=True):
                text, html = get_text_and_html(outer)
        assert "Good text" in text
        assert "Good HTML" in html

    def test_get_text_and_html_single_part_exception(self):
        """Single-part message with decode failure returns empty tuple."""
        msg = Message()
        msg["Content-Type"] = "text/plain"
        msg.set_payload("test")
        from unittest.mock import patch
        with patch.object(msg, "get_payload", side_effect=Exception("fail")):
            text, html = get_text_and_html(msg)
        assert text == ""
        assert html == ""

    def test_get_email_body_single_part_decode_exception_fallback(self):
        """Single part where get_payload(decode=True) raises falls back to str."""
        msg = Message()
        msg["Content-Type"] = "text/plain"

        from unittest.mock import patch

        call_count = 0
        original_get_payload = msg.get_payload

        def side_effect(decode=False):
            nonlocal call_count
            call_count += 1
            if decode:
                raise Exception("decode failure")
            return "raw payload string"

        with patch.object(msg, "get_payload", side_effect=side_effect):
            body = get_email_body(msg)
        assert body == "raw payload string"
