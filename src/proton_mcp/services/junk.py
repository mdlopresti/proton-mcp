"""Junk email detection service with persistent configuration."""

from __future__ import annotations

import copy
import logging
import os
import re
import uuid
from typing import Any

from proton_mcp.config import Config
from proton_mcp.models.email import JunkAnalysis, JunkConfig, JunkRule
from proton_mcp.utils.json_store import JsonStore

logger = logging.getLogger(__name__)

# Built-in spam subject patterns (case-insensitive matching against lowered subject)
_SUBJECT_PATTERNS: list[tuple[str, int]] = [
    (r"urgent.*action.*required", 2),
    (r"congratulations.*won", 2),
    (r"free.*money|money.*free", 2),
    (r"limited.*time.*offer", 2),
    (r"act.*now", 2),
    (r"viagra|cialis|pharmacy", 2),
    (r"increase.*size", 2),
    (r"lose.*weight.*fast", 2),
    (r"make.*money.*fast", 2),
    (r"nigerian.*prince", 2),
    (r"tax.*refund", 2),
    (r"security.*alert", 2),
    # NOTE: "re:.*re:.*re:" pattern REMOVED — long reply chains are normal (BUG FIX)
]

# Built-in suspicious sender patterns (case-insensitive matching against lowered from_addr)
# NOTE: admin@.* and support@.* REMOVED — legitimate services use these (BUG FIX)
_SENDER_PATTERNS: list[tuple[str, int]] = [
    (r"noreply@.*\.tk$", 1),
    (r".*@.*\.ml$", 1),
    (r".*@.*\.ga$", 1),
    (r"security@.*", 1),
]

# Built-in spam body patterns (case-insensitive matching against lowered body)
_BODY_PATTERNS: list[tuple[str, int]] = [
    (r"click.*here.*now", 2),
    (r"urgent.*respond", 2),
    (r"verify.*account.*immediately", 2),
    (r"suspended.*account", 2),
    (r"winner.*lottery", 2),
    (r"inheritance.*million", 2),
    (r"bitcoin.*investment", 2),
    (r"crypto.*opportunity", 2),
]

# Exclamation mark threshold — raised from 3 to 10 (BUG FIX)
_EXCLAMATION_THRESHOLD = 10

# Default config data for JsonStore initialisation
_DEFAULT_CONFIG_DATA: dict[str, Any] = {
    "custom_patterns": [],
    "whitelist": {"domains": [], "senders": []},
    "blacklist": {"domains": [], "senders": []},
    "thresholds": {"low": 1, "medium": 2, "high": 4},
}


def _extract_domain(email_address: str) -> str:
    """Extract the domain from an email address, handling display-name formats."""
    # Handle "Name <user@domain>" format
    if "<" in email_address and ">" in email_address:
        email_address = email_address.split("<")[1].split(">")[0]
    parts = email_address.strip().lower().split("@")
    return parts[1] if len(parts) == 2 else ""


def _extract_bare_email(email_address: str) -> str:
    """Extract bare email from possible display-name format."""
    if "<" in email_address and ">" in email_address:
        return email_address.split("<")[1].split(">")[0].strip().lower()
    return email_address.strip().lower()


