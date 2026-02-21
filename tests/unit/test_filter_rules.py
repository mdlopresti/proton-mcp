"""Tests for proton_mcp.services.filter_rules module."""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone

import pytest

from proton_mcp.models.email import FilterRule
from proton_mcp.services.filter_rules import FilterRuleEngine


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def engine(mock_config):
    """Create a FilterRuleEngine with a temporary data directory."""
    return FilterRuleEngine(mock_config)


@pytest.fixture
def sample_conditions():
    """Valid conditions dict for rule creation."""
    return {"from": "sender@example.com", "subject_contains": "newsletter"}


@pytest.fixture
def sample_actions():
    """Valid actions dict for rule creation."""
    return {"move_to_folder": "Newsletter", "mark_as_read": True}


@pytest.fixture
def engine_with_rule(engine, sample_conditions, sample_actions):
    """Engine that already has one rule created."""
    rule = engine.create_rule("Test Rule", sample_conditions, sample_actions)
    return engine, rule


@pytest.fixture
def sample_email():
    """Sample email data dict for matching tests."""
    return {
        "from": "sender@example.com",
        "to": "me@proton.me",
        "subject": "Monthly Newsletter Update",
        "body": "Here is your monthly newsletter with great content.",
        "date": datetime.now(tz=timezone.utc).isoformat(),
    }


# ---------------------------------------------------------------------------
# CRUD: Create
# ---------------------------------------------------------------------------


class TestCreateRule:
    def test_create_rule_returns_filter_rule(self, engine, sample_conditions, sample_actions):
        rule = engine.create_rule("My Rule", sample_conditions, sample_actions)
        assert isinstance(rule, FilterRule)
        assert rule.name == "My Rule"
        assert rule.conditions == sample_conditions
        assert rule.actions == sample_actions
        assert rule.enabled is True

    def test_create_rule_generates_uuid(self, engine, sample_conditions, sample_actions):
        rule = engine.create_rule("UUID Rule", sample_conditions, sample_actions)
        assert rule.id is not None
        assert len(rule.id) == 36  # UUID format: 8-4-4-4-12

    def test_create_rule_sets_created_at(self, engine, sample_conditions, sample_actions):
        rule = engine.create_rule("Dated Rule", sample_conditions, sample_actions)
        assert rule.created_at != ""
        # Should be parseable as ISO datetime
        dt = datetime.fromisoformat(rule.created_at)
        assert dt is not None

    def test_create_rule_initializes_stats(self, engine, sample_conditions, sample_actions):
        rule = engine.create_rule("Stats Rule", sample_conditions, sample_actions)
        assert rule.last_applied is None
        assert rule.emails_processed == 0

    def test_create_rule_disabled(self, engine, sample_conditions, sample_actions):
        rule = engine.create_rule("Disabled Rule", sample_conditions, sample_actions, enabled=False)
        assert rule.enabled is False

    def test_create_rule_rejects_duplicate_name(self, engine, sample_conditions, sample_actions):
        engine.create_rule("Unique Name", sample_conditions, sample_actions)
        with pytest.raises(ValueError, match="already exists"):
            engine.create_rule("Unique Name", {"from": "other@test.com"}, {"delete": True})

    def test_create_rule_rejects_invalid_condition(self, engine, sample_actions):
        with pytest.raises(ValueError, match="Invalid condition"):
            engine.create_rule("Bad Cond", {"invalid_field": "value"}, sample_actions)

    def test_create_rule_rejects_invalid_action(self, engine, sample_conditions):
        with pytest.raises(ValueError, match="Invalid action"):
            engine.create_rule("Bad Action", sample_conditions, {"explode": True})

    def test_create_rule_with_empty_conditions(self, engine, sample_actions):
        rule = engine.create_rule("Empty Conds", {}, sample_actions)
        assert rule.conditions == {}

    def test_create_rule_with_empty_actions(self, engine, sample_conditions):
        rule = engine.create_rule("Empty Actions", sample_conditions, {})
        assert rule.actions == {}

    def test_create_multiple_rules(self, engine, sample_actions):
        engine.create_rule("Rule A", {"from": "a@test.com"}, sample_actions)
        engine.create_rule("Rule B", {"from": "b@test.com"}, sample_actions)
        rules = engine.load_rules()
        assert len(rules) == 2


