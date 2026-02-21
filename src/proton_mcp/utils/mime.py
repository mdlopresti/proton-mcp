"""MIME parsing and email body extraction utilities."""

import logging
from email.header import decode_header
from email.message import Message

logger = logging.getLogger(__name__)


def decode_mime_words(text: str) -> str:
    """Decode MIME encoded words (RFC 2047).

    Handles encoded headers like ``=?UTF-8?B?...?=`` and returns a plain
    Unicode string.

    Args:
        text: The raw header text, possibly containing encoded words.
              If *None* is passed the function returns an empty string.

    Returns:
        The decoded Unicode string.
    """
    if text is None:
        return ""
    decoded_words = decode_header(text)
    decoded_text = ""
    for word, encoding in decoded_words:
        if isinstance(word, bytes):
            word = word.decode(encoding or "utf-8", errors="ignore")
        decoded_text += word
    return decoded_text


def get_email_body(msg: Message) -> str:
    """Extract plain text body from an email message.

    For multipart messages, walks parts and returns the first ``text/plain``
    part that is not an attachment. For single-part messages, decodes the
    payload directly.

    Args:
        msg: An :class:`email.message.Message` instance.

    Returns:
        The plain text body, or an empty string if none is found.
    """
    body = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/plain" and "attachment" not in content_disposition:
                try:
                    raw = part.get_payload(decode=True)
                    body = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else ""
                    break
                except Exception:
                    continue
    else:
        try:
            raw = msg.get_payload(decode=True)
            body = raw.decode("utf-8", errors="ignore") if isinstance(raw, bytes) else ""
        except Exception:
            body = str(msg.get_payload())

    return body


def get_html_body(msg: Message) -> str:
    """Extract HTML body from an email message.

    For multipart messages, walks parts and concatenates all ``text/html``
    parts that are not attachments. For single-part ``text/html`` messages,
    decodes the payload directly.

    Args:
        msg: An :class:`email.message.Message` instance.

    Returns:
        The HTML body content, or an empty string if none is found.
    """
    html_content = ""
    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if content_type == "text/html" and "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        html_content += payload.decode("utf-8", errors="ignore")
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes) and msg.get_content_type() == "text/html":
                html_content = payload.decode("utf-8", errors="ignore")
        except Exception:
            pass

    return html_content


def get_text_and_html(msg: Message) -> tuple[str, str]:
    """Extract both plain text and HTML body from an email message.

    For multipart messages, walks all parts and collects both ``text/plain``
    and ``text/html`` content (skipping attachments). For single-part messages,
    places the content in the appropriate slot based on its content type.

    Args:
        msg: An :class:`email.message.Message` instance.

    Returns:
        A ``(text_content, html_content)`` tuple. Either value may be an
        empty string if the corresponding content type is not present.
    """
    text_content = ""
    html_content = ""

    if msg.is_multipart():
        for part in msg.walk():
            content_type = part.get_content_type()
            content_disposition = str(part.get("Content-Disposition"))

            if "attachment" not in content_disposition:
                try:
                    payload = part.get_payload(decode=True)
                    if isinstance(payload, bytes):
                        content = payload.decode("utf-8", errors="ignore")
                        if content_type == "text/plain":
                            text_content += content
                        elif content_type == "text/html":
                            html_content += content
                except Exception:
                    continue
    else:
        try:
            payload = msg.get_payload(decode=True)
            if isinstance(payload, bytes):
                content = payload.decode("utf-8", errors="ignore")
                if msg.get_content_type() == "text/html":
                    html_content = content
                else:
                    text_content = content
        except Exception:
            pass

    return text_content, html_content
