"""Integration tests for configuration persistence.

Verifies that JSON-backed configs survive save/reload cycles. Each test
creates data via one service instance, then instantiates a NEW service
instance (simulating a restart) and verifies the data was persisted.
"""

from __future__ import annotations

from proton_mcp.services.filter_rules import FilterRuleEngine
from proton_mcp.services.junk import JunkDetector
from proton_mcp.services.unsubscribe import UnsubscribeService

# ===========================================================================
# JunkDetector persistence
# ===========================================================================


class TestJunkConfigPersistence:
    """Test that junk detection config survives save/reload cycles."""

    def test_custom_rule_persists_across_restart(self, integration_config):
        # Create a custom rule with the first instance
        detector1 = JunkDetector(integration_config)
        rule = detector1.create_rule(
            name="Block Crypto Spam",
            field="subject",
            pattern=r"crypto.*guaranteed.*profit",
            score=5,
        )
        rule_id = rule.id

        # Simulate restart: create a new instance
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert len(config.custom_patterns) == 1
        assert config.custom_patterns[0].id == rule_id
        assert config.custom_patterns[0].name == "Block Crypto Spam"
        assert config.custom_patterns[0].pattern == r"crypto.*guaranteed.*profit"
        assert config.custom_patterns[0].score == 5

    def test_whitelist_persists_across_restart(self, integration_config):
        detector1 = JunkDetector(integration_config)
        detector1.add_whitelist_entry("proton.me", "domain")
        detector1.add_whitelist_entry("trusted@example.com", "sender")

        # Restart
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert "proton.me" in config.whitelist["domains"]
        assert "trusted@example.com" in config.whitelist["senders"]

    def test_blacklist_persists_across_restart(self, integration_config):
        detector1 = JunkDetector(integration_config)
        detector1.add_blacklist_entry("spam.tk", "domain")

        # Restart
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert "spam.tk" in config.blacklist["domains"]

    def test_rule_deletion_persists(self, integration_config):
        detector1 = JunkDetector(integration_config)
        rule = detector1.create_rule("Temp Rule", "subject", r"temp.*", score=1)
        rule_id = rule.id
        detector1.delete_rule(rule_id)

        # Restart
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert len(config.custom_patterns) == 0

    def test_rule_update_persists(self, integration_config):
        detector1 = JunkDetector(integration_config)
        rule = detector1.create_rule("My Rule", "subject", r"test", score=2)
        detector1.update_rule(rule.id, score=10, name="Updated Rule")

        # Restart
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert config.custom_patterns[0].name == "Updated Rule"
        assert config.custom_patterns[0].score == 10

    def test_multiple_rules_persist(self, integration_config):
        detector1 = JunkDetector(integration_config)
        detector1.create_rule("Rule A", "subject", r"aaa", score=1)
        detector1.create_rule("Rule B", "body", r"bbb", score=3)
        detector1.create_rule("Rule C", "sender", r"ccc", score=5)

        # Restart
        detector2 = JunkDetector(integration_config)
        config = detector2.load_config()

        assert len(config.custom_patterns) == 3
        names = {r.name for r in config.custom_patterns}
        assert names == {"Rule A", "Rule B", "Rule C"}


# ===========================================================================
# FilterRuleEngine persistence
# ===========================================================================


class TestFilterRulePersistence:
    """Test that filter rules survive save/reload cycles."""

    def test_rule_persists_across_restart(self, integration_config):
        engine1 = FilterRuleEngine(integration_config)
        rule = engine1.create_rule(
            "GitHub Notifications",
            {"sender_domain": "github.com"},
            {"move_to_folder": "GitHub", "mark_as_read": True},
        )
        rule_id = rule.id

        # Restart
        engine2 = FilterRuleEngine(integration_config)
        rules = engine2.load_rules()

        assert len(rules) == 1
        assert rules[0].id == rule_id
        assert rules[0].name == "GitHub Notifications"
        assert rules[0].conditions == {"sender_domain": "github.com"}
        assert rules[0].actions == {"move_to_folder": "GitHub", "mark_as_read": True}

    def test_rule_deletion_persists(self, integration_config):
        engine1 = FilterRuleEngine(integration_config)
        rule = engine1.create_rule("Temp", {"from": "temp@test.com"}, {"delete": True})
        engine1.delete_rule(rule.id)

        # Restart
        engine2 = FilterRuleEngine(integration_config)
        rules = engine2.load_rules()

        assert len(rules) == 0

    def test_rule_update_persists(self, integration_config):
        engine1 = FilterRuleEngine(integration_config)
        rule = engine1.create_rule(
            "Newsletter",
            {"from": "news@example.com"},
            {"move_to_folder": "News"},
        )
        engine1.update_rule(rule.id, enabled=False, name="Old Newsletter")

        # Restart
        engine2 = FilterRuleEngine(integration_config)
        rules = engine2.load_rules()

        assert len(rules) == 1
        assert rules[0].name == "Old Newsletter"
        assert rules[0].enabled is False

    def test_multiple_rules_persist(self, integration_config):
        engine1 = FilterRuleEngine(integration_config)
        engine1.create_rule("Rule 1", {"from": "a@a.com"}, {"mark_as_read": True})
        engine1.create_rule("Rule 2", {"from": "b@b.com"}, {"mark_as_important": True})
        engine1.create_rule("Rule 3", {"from": "c@c.com"}, {"move_to_folder": "VIP"})

        # Restart
        engine2 = FilterRuleEngine(integration_config)
        rules = engine2.load_rules()

        assert len(rules) == 3
        names = {r.name for r in rules}
        assert names == {"Rule 1", "Rule 2", "Rule 3"}


