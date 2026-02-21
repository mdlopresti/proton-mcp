"""Filter rules service with persistent JSON storage."""

from __future__ import annotations

import logging
import os
import uuid
from datetime import UTC, datetime
from typing import Any

from proton_mcp.config import Config
from proton_mcp.models.email import FilterRule
from proton_mcp.utils.json_store import JsonStore

logger = logging.getLogger(__name__)


class FilterRuleEngine:
    """Email filter rule engine with JSON-backed persistence.

    Uses JsonStore for atomic rule persistence. Supports:
    - CRUD operations on rules
    - Rule matching against email data
    - Action execution (move, mark, delete) via IMAPClient
    - Rule statistics tracking
    """

    def __init__(self, config: Config) -> None:
        rules_path = os.path.join(config.data_dir, "filter_rules.json")
        self._store = JsonStore(
            file_path=rules_path,
            schema_version=1,
            default_data={"rules": []},
        )
        self._rules: list[FilterRule] = self.load_rules()

    def load_rules(self) -> list[FilterRule]:
        """Load all filter rules from JSON store."""
        data = self._store.load()
        raw_rules = data.get("rules", [])
        self._rules = [FilterRule.from_dict(r) for r in raw_rules]
        return list(self._rules)

    def save_rules(self, rules: list[FilterRule]) -> None:
        """Save all filter rules to JSON store."""
        self._rules = list(rules)
        data = {"rules": [rule.to_dict() for rule in self._rules]}
        self._store.save(data)

    def create_rule(
        self,
        name: str,
        conditions: dict[str, Any],
        actions: dict[str, Any],
        enabled: bool = True,
    ) -> FilterRule:
        """Create a new filter rule. Raises ValueError on duplicate name or invalid conditions/actions."""
        # Check for duplicate name
        if any(rule.name == name for rule in self._rules):
            raise ValueError(f"Rule with name '{name}' already exists")

        # Validate conditions
        valid_conds = self.valid_conditions()
        for condition in conditions:
            if condition not in valid_conds:
                raise ValueError(f"Invalid condition: {condition}")

        # Validate actions
        valid_acts = self.valid_actions()
        for action in actions:
            if action not in valid_acts:
                raise ValueError(f"Invalid action: {action}")

        rule = FilterRule(
            id=str(uuid.uuid4()),
            name=name,
            conditions=dict(conditions),
            actions=dict(actions),
            enabled=enabled,
            created_at=datetime.now(tz=UTC).isoformat(),
            last_applied=None,
            emails_processed=0,
        )

        self._rules.append(rule)
        self.save_rules(self._rules)
        return rule

    def delete_rule(self, rule_id: str) -> bool:
        """Delete a filter rule by ID. Returns False if not found."""
        updated = [r for r in self._rules if r.id != rule_id]
        if len(updated) == len(self._rules):
            logger.error("Rule with ID '%s' not found", rule_id)
            return False
        self.save_rules(updated)
        return True

    def update_rule(self, rule_id: str, **updates: Any) -> bool:
        """Update an existing filter rule. Returns False if not found."""
        for rule in self._rules:
            if rule.id == rule_id:
                for key, value in updates.items():
                    if hasattr(rule, key):
                        setattr(rule, key, value)
                self.save_rules(self._rules)
                return True

        logger.error("Rule with ID '%s' not found", rule_id)
        return False

    def get_rule(self, rule_id: str) -> FilterRule | None:
        """Get a single rule by ID."""
        for rule in self._rules:
            if rule.id == rule_id:
                return rule
        return None

    def email_matches_rule(self, email_data: dict[str, Any], rule: FilterRule) -> bool:
        """Check if an email matches a rule's conditions.

        All conditions must match (AND logic). Matching is case-insensitive
        for string comparisons.
        """
        conditions = rule.conditions

        for condition, value in conditions.items():
            if condition == "from":
                sender = email_data.get("from", "")
                if value.lower() not in sender.lower():
                    return False

            elif condition == "to":
                recipient = email_data.get("to", "")
                if value.lower() not in recipient.lower():
                    return False

            elif condition == "subject_contains":
                subject = email_data.get("subject", "")
                if value.lower() not in subject.lower():
                    return False

            elif condition == "subject_equals":
                subject = email_data.get("subject", "")
                if value.lower() != subject.lower():
                    return False

            elif condition == "body_contains":
                body = email_data.get("body", "")
                if value.lower() not in body.lower():
                    return False

            elif condition == "sender_domain":
                sender = email_data.get("from", "")
                domain = sender.split("@")[-1] if "@" in sender else ""
                if value.lower() != domain.lower():
                    return False

            elif condition == "has_attachments":
                has_attach = email_data.get("has_attachments", False)
                if bool(value) != bool(has_attach):
                    return False

            elif condition == "older_than_days":
                email_date_str = email_data.get("date", "")
                if not email_date_str:
                    return False
                try:
                    email_date = datetime.fromisoformat(email_date_str)
                    if email_date.tzinfo is None:
                        email_date = email_date.replace(tzinfo=UTC)
                    age_days = (datetime.now(tz=UTC) - email_date).days
                    if age_days < int(value):
                        return False
                except (ValueError, TypeError):
                    logger.warning("Could not parse date '%s' for older_than_days", email_date_str)
                    return False

            elif condition == "newer_than_days":
                email_date_str = email_data.get("date", "")
                if not email_date_str:
                    return False
                try:
                    email_date = datetime.fromisoformat(email_date_str)
                    if email_date.tzinfo is None:
                        email_date = email_date.replace(tzinfo=UTC)
                    age_days = (datetime.now(tz=UTC) - email_date).days
                    if age_days > int(value):
                        return False
                except (ValueError, TypeError):
                    logger.warning("Could not parse date '%s' for newer_than_days", email_date_str)
                    return False

        return True

    @staticmethod
    def valid_conditions() -> list[str]:
        """Return list of valid condition keys."""
        return [
            "from",
            "to",
            "subject_contains",
            "subject_equals",
            "body_contains",
            "sender_domain",
            "has_attachments",
            "older_than_days",
            "newer_than_days",
        ]

    @staticmethod
    def valid_actions() -> list[str]:
        """Return list of valid action keys."""
        return [
            "move_to_folder",
            "mark_as_read",
            "mark_as_important",
            "delete",
            "forward_to",
            "auto_reply",
        ]
