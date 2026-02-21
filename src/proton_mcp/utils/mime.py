"""MIME parsing and email body extraction utilities."""

from email.message import Message


def decode_mime_words(text: str) -> str:
    """Decode MIME encoded words (RFC 2047)."""
    raise NotImplementedError


def get_email_body(msg: Message) -> str:
    """Extract plain text body from an email message."""
    raise NotImplementedError


def get_html_body(msg: Message) -> str:
    """Extract HTML body from an email message."""
    raise NotImplementedError


def get_text_and_html(msg: Message) -> tuple[str, str]:
    """Extract both plain text and HTML body from an email message."""
    raise NotImplementedError
