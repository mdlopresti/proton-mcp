"""SMTP client for sending emails."""

from __future__ import annotations

import logging
import smtplib
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from typing import Any

from proton_mcp.config import Config

logger = logging.getLogger(__name__)


class SMTPClient:
    """SMTP client with STARTTLS support. Supports context manager."""

    def __init__(self, config: Config) -> None:
        self._config = config
        self._server: smtplib.SMTP | None = None

    def __enter__(self) -> SMTPClient:
        try:
            self._server = smtplib.SMTP(self._config.smtp_host, self._config.smtp_port)
            self._server.starttls()
            self._server.login(self._config.email, self._config.password)
            return self
        except Exception as e:
            logger.error(f"SMTP connection failed: {e}")
            raise

    def __exit__(self, *args: Any) -> None:
        if self._server is not None:
            try:
                self._server.quit()
            except smtplib.SMTPServerDisconnected:
                pass

    def send_email(self, to: str, subject: str, body: str, reply_to_id: str | None = None) -> bool:
        """Send an email. Returns True on success."""
        try:
            msg = MIMEMultipart()
            msg["From"] = self._config.email
            msg["To"] = to
            msg["Subject"] = subject

            if reply_to_id:
                msg["In-Reply-To"] = reply_to_id
                msg["References"] = reply_to_id

            msg.attach(MIMEText(body, "plain"))

            if self._server is None:
                raise smtplib.SMTPServerDisconnected("Not connected")

            self._server.send_message(msg)
            return True
        except Exception as e:
            logger.error(f"Failed to send email: {e}")
            return False
