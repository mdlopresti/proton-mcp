"""Integration test fixtures for end-to-end workflow testing.

These fixtures provide a realistic testing environment by creating a real
Config with a temp data_dir, and mock IMAP/SMTP servers that simulate
realistic email server behaviour at the imaplib/smtplib level.
"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proton_mcp.config import Config

# ---------------------------------------------------------------------------
# Helpers for building realistic IMAP responses
# ---------------------------------------------------------------------------


def make_raw_email(
    subject: str = "Test Subject",
    from_addr: str = "sender@example.com",
    to_addr: str = "recipient@proton.me",
    date: str = "Mon, 01 Jan 2024 12:00:00 +0000",
    body: str = "Hello, world!",
    html_body: str = "",
    list_unsubscribe: str = "",
    list_unsubscribe_post: str = "",
) -> bytes:
    """Build a minimal RFC822 email as bytes with optional headers."""
    headers = f"Subject: {subject}\r\nFrom: {from_addr}\r\nTo: {to_addr}\r\nDate: {date}\r\n"
    if list_unsubscribe:
        headers += f"List-Unsubscribe: {list_unsubscribe}\r\n"
    if list_unsubscribe_post:
        headers += f"List-Unsubscribe-Post: {list_unsubscribe_post}\r\n"

    if html_body:
        boundary = "----=_Part_12345"
        headers += f'Content-Type: multipart/alternative; boundary="{boundary}"\r\n'
        body_part = (
            f"\r\n--{boundary}\r\n"
            f"Content-Type: text/plain; charset=utf-8\r\n\r\n"
            f"{body}\r\n"
            f"--{boundary}\r\n"
            f"Content-Type: text/html; charset=utf-8\r\n\r\n"
            f"{html_body}\r\n"
            f"--{boundary}--\r\n"
        )
        return (headers + body_part).encode()

    headers += "Content-Type: text/plain; charset=utf-8\r\n"
    return (headers + f"\r\n{body}").encode()


def make_fetch_response(uid: str, raw_email: bytes) -> list:
    """Build an IMAP FETCH response tuple for a single UID."""
    header = f"1 (UID {uid} RFC822 {{{len(raw_email)}}})".encode()
    return [(header, raw_email), b")"]


def make_batch_fetch_response(uid_email_pairs: list[tuple[str, bytes]]) -> list:
    """Build an IMAP FETCH response for multiple UIDs."""
    result = []
    for seq, (uid, raw_email) in enumerate(uid_email_pairs, start=1):
        header = f"{seq} (UID {uid} RFC822 {{{len(raw_email)}}})".encode()
        result.append((header, raw_email))
        result.append(b")")
    return result


# ---------------------------------------------------------------------------
# Config fixture with real temp directory
# ---------------------------------------------------------------------------


@pytest.fixture
def integration_data_dir():
    """Temporary directory for integration test data files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def integration_config(integration_data_dir):
    """Real Config object pointing to a temp data directory."""
    return Config(
        imap_host="127.0.0.1",
        imap_port=1143,
        smtp_host="127.0.0.1",
        smtp_port=1025,
        email="test@proton.me",
        password="test-bridge-password",  # noqa: S106
        data_dir=str(integration_data_dir),
    )


@pytest.fixture
def integration_env_vars(integration_data_dir):
    """Set environment variables for Config.from_env() in integration tests."""
    env = {
        "PROTON_EMAIL": "test@proton.me",
        "PROTON_BRIDGE_PASSWORD": "test-bridge-password",
        "BRIDGE_IMAP_HOST": "127.0.0.1",
        "BRIDGE_IMAP_PORT": "1143",
        "BRIDGE_SMTP_HOST": "127.0.0.1",
        "BRIDGE_SMTP_PORT": "1025",
        "PROTON_DATA_DIR": str(integration_data_dir),
    }
    with patch.dict(os.environ, env, clear=False):
        yield


# ---------------------------------------------------------------------------
# Mock IMAP server that simulates realistic behaviour
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_imap_conn():
    """A mock IMAP4 connection that simulates realistic server responses.

    Provides sensible defaults for select, uid (search/fetch/copy/store),
    list, create, delete, expunge, close, and logout.
    """
    conn = MagicMock()
    conn.select.return_value = ("OK", [b"10"])
    conn.uid.return_value = ("OK", [b""])
    conn.list.return_value = (
        "OK",
        [
            b'(\\HasNoChildren) "/" "INBOX"',
            b'(\\HasNoChildren) "/" "Sent"',
            b'(\\HasNoChildren) "/" "Drafts"',
            b'(\\HasNoChildren) "/" "Trash"',
            b'(\\HasNoChildren) "/" "Spam"',
            b'(\\HasNoChildren) "/" "Archive"',
        ],
    )
    conn.create.return_value = ("OK", [b"Created"])
    conn.delete.return_value = ("OK", [b"Deleted"])
    conn.expunge.return_value = ("OK", [b"Done"])
    conn.close.return_value = ("OK", [b"Closing"])
    conn.logout.return_value = ("BYE", [b"Logging out"])
    conn.starttls.return_value = None
    conn.login.return_value = ("OK", [b"Logged in"])
    return conn


@pytest.fixture
def patch_imap(mock_imap_conn):
    """Patch imaplib.IMAP4 to return the mock connection."""
    with patch("proton_mcp.clients.imap.imaplib.IMAP4", return_value=mock_imap_conn):
        yield mock_imap_conn


# ---------------------------------------------------------------------------
# Mock SMTP server
# ---------------------------------------------------------------------------


@pytest.fixture
def mock_smtp_conn():
    """A mock SMTP connection that simulates realistic server responses."""
    conn = MagicMock()
    conn.starttls.return_value = (220, b"Ready for TLS")
    conn.login.return_value = (235, b"Authenticated")
    conn.send_message.return_value = {}
    conn.sendmail.return_value = {}
    conn.quit.return_value = (221, b"Bye")
    return conn


@pytest.fixture
def patch_smtp(mock_smtp_conn):
    """Patch smtplib.SMTP to return the mock connection."""
    with patch("proton_mcp.clients.smtp.smtplib.SMTP", return_value=mock_smtp_conn):
        yield mock_smtp_conn


# ---------------------------------------------------------------------------
# Combined fixture for tests that need both IMAP and SMTP
# ---------------------------------------------------------------------------


@pytest.fixture
def patch_mail(patch_imap, patch_smtp):
    """Patch both IMAP and SMTP for end-to-end tool tests."""
    return {"imap": patch_imap, "smtp": patch_smtp}