class JunkDetector:
    """Junk email detection engine with persistent JSON-backed configuration.

    Uses JsonStore for atomic config persistence. Supports:
    - Built-in hardcoded patterns (default scoring)
    - Custom user patterns (JunkRule)
    - Whitelist (domains/senders) checked FIRST -- skips scoring
    - Blacklist (domains/senders) auto-scores high
    - Configurable thresholds
    """

    def __init__(self, config: Config) -> None:
        config_path = os.path.join(config.data_dir, "junk_config.json")
        self._store = JsonStore(
            file_path=config_path,
            schema_version=1,
            default_data=copy.deepcopy(_DEFAULT_CONFIG_DATA),
        )
        self._config: JunkConfig = self.load_config()

    def load_config(self) -> JunkConfig:
        """Load junk config from JSON store. Creates default if missing."""
        data = self._store.load()
        self._config = JunkConfig.from_dict(data)
        return self._config

    def save_config(self, junk_config: JunkConfig) -> None:
        """Save junk config to JSON store."""
        self._config = junk_config
        self._store.save(junk_config.to_dict())

    def analyze_email(self, email_data: dict[str, Any]) -> JunkAnalysis:
        """Analyze a single email for junk indicators.

        Checks whitelist first (returns clean if match).
        Checks blacklist (auto-scores high if match).
        Applies built-in + custom patterns.
        Returns JunkAnalysis model.
        """
        raw_subject = email_data.get("subject", "")
        subject = raw_subject.lower()
        from_addr = email_data.get("from", "").lower()
        body = email_data.get("body", "").lower()
        email_id = str(email_data.get("id", ""))

        # --- Whitelist check (FIRST) ---
        if from_addr and self.is_whitelisted(from_addr):
            return JunkAnalysis(
                is_likely_junk=False,
                junk_score=0,
                likelihood="unlikely",
                indicators=[],
                email_id=email_id,
            )

        junk_score = 0
        indicators: list[str] = []

        # --- Blacklist check ---
        if from_addr and self.is_blacklisted(from_addr):
            junk_score = 10
            indicators.append("Sender/domain is blacklisted")
            return JunkAnalysis(
                is_likely_junk=True,
                junk_score=junk_score,
                likelihood="high",
                indicators=indicators,
                email_id=email_id,
            )

        # --- Built-in subject patterns ---
        for pattern, score in _SUBJECT_PATTERNS:
            if re.search(pattern, subject):
                indicators.append(f"Suspicious subject pattern: {pattern}")
                junk_score += score

        # --- Built-in sender patterns ---
        for pattern, score in _SENDER_PATTERNS:
            if re.search(pattern, from_addr):
                indicators.append(f"Suspicious sender pattern: {pattern}")
                junk_score += score

        # --- Built-in body patterns ---
        for pattern, score in _BODY_PATTERNS:
            if re.search(pattern, body):
                indicators.append(f"Suspicious body content: {pattern}")
                junk_score += score

        # --- Excessive caps in subject (checked against original case) ---
        if len(raw_subject) > 10:
            caps_ratio = sum(1 for c in raw_subject if c.isupper()) / len(raw_subject)
            if caps_ratio > 0.5:
                indicators.append("Excessive capital letters in subject")
                junk_score += 1

        # --- Excessive exclamation marks (threshold raised to 10) ---
        exclamation_count = subject.count("!") + body[:500].count("!")
        if exclamation_count > _EXCLAMATION_THRESHOLD:
            indicators.append(f"Excessive exclamation marks ({exclamation_count})")
            junk_score += 1

        # --- Custom patterns from config ---
        for rule in self._config.custom_patterns:
            if not rule.enabled:
                continue
            target = ""
            if rule.field == "subject":
                target = subject
            elif rule.field == "sender":
                target = from_addr
            elif rule.field == "body":
                target = body
            else:
                continue

            try:
                if re.search(rule.pattern, target):
                    indicators.append(f"Custom rule '{rule.name}': {rule.pattern}")
                    junk_score += rule.score
            except re.error:
                logger.warning("Invalid regex in custom rule '%s': %s", rule.name, rule.pattern)

        # --- Determine likelihood from configurable thresholds ---
        thresholds = self._config.thresholds
        high_t = thresholds.get("high", 4)
        medium_t = thresholds.get("medium", 2)
        low_t = thresholds.get("low", 1)

        if junk_score >= high_t:
            likelihood = "high"
        elif junk_score >= medium_t:
            likelihood = "medium"
        elif junk_score >= low_t:
            likelihood = "low"
        else:
            likelihood = "unlikely"

        return JunkAnalysis(
            is_likely_junk=junk_score >= medium_t,
            junk_score=junk_score,
            likelihood=likelihood,
            indicators=indicators,
            email_id=email_id,
        )

    # ------------------------------------------------------------------
    # Whitelist / Blacklist queries
    # ------------------------------------------------------------------

    def is_whitelisted(self, sender: str) -> bool:
        """Check if sender or sender domain is whitelisted."""
        bare = _extract_bare_email(sender)
        domain = _extract_domain(sender)

        wl = self._config.whitelist
        wl_senders = [s.lower() for s in wl.get("senders", [])]
        wl_domains = [d.lower() for d in wl.get("domains", [])]

        if bare in wl_senders:
            return True
        if domain and domain in wl_domains:
            return True
        return False

    def is_blacklisted(self, sender: str) -> bool:
        """Check if sender or sender domain is blacklisted."""
        bare = _extract_bare_email(sender)
        domain = _extract_domain(sender)

        bl = self._config.blacklist
        bl_senders = [s.lower() for s in bl.get("senders", [])]
        bl_domains = [d.lower() for d in bl.get("domains", [])]

        if bare in bl_senders:
            return True
        if domain and domain in bl_domains:
            return True
        return False

    # ------------------------------------------------------------------
    # Whitelist CRUD
    # ------------------------------------------------------------------

    def add_whitelist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Add a domain or sender to the whitelist.

        Args:
            entry: The domain or email address to whitelist.
            entry_type: Either ``"domain"`` or ``"sender"``.

        Returns:
            True if the entry was added, False if it already existed.
        """
        key = "domains" if entry_type == "domain" else "senders"
        entry_lower = entry.lower()

        if entry_lower in [e.lower() for e in self._config.whitelist.get(key, [])]:
            return False

        self._config.whitelist.setdefault(key, []).append(entry_lower)
        self.save_config(self._config)
        return True

    def remove_whitelist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Remove a domain or sender from the whitelist.

        Returns:
            True if the entry was removed, False if it was not found.
        """
        key = "domains" if entry_type == "domain" else "senders"
        entry_lower = entry.lower()

        items = self._config.whitelist.get(key, [])
        new_items = [e for e in items if e.lower() != entry_lower]
        if len(new_items) == len(items):
            return False

        self._config.whitelist[key] = new_items
        self.save_config(self._config)
        return True

    # ------------------------------------------------------------------
    # Blacklist CRUD
    # ------------------------------------------------------------------

    def add_blacklist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Add a domain or sender to the blacklist.

        Returns:
            True if the entry was added, False if it already existed.
        """
        key = "domains" if entry_type == "domain" else "senders"
        entry_lower = entry.lower()

        if entry_lower in [e.lower() for e in self._config.blacklist.get(key, [])]:
            return False

        self._config.blacklist.setdefault(key, []).append(entry_lower)
        self.save_config(self._config)
        return True

    def remove_blacklist_entry(self, entry: str, entry_type: str = "domain") -> bool:
        """Remove a domain or sender from the blacklist.

        Returns:
            True if the entry was removed, False if it was not found.
        """
        key = "domains" if entry_type == "domain" else "senders"
        entry_lower = entry.lower()

        items = self._config.blacklist.get(key, [])
        new_items = [e for e in items if e.lower() != entry_lower]
        if len(new_items) == len(items):
            return False

        self._config.blacklist[key] = new_items
        self.save_config(self._config)
        return True

    # ------------------------------------------------------------------
    # Custom Rule CRUD
    # ------------------------------------------------------------------

    def create_rule(self, name: str, field: str, pattern: str, score: int = 2, enabled: bool = True) -> JunkRule:
        """Create a custom junk detection rule.

        Args:
            name: Human-readable rule name.
            field: Field to match against (``"subject"``, ``"sender"``, ``"body"``).
            pattern: Regular expression pattern.
            score: Points to add when matched.
            enabled: Whether the rule is active.

        Returns:
            The newly created JunkRule.
        """
        rule_id = str(uuid.uuid4())
        rule = JunkRule(
            id=rule_id,
            name=name,
            field=field,
            pattern=pattern,
            score=score,
            enabled=enabled,
        )
        self._config.custom_patterns.append(rule)
        self.save_config(self._config)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a custom junk detection rule by ID.

        Returns:
            True if the rule was found and deleted, False otherwise.
        """
        original_len = len(self._config.custom_patterns)
        self._config.custom_patterns = [r for r in self._config.custom_patterns if r.id != rule_id]
        if len(self._config.custom_patterns) == original_len:
            return False

        self.save_config(self._config)
        return True

    def update_rule(self, rule_id: str, **updates: Any) -> bool:
        """Update a custom junk detection rule.

        Supported keyword arguments: ``name``, ``field``, ``pattern``,
        ``score``, ``enabled``.

        Returns:
            True if the rule was found and updated, False otherwise.
        """
        allowed_fields = {"name", "field", "pattern", "score", "enabled"}
        for rule in self._config.custom_patterns:
            if rule.id == rule_id:
                for key, value in updates.items():
                    if key in allowed_fields:
                        setattr(rule, key, value)
                self.save_config(self._config)
                return True
        return False