# ---------------------------------------------------------------------------
# CRUD: Delete
# ---------------------------------------------------------------------------


class TestDeleteRule:
    def test_delete_existing_rule(self, engine_with_rule):
        engine, rule = engine_with_rule
        assert engine.delete_rule(rule.id) is True
        assert engine.get_rule(rule.id) is None

    def test_delete_nonexistent_rule(self, engine):
        assert engine.delete_rule("nonexistent-id") is False

    def test_delete_only_removes_target(self, engine, sample_actions):
        rule_a = engine.create_rule("A", {"from": "a@test.com"}, sample_actions)
        rule_b = engine.create_rule("B", {"from": "b@test.com"}, sample_actions)
        engine.delete_rule(rule_a.id)
        assert engine.get_rule(rule_a.id) is None
        assert engine.get_rule(rule_b.id) is not None


# ---------------------------------------------------------------------------
# CRUD: Update
# ---------------------------------------------------------------------------


class TestUpdateRule:
    def test_update_existing_rule(self, engine_with_rule):
        engine, rule = engine_with_rule
        assert engine.update_rule(rule.id, name="Updated Name") is True
        updated = engine.get_rule(rule.id)
        assert updated.name == "Updated Name"

    def test_update_nonexistent_rule(self, engine):
        assert engine.update_rule("nonexistent-id", name="Nope") is False

    def test_update_enabled_flag(self, engine_with_rule):
        engine, rule = engine_with_rule
        engine.update_rule(rule.id, enabled=False)
        updated = engine.get_rule(rule.id)
        assert updated.enabled is False

    def test_update_conditions(self, engine_with_rule):
        engine, rule = engine_with_rule
        new_conds = {"subject_equals": "Important"}
        engine.update_rule(rule.id, conditions=new_conds)
        updated = engine.get_rule(rule.id)
        assert updated.conditions == new_conds

    def test_update_actions(self, engine_with_rule):
        engine, rule = engine_with_rule
        new_actions = {"delete": True}
        engine.update_rule(rule.id, actions=new_actions)
        updated = engine.get_rule(rule.id)
        assert updated.actions == new_actions

    def test_update_multiple_fields(self, engine_with_rule):
        engine, rule = engine_with_rule
        engine.update_rule(rule.id, name="New Name", enabled=False)
        updated = engine.get_rule(rule.id)
        assert updated.name == "New Name"
        assert updated.enabled is False


# ---------------------------------------------------------------------------
# CRUD: Get
# ---------------------------------------------------------------------------


class TestGetRule:
    def test_get_existing_rule(self, engine_with_rule):
        engine, rule = engine_with_rule
        found = engine.get_rule(rule.id)
        assert found is not None
        assert found.id == rule.id
        assert found.name == rule.name

    def test_get_nonexistent_rule(self, engine):
        assert engine.get_rule("does-not-exist") is None


# ---------------------------------------------------------------------------
# Matching: individual condition types
# ---------------------------------------------------------------------------


class TestMatchFrom:
    def test_from_matches_sender(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"from": "sender@example.com"})
        email = {"from": "sender@example.com"}
        assert engine.email_matches_rule(email, rule) is True

    def test_from_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"from": "Sender@Example.COM"})
        email = {"from": "sender@example.com"}
        assert engine.email_matches_rule(email, rule) is True

    def test_from_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"from": "other@example.com"})
        email = {"from": "sender@example.com"}
        assert engine.email_matches_rule(email, rule) is False

    def test_from_substring_match(self, engine):
        """The 'from' condition uses 'in' (substring) matching like the monolith."""
        rule = FilterRule(id="r1", name="test", conditions={"from": "sender"})
        email = {"from": "sender@example.com"}
        assert engine.email_matches_rule(email, rule) is True


