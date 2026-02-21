"""Junk email detection service with persistent configuration."""

from __future__ import annotations

from typing import Any

from proton_mcp.config import Config
from proton_mcp.models.email import JunkAnalysis, JunkConfig, JunkRule


class JunkDetector:
    """Junk email detection engine with persistent JSON-backed configuration.

    Uses JsonStore for atomic config persistence. Supports:
    - Built-in hardcoded patterns (default scoring)
    - Custom user patterns (JunkRule)
    - Whitelist (domains/senders) checked FIRST — skips scoring
    - Blacklist (domains/senders) auto-scores high
    - Configurable thresholds
    """

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def load_config(self) -> JunkConfig:
        """Load junk config from JSON store. Creates default if missing."""
        raise NotImplementedError

    def save_config(self, junk_config: JunkConfig) -> None:
        """Save junk config to JSON store."""
        raise NotImplementedError

    def analyze_email(self, email_data: dict[str, Any]) -> JunkAnalysis:
        """Analyze a single email for junk indicators.

        Checks whitelist first (returns clean if match).
        Checks blacklist (auto-scores high if match).
        Applies built-in + custom patterns.
        Returns JunkAnalysis model.
        """
        raise NotImplementedError

    def is_whitelisted(self, sender: str) -> bool:
        """Check if sender or sender domain is whitelisted."""
        raise NotImplementedError

    def is_blacklisted(self, sender: str) -> bool:
        """Check if sender or sender domain is blacklisted."""
        raise NotImplementedError

    def add_whitelist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Add a domain or sender to the whitelist."""
        raise NotImplementedError

    def remove_whitelist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Remove a domain or sender from the whitelist."""
        raise NotImplementedError

    def add_blacklist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Add a domain or sender to the blacklist."""
        raise NotImplementedError

    def remove_blacklist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Remove a domain or sender from the blacklist."""
        raise NotImplementedError

    def create_rule(self, name: str, field: str, pattern: str, score: int = 2, enabled: bool = True) -> JunkRule:
        """Create a custom junk detection rule."""
        raise NotImplementedError

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a custom junk detection rule by ID."""
        raise NotImplementedError

    def update_rule(self, rule_id: str, **updates: Any) -> bool:
        """Update a custom junk detection rule."""
        raise NotImplementedError