# ===========================================================================
# UnsubscribeService persistence
# ===========================================================================


class TestUnsubscribePersistence:
    """Test that unsubscribe config and history survive save/reload cycles."""

    def test_sender_preference_persists(self, integration_config):
        unsub1 = UnsubscribeService(integration_config)
        unsub1.add_sender_preference("spam@marketing.com", "always_unsubscribe")

        # Restart
        unsub2 = UnsubscribeService(integration_config)
        pref = unsub2.get_sender_preference("spam@marketing.com")

        assert pref is not None
        assert pref.action == "always_unsubscribe"

    def test_sender_preference_removal_persists(self, integration_config):
        unsub1 = UnsubscribeService(integration_config)
        unsub1.add_sender_preference("news@example.com", "never_unsubscribe")
        unsub1.remove_sender_preference("news@example.com")

        # Restart
        unsub2 = UnsubscribeService(integration_config)
        pref = unsub2.get_sender_preference("news@example.com")

        assert pref is None

    def test_detection_pattern_persists(self, integration_config):
        unsub1 = UnsubscribeService(integration_config)
        pattern = unsub1.add_detection_pattern(
            "Custom Tracker",
            r"custom\.tracker\.com",
            "tracker_domain",
        )
        pattern_id = pattern.id

        # Restart
        unsub2 = UnsubscribeService(integration_config)
        config = unsub2.load_config()

        patterns = config.get("detection_patterns", [])
        custom_patterns = [p for p in patterns if p.get("id") == pattern_id]
        assert len(custom_patterns) == 1
        assert custom_patterns[0]["name"] == "Custom Tracker"

    def test_detection_pattern_removal_persists(self, integration_config):
        unsub1 = UnsubscribeService(integration_config)
        pattern = unsub1.add_detection_pattern("Temp Pattern", r"temp\.com")
        unsub1.remove_detection_pattern(pattern.id)

        # Restart
        unsub2 = UnsubscribeService(integration_config)
        config = unsub2.load_config()

        patterns = config.get("detection_patterns", [])
        custom = [p for p in patterns if p.get("id") == pattern.id]
        assert len(custom) == 0

    def test_history_persists(self, integration_config):
        unsub1 = UnsubscribeService(integration_config)
        unsub1.log_attempt(
            sender="newsletter@example.com",
            method="one_click",
            url="https://example.com/unsub",
            success=True,
        )
        unsub1.log_attempt(
            sender="spam@marketing.com",
            method="http",
            url="https://marketing.com/unsub",
            success=False,
        )

        # Restart
        unsub2 = UnsubscribeService(integration_config)
        history = unsub2.get_history()

        assert len(history) == 2
        assert history[0].sender == "newsletter@example.com"
        assert history[0].success is True
        assert history[1].sender == "spam@marketing.com"
        assert history[1].success is False

    def test_full_config_roundtrip(self, integration_config):
        """Test that all config fields survive a complete roundtrip."""
        unsub1 = UnsubscribeService(integration_config)

        # Add preferences
        unsub1.add_sender_preference("keep@good.com", "never_unsubscribe")
        unsub1.add_sender_preference("block@bad.com", "always_unsubscribe")

        # Add patterns
        unsub1.add_detection_pattern("Tracker A", r"tracker-a\.com")

        # Log attempts
        unsub1.log_attempt("test@test.com", "http", "https://test.com/unsub", True)

        # Full restart
        unsub2 = UnsubscribeService(integration_config)
        config = unsub2.load_config()

        assert len(config.get("sender_preferences", [])) == 2
        # Built-in patterns (3) + custom (1)
        assert len(config.get("detection_patterns", [])) >= 4
        assert len(config.get("history", [])) == 1