class TestMatchTo:
    def test_to_matches_recipient(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"to": "me@proton.me"})
        email = {"to": "me@proton.me"}
        assert engine.email_matches_rule(email, rule) is True

    def test_to_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"to": "ME@PROTON.ME"})
        email = {"to": "me@proton.me"}
        assert engine.email_matches_rule(email, rule) is True

    def test_to_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"to": "other@proton.me"})
        email = {"to": "me@proton.me"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchSubjectContains:
    def test_subject_contains_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_contains": "newsletter"})
        email = {"subject": "Monthly Newsletter Update"}
        assert engine.email_matches_rule(email, rule) is True

    def test_subject_contains_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_contains": "NEWSLETTER"})
        email = {"subject": "Monthly Newsletter Update"}
        assert engine.email_matches_rule(email, rule) is True

    def test_subject_contains_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_contains": "urgent"})
        email = {"subject": "Monthly Newsletter Update"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchSubjectEquals:
    def test_subject_equals_exact_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_equals": "Hello World"})
        email = {"subject": "Hello World"}
        assert engine.email_matches_rule(email, rule) is True

    def test_subject_equals_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_equals": "hello world"})
        email = {"subject": "Hello World"}
        assert engine.email_matches_rule(email, rule) is True

    def test_subject_equals_substring_does_not_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_equals": "Hello"})
        email = {"subject": "Hello World"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchBodyContains:
    def test_body_contains_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"body_contains": "great content"})
        email = {"body": "Here is your newsletter with great content inside."}
        assert engine.email_matches_rule(email, rule) is True

    def test_body_contains_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"body_contains": "GREAT CONTENT"})
        email = {"body": "Here is your newsletter with great content inside."}
        assert engine.email_matches_rule(email, rule) is True

    def test_body_contains_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"body_contains": "missing phrase"})
        email = {"body": "Here is your newsletter."}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchSenderDomain:
    def test_sender_domain_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"sender_domain": "example.com"})
        email = {"from": "user@example.com"}
        assert engine.email_matches_rule(email, rule) is True

    def test_sender_domain_case_insensitive(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"sender_domain": "EXAMPLE.COM"})
        email = {"from": "user@example.com"}
        assert engine.email_matches_rule(email, rule) is True

    def test_sender_domain_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"sender_domain": "other.com"})
        email = {"from": "user@example.com"}
        assert engine.email_matches_rule(email, rule) is False

    def test_sender_domain_no_at_sign(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"sender_domain": "example.com"})
        email = {"from": "no-domain-here"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchHasAttachments:
    def test_has_attachments_true_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"has_attachments": True})
        email = {"has_attachments": True}
        assert engine.email_matches_rule(email, rule) is True

    def test_has_attachments_false_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"has_attachments": False})
        email = {"has_attachments": False}
        assert engine.email_matches_rule(email, rule) is True

    def test_has_attachments_mismatch(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"has_attachments": True})
        email = {"has_attachments": False}
        assert engine.email_matches_rule(email, rule) is False

    def test_has_attachments_missing_key(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"has_attachments": True})
        email = {"from": "test@test.com"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchOlderThanDays:
    def test_older_than_days_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"older_than_days": 7})
        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()
        email = {"date": old_date}
        assert engine.email_matches_rule(email, rule) is True

    def test_older_than_days_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"older_than_days": 7})
        recent_date = (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat()
        email = {"date": recent_date}
        assert engine.email_matches_rule(email, rule) is False

    def test_older_than_days_missing_date(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"older_than_days": 7})
        email = {"from": "test@test.com"}
        assert engine.email_matches_rule(email, rule) is False

    def test_older_than_days_invalid_date(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"older_than_days": 7})
        email = {"date": "not-a-date"}
        assert engine.email_matches_rule(email, rule) is False


