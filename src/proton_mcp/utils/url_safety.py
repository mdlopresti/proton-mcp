"""URL safety validation for SSRF protection."""

import ipaddress
import logging
from urllib.parse import urlparse

logger = logging.getLogger(__name__)


def is_safe_url(url: str) -> bool:
    """Validate that a URL is safe to request (not targeting internal/private networks).

    Checks for:
    - Only ``http`` and ``https`` schemes are allowed.
    - Blocks ``localhost`` and ``localhost.localdomain`` hostnames.
    - Blocks loopback, private, link-local, and reserved IP addresses.

    Args:
        url: The URL string to validate.

    Returns:
        ``True`` if the URL appears safe for outbound requests, ``False`` otherwise.
    """
    try:
        parsed = urlparse(url)
    except Exception:
        return False

    # Only allow http and https schemes
    if parsed.scheme not in ("http", "https"):
        logger.warning("Blocked URL with non-HTTP scheme: %s", parsed.scheme)
        return False

    hostname = parsed.hostname
    if not hostname:
        return False

    # Reject localhost variants
    if hostname in ("localhost", "localhost.localdomain"):
        logger.warning("Blocked request to localhost: %s", url)
        return False

    # Check if hostname is an IP address and validate it
    try:
        addr = ipaddress.ip_address(hostname)
        if addr.is_loopback:
            logger.warning("Blocked request to loopback address: %s", url)
            return False
        if addr.is_private:
            logger.warning("Blocked request to private IP range: %s", url)
            return False
        if addr.is_link_local:
            logger.warning("Blocked request to link-local address: %s", url)
            return False
        if addr.is_reserved:
            logger.warning("Blocked request to reserved address: %s", url)
            return False
    except ValueError:
        # Not an IP address, it's a hostname string - allow it but log
        logger.debug("URL uses hostname (not IP): %s", hostname)

    return True
