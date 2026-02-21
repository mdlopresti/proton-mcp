"""URL safety validation for SSRF protection."""


def is_safe_url(url: str) -> bool:
    """Validate that a URL is safe to request (not targeting internal/private networks)."""
    raise NotImplementedError