class TestMatchNewerThanDays:
    def test_newer_than_days_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"newer_than_days": 7})
        recent_date = (datetime.now(tz=timezone.utc) - timedelta(days=3)).isoformat()
        email = {"date": recent_date}
        assert engine.email_matches_rule(email, rule) is True

    def test_newer_than_days_no_match(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"newer_than_days": 7})
        old_date = (datetime.now(tz=timezone.utc) - timedelta(days=10)).isoformat()
        email = {"date": old_date}
        assert engine.email_matches_rule(email, rule) is False


# ---------------------------------------------------------------------------
# Matching: compound conditions (AND logic)
# ---------------------------------------------------------------------------


class TestMatchMultipleConditions:
    def test_all_conditions_must_match(self, engine):
        rule = FilterRule(
            id="r1",
            name="test",
            conditions={
                "from": "sender@example.com",
                "subject_contains": "newsletter",
            },
        )
        email = {
            "from": "sender@example.com",
            "subject": "Monthly Newsletter",
        }
        assert engine.email_matches_rule(email, rule) is True

    def test_partial_match_returns_false(self, engine):
        rule = FilterRule(
            id="r1",
            name="test",
            conditions={
                "from": "sender@example.com",
                "subject_contains": "newsletter",
            },
        )
        email = {
            "from": "sender@example.com",
            "subject": "Important Update",
        }
        assert engine.email_matches_rule(email, rule) is False

    def test_empty_conditions_matches_all(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={})
        email = {"from": "any@any.com", "subject": "anything"}
        assert engine.email_matches_rule(email, rule) is True


class TestMatchDisabledRule:
    def test_disabled_rule_still_matches(self, engine):
        """Matching logic is separate from whether a rule is enabled/disabled."""
        rule = FilterRule(
            id="r1",
            name="test",
            conditions={"from": "sender@example.com"},
            enabled=False,
        )
        email = {"from": "sender@example.com"}
        assert engine.email_matches_rule(email, rule) is True


class TestMatchAllConditionTypes:
    def test_rule_with_all_string_conditions(self, engine):
        """A rule using every string-based condition type."""
        rule = FilterRule(
            id="r1",
            name="test",
            conditions={
                "from": "sender@example.com",
                "to": "me@proton.me",
                "subject_contains": "news",
                "body_contains": "content",
                "sender_domain": "example.com",
            },
        )
        email = {
            "from": "sender@example.com",
            "to": "me@proton.me",
            "subject": "Weekly News Digest",
            "body": "Here is some content for you.",
        }
        assert engine.email_matches_rule(email, rule) is True


# ---------------------------------------------------------------------------
# Persistence
# ---------------------------------------------------------------------------


class TestPersistence:
    def test_load_creates_default_when_missing(self, mock_config):
        engine = FilterRuleEngine(mock_config)
        rules = engine.load_rules()
        assert rules == []

    def test_create_rule_persists(self, mock_config, sample_conditions, sample_actions):
        engine1 = FilterRuleEngine(mock_config)
        rule = engine1.create_rule("Persist Me", sample_conditions, sample_actions)

        # Create a new engine instance pointing at the same data dir
        engine2 = FilterRuleEngine(mock_config)
        loaded = engine2.get_rule(rule.id)
        assert loaded is not None
        assert loaded.name == "Persist Me"
        assert loaded.conditions == sample_conditions
        assert loaded.actions == sample_actions

    def test_delete_rule_persists(self, mock_config, sample_conditions, sample_actions):
        engine1 = FilterRuleEngine(mock_config)
        rule = engine1.create_rule("Delete Me", sample_conditions, sample_actions)
        engine1.delete_rule(rule.id)

        engine2 = FilterRuleEngine(mock_config)
        assert engine2.get_rule(rule.id) is None

    def test_update_rule_persists(self, mock_config, sample_conditions, sample_actions):
        engine1 = FilterRuleEngine(mock_config)
        rule = engine1.create_rule("Update Me", sample_conditions, sample_actions)
        engine1.update_rule(rule.id, name="Updated Name")

        engine2 = FilterRuleEngine(mock_config)
        loaded = engine2.get_rule(rule.id)
        assert loaded.name == "Updated Name"

    def test_round_trip_serialization(self, mock_config, sample_conditions, sample_actions):
        engine1 = FilterRuleEngine(mock_config)
        original = engine1.create_rule(
            "Round Trip",
            sample_conditions,
            sample_actions,
            enabled=False,
        )

        engine2 = FilterRuleEngine(mock_config)
        loaded = engine2.get_rule(original.id)
        assert loaded.id == original.id
        assert loaded.name == original.name
        assert loaded.conditions == original.conditions
        assert loaded.actions == original.actions
        assert loaded.enabled == original.enabled
        assert loaded.created_at == original.created_at
        assert loaded.last_applied == original.last_applied
        assert loaded.emails_processed == original.emails_processed

    def test_json_file_structure(self, mock_config, sample_conditions, sample_actions, temp_dir):
        engine = FilterRuleEngine(mock_config)
        engine.create_rule("Verify Structure", sample_conditions, sample_actions)

        json_path = temp_dir / "filter_rules.json"
        with open(json_path) as f:
            data = json.load(f)

        assert "schema_version" in data
        assert data["schema_version"] == 1
        assert "rules" in data
        assert len(data["rules"]) == 1
        assert data["rules"][0]["name"] == "Verify Structure"


