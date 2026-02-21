"""Filter rules service with persistent JSON storage."""

from __future__ import annotations

from typing import Any

from proton_mcp.config import Config
from proton_mcp.models.email import FilterRule


class FilterRuleEngine:
    """Email filter rule engine with JSON-backed persistence.

    Uses JsonStore for atomic rule persistence. Supports:
    - CRUD operations on rules
    - Rule matching against email data
    - Action execution (move, mark, delete) via IMAPClient
    - Rule statistics tracking
    """

    def __init__(self, config: Config) -> None:
        raise NotImplementedError

    def load_rules(self) -> list[FilterRule]:
        """Load all filter rules from JSON store."""
        raise NotImplementedError

    def save_rules(self, rules: list[FilterRule]) -> None:
        """Save all filter rules to JSON store."""
        raise NotImplementedError

    def create_rule(
        self,
        name: str,
        conditions: dict[str, Any],
        actions: dict[str, Any],
        enabled: bool = True,
    ) -> FilterRule:
        """Create a new filter rule. Raises ValueError on duplicate name or invalid conditions/actions."""
        raise NotImplementedError

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a filter rule by ID. Returns False if not found."""
        raise NotImplementedError

    def update_rule(self, rule_id: str, **updates: Any) -> bool:
        """Update an existing filter rule. Returns False if not found."""
        raise NotImplementedError

    def get_rule(self, rule_id: str) -> FilterRule | None:
        """Get a single rule by ID."""
        raise NotImplementedError

    def email_matches_rule(self, email_data: dict[str, Any], rule: FilterRule) -> bool:
        """Check if an email matches a rule's conditions."""
        raise NotImplementedError

    @staticmethod
    def valid_conditions() -> list[str]:
        """Return list of valid condition keys."""
        return [
            "from", "to", "subject_contains", "subject_equals",
            "body_contains", "sender_domain", "has_attachments",
            "older_than_days", "newer_than_days",
        ]

    @staticmethod
    def valid_actions() -> list[str]:
        """Return list of valid action keys."""
        return [
            "move_to_folder", "mark_as_read", "mark_as_important",
            "delete", "forward_to", "auto_reply",
        ]
