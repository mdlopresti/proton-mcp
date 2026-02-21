"""SMTP client for sending emails."""

from __future__ import annotations

from typing import Any

from proton_mcp.config import Config


class SMTPClient:
    """SMTP client with STARTTLS support. Supports context manager."""

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def __enter__(self) -> SMTPClient:
        raise NotImplementedError

    def __exit__(self, *args: Any) -> None:
        raise NotImplementedError

    def send_email(self, to: str, subject: str, body: str, reply_to_id: str | None = None) -> bool:
        """Send an email. Returns True on success."""
        raise NotImplementedError