# ---------------------------------------------------------------------------
# Edge cases
# ---------------------------------------------------------------------------


class TestEdgeCases:
    def test_empty_conditions_dict(self, engine, sample_actions):
        rule = engine.create_rule("Empty Conds", {}, sample_actions)
        assert rule.conditions == {}
        # Empty conditions should match any email
        assert engine.email_matches_rule({"from": "any@any.com"}, rule) is True

    def test_empty_actions_dict(self, engine, sample_conditions):
        rule = engine.create_rule("Empty Actions", sample_conditions, {})
        assert rule.actions == {}

    def test_case_insensitive_from(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"from": "USER@EXAMPLE.COM"})
        email = {"from": "user@example.com"}
        assert engine.email_matches_rule(email, rule) is True

    def test_case_insensitive_subject_equals(self, engine):
        rule = FilterRule(id="r1", name="test", conditions={"subject_equals": "HELLO WORLD"})
        email = {"subject": "hello world"}
        assert engine.email_matches_rule(email, rule) is True

    def test_missing_email_fields_do_not_crash(self, engine):
        """Matching against an email missing all fields should not raise."""
        rule = FilterRule(
            id="r1",
            name="test",
            conditions={"from": "test@test.com"},
        )
        email: dict = {}
        assert engine.email_matches_rule(email, rule) is False

    def test_valid_conditions_list(self, engine):
        expected = [
            "from", "to", "subject_contains", "subject_equals",
            "body_contains", "sender_domain", "has_attachments",
            "older_than_days", "newer_than_days",
        ]
        assert engine.valid_conditions() == expected

    def test_valid_actions_list(self, engine):
        expected = [
            "move_to_folder", "mark_as_read", "mark_as_important",
            "delete", "forward_to", "auto_reply",
        ]
        assert engine.valid_actions() == expected

    def test_create_rule_with_all_valid_conditions(self, engine):
        conditions = {
            "from": "test@test.com",
            "to": "me@me.com",
            "subject_contains": "hello",
            "subject_equals": "Hello World",
            "body_contains": "content",
            "sender_domain": "test.com",
            "has_attachments": True,
            "older_than_days": 30,
            "newer_than_days": 1,
        }
        actions = {"move_to_folder": "Archive"}
        rule = engine.create_rule("All Conditions", conditions, actions)
        assert rule.conditions == conditions

    def test_create_rule_with_all_valid_actions(self, engine):
        conditions = {"from": "test@test.com"}
        actions = {
            "move_to_folder": "Archive",
            "mark_as_read": True,
            "mark_as_important": True,
            "delete": False,
            "forward_to": "other@test.com",
            "auto_reply": "I'm away",
        }
        rule = engine.create_rule("All Actions", conditions, actions)
        assert rule.actions == actions
