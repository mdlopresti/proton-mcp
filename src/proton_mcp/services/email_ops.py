"""Core email operations service."""

from __future__ import annotations

from typing import Any

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.clients.smtp import SMTPClient
from proton_mcp.config import Config
from proton_mcp.models.email import EmailSummary, FullEmail


class EmailService:
    """Core email operations: search, fetch, send, get recent.

    Depends on IMAPClient and SMTPClient. Does NOT directly use imaplib/smtplib.
    """

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def search_emails(
        self,
        query: str,
        mailbox: str = "INBOX",
        max_results: int = 50,
        include_body: bool = True,
    ) -> list[EmailSummary]:
        """Search emails matching IMAP query. Returns EmailSummary list.

        When include_body=False, skips body extraction for faster results
        (ENHANCEMENT-lightweight-search).
        """
        raise NotImplementedError

    def get_full_email(self, uid: str, mailbox: str = "INBOX") -> FullEmail | None:
        """Fetch a single complete email by UID."""
        raise NotImplementedError

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to_id: str | None = None,
    ) -> bool:
        """Send an email. Returns True on success."""
        raise NotImplementedError

    def get_recent_emails(
        self,
        hours: int = 24,
        mailbox: str = "INBOX",
        max_results: int = 50,
        include_body: bool = True,
    ) -> list[EmailSummary]:
        """Get emails from the last N hours."""
        raise NotImplementedError
