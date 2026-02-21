"""Core email operations service."""

from __future__ import annotations

import logging
from datetime import datetime, timedelta, timezone

from proton_mcp.clients.imap import IMAPClient
from proton_mcp.clients.smtp import SMTPClient
from proton_mcp.config import Config
from proton_mcp.models.email import EmailSummary, FullEmail

logger = logging.getLogger(__name__)

_BODY_PREVIEW_LENGTH = 200


class EmailService:
    """Core email operations: search, fetch, send, get recent.

    Depends on IMAPClient and SMTPClient. Does NOT directly use imaplib/smtplib.
    """

    def __init__(self, config: Config) -> None:
        self._config = config

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
        with IMAPClient(self._config) as imap:
            uids = imap.search(query, mailbox)
            if not uids:
                return []

            # Limit to max_results (take the most recent UIDs, which are at the end)
            uids = uids[-max_results:]

            fetched = imap.fetch_batch(uids, mailbox)

        results: list[EmailSummary] = []
        for uid in uids:
            data = fetched.get(uid)
            if data is None:
                continue

            body = data.get("body", "")
            if include_body:
                preview = body[:_BODY_PREVIEW_LENGTH] if body else ""
            else:
                preview = ""

            results.append(
                EmailSummary(
                    id=data["id"],
                    subject=data.get("subject", ""),
                    from_addr=data.get("from", ""),
                    date=data.get("date", ""),
                    body_preview=preview,
                )
            )

        return results

    def get_full_email(self, uid: str, mailbox: str = "INBOX") -> FullEmail | None:
        """Fetch a single complete email by UID."""
        with IMAPClient(self._config) as imap:
            data = imap.fetch_one(uid, mailbox)

        if data is None:
            return None

        return FullEmail(
            id=data["id"],
            subject=data.get("subject", ""),
            from_addr=data.get("from", ""),
            to_addr=data.get("to", ""),
            date=data.get("date", ""),
            body=data.get("body", ""),
        )

    def send_email(
        self,
        to: str,
        subject: str,
        body: str,
        reply_to_id: str | None = None,
    ) -> bool:
        """Send an email. Returns True on success."""
        with SMTPClient(self._config) as smtp:
            return smtp.send_email(to, subject, body, reply_to_id)

    def get_recent_emails(
        self,
        hours: int = 24,
        mailbox: str = "INBOX",
        max_results: int = 50,
        include_body: bool = True,
    ) -> list[EmailSummary]:
        """Get emails from the last N hours."""
        since = datetime.now(tz=timezone.utc) - timedelta(hours=hours)
        date_str = since.strftime("%d-%b-%Y")
        query = f"SINCE {date_str}"
        return self.search_emails(query, mailbox, max_results, include_body)
