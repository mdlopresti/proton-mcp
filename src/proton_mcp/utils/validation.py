"""Input validation utilities."""


def validate_email_id(email_id: str) -> str:
    """Validate email ID is numeric (single or comma-separated list)."""
    raise NotImplementedError


def validate_folder_name(folder_name: str) -> str:
    """Validate folder name contains only safe characters."""
    raise NotImplementedError


def quote_mailbox(name: str) -> str:
    """Quote a mailbox name for IMAP commands per RFC 3501."""
    raise NotImplementedError
