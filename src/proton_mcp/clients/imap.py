"""IMAP client with UID-based operations."""

from __future__ import annotations

import email
import imaplib
import logging
from typing import Any

from proton_mcp.config import Config
from proton_mcp.utils.mime import decode_mime_words, get_email_body

logger = logging.getLogger(__name__)


class IMAPClient:
    """IMAP client using UIDs for all operations. Supports context manager."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._mail: imaplib.IMAP4 | None = None

    def __enter__(self) -> IMAPClient:
        try:
            self._mail = imaplib.IMAP4(self._config.imap_host, self._config.imap_port)
            self._mail.starttls()
            self._mail.login(self._config.email, self._config.password)
            return self
        except Exception:
            logger.error("IMAP connection failed", exc_info=True)
            raise

    def __exit__(self, *args: Any) -> None:
        if self._mail is None:
            return
        try:
            self._mail.close()
        except Exception:
            pass
        try:
            self._mail.logout()
        except Exception:
            pass
        self._mail = None

    # ------------------------------------------------------------------
    # Search
    # ------------------------------------------------------------------

    def search(self, query: str, mailbox: str = "INBOX") -> list[str]:
        """Search for emails, returns list of UIDs."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, response = self._mail.select(mailbox)
        if status != "OK":
            logger.error("Failed to select mailbox '%s': %s", mailbox, response)
            return []

        status, data = self._mail.uid("search", "", query)
        if status != "OK":
            return []

        raw = data[0]
        if not raw or raw == b"":
            return []
        return [uid.decode() for uid in raw.split()]

    # ------------------------------------------------------------------
    # Fetch
    # ------------------------------------------------------------------

    def _parse_email(self, uid: str, raw_email: bytes) -> dict[str, Any]:
        """Parse raw email bytes into a dict."""
        msg = email.message_from_bytes(raw_email)
        return {
            "id": uid,
            "subject": decode_mime_words(msg["Subject"]),
            "from": decode_mime_words(msg["From"]),
            "to": decode_mime_words(msg["To"]),
            "date": msg["Date"],
            "body": get_email_body(msg),
        }

    def fetch_one(self, uid: str, mailbox: str = "INBOX") -> dict[str, Any] | None:
        """Fetch a single email by UID."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, response = self._mail.select(mailbox)
        if status != "OK":
            logger.error("Failed to select mailbox '%s': %s", mailbox, response)
            return None

        status, msg_data = self._mail.uid("fetch", uid, "(RFC822)")
        if status != "OK":
            return None

        # msg_data is a list; for a single UID fetch, we expect a tuple entry
        # followed by a closing b')'. Filter for tuples with raw email data.
        for item in msg_data:
            if isinstance(item, tuple) and len(item) >= 2:
                raw_email = item[1]
                if raw_email:
                    return self._parse_email(uid, raw_email)

        return None

    def fetch_batch(self, uids: list[str], mailbox: str = "INBOX") -> dict[str, dict[str, Any]]:
        """Fetch multiple emails by UIDs."""
        assert self._mail is not None, "Not connected — use as context manager"
        if not uids:
            return {}

        status, response = self._mail.select(mailbox)
        if status != "OK":
            logger.error("Failed to select mailbox '%s': %s", mailbox, response)
            return {}

        uid_set = ",".join(uids)
        emails: dict[str, dict[str, Any]] = {}

        try:
            status, msg_data = self._mail.uid("fetch", uid_set, "(RFC822)")
            if status != "OK" or not msg_data:
                return {}

            # When fetching via UID, the IMAP response header contains the UID
            # in the format: b'N (UID XXXX RFC822 {size}'
            # We need to extract the UID from each response item.
            uid_set_remaining = set(uids)
            for item in msg_data:
                if isinstance(item, tuple) and len(item) >= 2:
                    header = item[0]
                    raw_email = item[1]
                    if isinstance(header, bytes) and raw_email:
                        # Extract UID from the FETCH response header.
                        # Format: b'SEQ (UID 123 RFC822 {size}' or
                        #         b'SEQ (RFC822 {size} UID 123'
                        header_str = header.decode("ascii", errors="ignore")
                        fetched_uid = self._extract_uid_from_header(header_str)
                        if fetched_uid and fetched_uid in uid_set_remaining:
                            emails[fetched_uid] = self._parse_email(fetched_uid, raw_email)
                            uid_set_remaining.discard(fetched_uid)

        except Exception:
            logger.warning("Batch fetch failed, falling back to individual fetch", exc_info=True)
            for uid in uids:
                if uid not in emails:
                    result = self._fetch_one_no_select(uid)
                    if result is not None:
                        emails[uid] = result

        return emails

    def _extract_uid_from_header(self, header: str) -> str | None:
        """Extract UID value from an IMAP FETCH response header string.

        The header looks like: ``1 (UID 123 RFC822 {456})`` or
        ``1 (RFC822 {456} UID 123)``.
        """
        upper = header.upper()
        idx = upper.find("UID ")
        if idx == -1:
            return None
        # Grab the token immediately after "UID "
        rest = header[idx + 4 :].strip()
        uid_val = rest.split()[0].rstrip(")")
        return uid_val if uid_val.isdigit() else None

    def _fetch_one_no_select(self, uid: str) -> dict[str, Any] | None:
        """Fetch a single email by UID without re-selecting the mailbox."""
        assert self._mail is not None
        try:
            status, msg_data = self._mail.uid("fetch", uid, "(RFC822)")
            if status != "OK":
                return None
            for item in msg_data:
                if isinstance(item, tuple) and len(item) >= 2 and item[1]:
                    return self._parse_email(uid, item[1])
        except Exception:
            logger.warning("Failed to fetch email UID %s", uid, exc_info=True)
        return None

    # ------------------------------------------------------------------
    # Copy / Store / Expunge
    # ------------------------------------------------------------------

    def copy(self, uids: list[str], target_mailbox: str) -> bool:
        """Copy emails to target mailbox."""
        assert self._mail is not None, "Not connected — use as context manager"
        uid_set = ",".join(uids)
        status, response = self._mail.uid("copy", uid_set, target_mailbox)
        if status != "OK":
            logger.error("Failed to copy UIDs %s to %s: %s", uid_set, target_mailbox, response)
            return False
        return True

    def store_flags(self, uids: list[str], flags: str, action: str = "+FLAGS") -> bool:
        """Set/remove flags on emails."""
        assert self._mail is not None, "Not connected — use as context manager"
        uid_set = ",".join(uids)
        status, response = self._mail.uid("store", uid_set, action, flags)
        if status != "OK":
            logger.error(
                "Failed to store flags %s %s on UIDs %s: %s",
                action,
                flags,
                uid_set,
                response,
            )
            return False
        return True

    def expunge(self) -> bool:
        """Expunge deleted messages."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, response = self._mail.expunge()
        if status != "OK":
            logger.error("Expunge failed: %s", response)
            return False
        return True

    # ------------------------------------------------------------------
    # Mailbox management
    # ------------------------------------------------------------------

    def list_mailboxes(self) -> list[str]:
        """List available mailboxes."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, mailboxes = self._mail.list()
        if status != "OK" or not mailboxes:
            return []

        folder_list: list[str] = []
        for item in mailboxes:
            if isinstance(item, bytes):
                decoded = item.decode("utf-8", errors="ignore")
                # IMAP LIST response format:
                # '(\\HasNoChildren) "/" "INBOX"'
                # Parse the mailbox name — it is the last quoted string.
                parts = decoded.split('"')
                if len(parts) >= 3:
                    folder_name = parts[-2]
                    folder_list.append(folder_name)
        return folder_list

    def create_mailbox(self, name: str) -> bool:
        """Create a new mailbox."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, response = self._mail.create(name)
        if status != "OK":
            logger.error("Failed to create mailbox '%s': %s", name, response)
            return False
        return True

    def delete_mailbox(self, name: str) -> bool:
        """Delete a mailbox."""
        assert self._mail is not None, "Not connected — use as context manager"
        status, response = self._mail.delete(name)
        if status != "OK":
            logger.error("Failed to delete mailbox '%s': %s", name, response)
            return False
        return True
