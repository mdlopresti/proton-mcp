"""Unsubscribe detection and execution service with persistent configuration."""

from __future__ import annotations

from typing import Any

from proton_mcp.config import Config
from proton_mcp.models.email import (
    DetectionPattern,
    UnsubscribeHistoryEntry,
    UnsubscribeMethod,
    UnsubscribePreference,
)


class UnsubscribeService:
    """Unsubscribe detection and execution with persistent config.

    Uses JsonStore for config persistence. Supports:
    - RFC 2369 List-Unsubscribe header parsing
    - RFC 8058 One-Click unsubscribe
    - HTML body link detection (including tracker-wrapped URLs)
    - Text body pattern matching
    - Sender preferences (always/never unsubscribe)
    - Detection patterns (configurable tracker domains)
    - History logging of unsubscribe attempts
    """

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def load_config(self) -> dict[str, Any]:
        """Load unsubscribe config from JSON store."""
        raise NotImplementedError

    def save_config(self, config_data: dict[str, Any]) -> None:
        """Save unsubscribe config to JSON store."""
        raise NotImplementedError

    def find_unsubscribe_links(self, email_data: dict[str, Any]) -> list[UnsubscribeMethod]:
        """Find all unsubscribe methods in an email.

        Checks: RFC 2369 headers, RFC 8058 one-click, HTML body, text body.
        Deduplicates results.
        """
        raise NotImplementedError

    def execute_unsubscribe(self, method: UnsubscribeMethod) -> bool:
        """Execute an unsubscribe action. Logs attempt to history.

        Supports HTTP GET/POST and one-click unsubscribe.
        Uses url_safety for SSRF protection.
        """
        raise NotImplementedError

    def get_sender_preference(self, sender: str) -> UnsubscribePreference | None:
        """Get unsubscribe preference for a sender/domain."""
        raise NotImplementedError

    def add_sender_preference(self, sender: str, action: str, domain: str = "") -> bool:
        """Add a sender preference (always_unsubscribe or never_unsubscribe)."""
        raise NotImplementedError

    def remove_sender_preference(self, sender: str) -> bool:
        """Remove a sender preference."""
        raise NotImplementedError

    def add_detection_pattern(
        self, name: str, pattern: str, pattern_type: str = "tracker_domain", enabled: bool = True
    ) -> DetectionPattern:
        """Add a detection pattern for tracker URLs."""
        raise NotImplementedError

    def remove_detection_pattern(self, pattern_id: str) -> bool:
        """Remove a detection pattern by ID."""
        raise NotImplementedError

    def get_history(self) -> list[UnsubscribeHistoryEntry]:
        """Get unsubscribe attempt history."""
        raise NotImplementedError

    def log_attempt(self, sender: str, method: str, url: str, success: bool) -> None:
        """Log an unsubscribe attempt to history."""
        raise NotImplementedError

    def check_resubscribe(self, sender: str) -> bool:
        """Check if a sender in history is still sending (re-subscribed)."""
        raise NotImplementedError
