"""Input validation utilities."""

import logging
import re

logger = logging.getLogger(__name__)


def validate_email_id(email_id: str) -> str:
    """Validate email ID is numeric (single or comma-separated list).

    Strips whitespace and verifies the format is one or more numeric IDs
    separated by commas (with optional whitespace around commas).

    Args:
        email_id: A string containing one or more numeric email IDs.

    Returns:
        The stripped, validated email ID string.

    Raises:
        ValueError: If the email ID format is invalid.
    """
    email_id = email_id.strip()
    if not re.match(r"^\d+(,\s*\d+)*$", email_id):
        raise ValueError(f"Invalid email ID format: {email_id}")
    return email_id


def validate_folder_name(folder_name: str) -> str:
    """Validate folder name contains only safe characters.

    Allows alphanumeric characters, spaces, hyphens, underscores, dots,
    and forward slashes (for nested folders). Blocks path traversal attempts.

    Args:
        folder_name: The folder name to validate.

    Returns:
        The stripped, validated folder name.

    Raises:
        ValueError: If the folder name is empty, contains unsafe characters,
                     or includes path traversal sequences.
    """
    folder_name = folder_name.strip()
    if not folder_name:
        raise ValueError("Folder name cannot be empty")
    # Allow alphanumeric, spaces, hyphens, underscores, dots, forward slashes (for nested folders)
    if not re.match(r"^[\w\s\-./]+$", folder_name):
        raise ValueError(f"Invalid folder name: {folder_name}")
    if ".." in folder_name:
        raise ValueError(f"Directory traversal not allowed in folder name: {folder_name}")
    return folder_name


def quote_mailbox(name: str) -> str:
    """Quote a mailbox name for IMAP commands per RFC 3501.

    If the name contains spaces or backslashes, wraps it in double quotes
    and escapes any internal backslashes and double quotes.

    Args:
        name: The mailbox name to quote.

    Returns:
        The quoted mailbox name string, or the original if quoting is not needed.
    """
    if " " in name or "\\" in name:
        escaped = name.replace("\\", "\\\\").replace('"', '\\"')
        return f'"{escaped}"'
    return name
