"""Comprehensive tests for the JunkDetector service.

Covers:
- Known spam detection with built-in patterns
- BUG FIX verification (admin@, support@, re:re:re:, exclamation threshold)
- Whitelist bypass (domain + sender, checked before blacklist)
- Blacklist auto-score (domain + sender)
- Custom JunkRule evaluation (enabled/disabled)
- Configurable threshold classification
- Config persistence (load/save, CRUD operations)
- Edge cases (empty data, long subjects, missing body, unicode)
"""

from __future__ import annotations

import json
import os
from pathlib import Path

import pytest

from proton_mcp.models.email import JunkAnalysis
from proton_mcp.services.junk import JunkDetector

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_email(
    subject: str = "",
    from_addr: str = "someone@example.com",
    body: str = "",
    email_id: str = "1",
) -> dict:
    return {
        "id": email_id,
        "subject": subject,
        "from": from_addr,
        "body": body,
    }


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def detector(mock_config) -> JunkDetector:
    """Fresh JunkDetector with an empty default config in a temp directory."""
    return JunkDetector(mock_config)


@pytest.fixture
def detector_with_sample(mock_config, fixtures_dir) -> JunkDetector:
    """JunkDetector pre-loaded with the sample junk config fixture."""
    src = fixtures_dir / "sample_junk_config.json"
    dst = Path(mock_config.data_dir) / "junk_config.json"
    dst.write_text(src.read_text())
    return JunkDetector(mock_config)


# ===================================================================
# 1. Known spam detection
# ===================================================================


class TestKnownSpamDetection:
    """Emails with obvious spam patterns should score high."""

    def test_urgent_action_required(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="URGENT ACTION REQUIRED: Verify now"))
        assert result.junk_score >= 2
        assert result.likelihood in ("medium", "high")
        assert result.is_likely_junk

    def test_congratulations_won(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="Congratulations! You have won a prize"))
        assert result.junk_score >= 2
        assert result.is_likely_junk

    def test_nigerian_prince(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="A Nigerian Prince needs your help"))
        assert result.junk_score >= 2
        assert result.is_likely_junk

    def test_free_money(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="Get free money today!"))
        assert result.junk_score >= 2

    def test_viagra_pharmacy(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="Buy viagra cheap pharmacy"))
        assert result.junk_score >= 2

    def test_suspicious_tld_sender(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(from_addr="noreply@phishing.tk", subject="Hello"))
        assert result.junk_score >= 1
        assert any("sender pattern" in i.lower() for i in result.indicators)

    def test_suspicious_ml_tld(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(from_addr="offers@deals.ml", subject="Hello"))
        assert result.junk_score >= 1

    def test_suspicious_ga_tld(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(from_addr="spam@bad.ga", subject="Hello"))
        assert result.junk_score >= 1

    def test_body_click_here_now(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(body="Please click here now to claim your prize"))
        assert result.junk_score >= 2

    def test_body_verify_account(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(body="You must verify account immediately or it will be closed"))
        assert result.junk_score >= 2

    def test_body_inheritance_million(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(body="You have an inheritance of 5 million dollars"))
        assert result.junk_score >= 2

    def test_body_bitcoin_investment(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(body="Amazing bitcoin investment opportunity awaits"))
        assert result.junk_score >= 2

    def test_excessive_caps(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="THIS IS ALL CAPS SHOUTING"))
        assert any("capital letters" in i.lower() for i in result.indicators)
        assert result.junk_score >= 1

    def test_combined_spam_signals(self, detector: JunkDetector):
        """Multiple spam signals should stack scores."""
        result = detector.analyze_email(
            _make_email(
                subject="URGENT ACTION REQUIRED: Free money",
                from_addr="scam@shady.tk",
                body="Click here now to verify account immediately",
            )
        )
        assert result.junk_score >= 6
        assert result.likelihood == "high"
        assert result.is_likely_junk

    def test_security_sender_pattern(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(from_addr="security@phishing-site.com", subject="Alert"))
        assert result.junk_score >= 1


# ===================================================================
# 2. BUG FIX verification -- legitimate emails
# ===================================================================


class TestBugFixVerification:
    """Verify that the bug fixes from BUG-junk-false-positives are applied."""

    def test_admin_at_uber_not_junk(self, detector: JunkDetector):
        """admin@uber.com should NOT trigger junk detection (BUG FIX)."""
        result = detector.analyze_email(
            _make_email(
                subject="Your Uber receipt",
                from_addr="admin@uber.com",
                body="Thanks for riding with Uber.",
            )
        )
        assert result.junk_score == 0
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_support_at_experian_not_junk(self, detector: JunkDetector):
        """support@experian.com should NOT trigger junk detection (BUG FIX)."""
        result = detector.analyze_email(
            _make_email(
                subject="Your credit report is ready",
                from_addr="support@experian.com",
                body="Your latest credit report is available.",
            )
        )
        assert result.junk_score == 0
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_reply_chain_not_junk(self, detector: JunkDetector):
        """Email with subject 're: re: re: Meeting notes' should NOT trigger (BUG FIX)."""
        result = detector.analyze_email(
            _make_email(
                subject="re: re: re: Meeting notes",
                from_addr="colleague@company.com",
                body="Let's reschedule.",
            )
        )
        assert result.junk_score == 0
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_five_exclamation_marks_not_junk(self, detector: JunkDetector):
        """Email with 5 exclamation marks should NOT trigger (raised threshold to 10)."""
        result = detector.analyze_email(
            _make_email(
                subject="Big sale this weekend!!!!!",
                from_addr="deals@legit-store.com",
                body="Everything is on sale!",
            )
        )
        # 5 (subject) + 1 (body) = 6 total, which is below threshold 10
        assert not any("exclamation" in i.lower() for i in result.indicators)

    def test_eleven_exclamation_marks_triggers(self, detector: JunkDetector):
        """Email with 11+ exclamation marks SHOULD trigger."""
        result = detector.analyze_email(
            _make_email(
                subject="BUY NOW!!!!!!!!!!!",
                from_addr="spammer@example.com",
                body="!!",
            )
        )
        # 11 (subject) + 2 (body) = 13, above threshold 10
        assert any("exclamation" in i.lower() for i in result.indicators)

    def test_admin_at_generic_domain_not_flagged(self, detector: JunkDetector):
        """admin@ addresses at any domain should not be flagged as suspicious."""
        result = detector.analyze_email(
            _make_email(
                subject="Password reset",
                from_addr="admin@mycompany.com",
                body="Click to reset your password.",
            )
        )
        # Should not have any sender-pattern indicator for admin@
        assert not any("admin@" in i for i in result.indicators)

    def test_support_at_generic_domain_not_flagged(self, detector: JunkDetector):
        """support@ addresses at any domain should not be flagged as suspicious."""
        result = detector.analyze_email(
            _make_email(
                subject="Ticket update",
                from_addr="support@helpdesk.com",
                body="Your ticket has been updated.",
            )
        )
        assert not any("support@" in i for i in result.indicators)


# ===================================================================
# 3. Whitelist tests
# ===================================================================


class TestWhitelist:
    """Whitelisted senders/domains should bypass all scoring."""

    def test_whitelisted_domain_bypasses_scoring(self, detector: JunkDetector):
        detector.add_whitelist_entry("trusted.com", entry_type="domain")
        result = detector.analyze_email(
            _make_email(
                subject="URGENT ACTION REQUIRED: Free money",
                from_addr="user@trusted.com",
                body="Click here now",
            )
        )
        assert result.junk_score == 0
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_whitelisted_sender_bypasses_scoring(self, detector: JunkDetector):
        detector.add_whitelist_entry("boss@company.com", entry_type="sender")
        result = detector.analyze_email(
            _make_email(
                subject="URGENT ACTION REQUIRED",
                from_addr="boss@company.com",
            )
        )
        assert result.junk_score == 0
        assert not result.is_likely_junk

    def test_whitelist_checked_before_blacklist(self, detector: JunkDetector):
        """If a sender is both whitelisted and blacklisted, whitelist wins."""
        detector.add_whitelist_entry("dual@example.com", entry_type="sender")
        detector.add_blacklist_entry("dual@example.com", entry_type="sender")
        result = detector.analyze_email(_make_email(from_addr="dual@example.com", subject="Test"))
        assert result.junk_score == 0
        assert not result.is_likely_junk

    def test_whitelist_domain_also_covers_sender(self, detector: JunkDetector):
        """Whitelisting a domain covers any sender at that domain."""
        detector.add_whitelist_entry("company.com", entry_type="domain")
        assert detector.is_whitelisted("alice@company.com")
        assert detector.is_whitelisted("bob@company.com")

    def test_whitelist_is_case_insensitive(self, detector: JunkDetector):
        detector.add_whitelist_entry("TRUSTED.COM", entry_type="domain")
        assert detector.is_whitelisted("user@trusted.com")
        assert detector.is_whitelisted("user@TRUSTED.COM")

    def test_whitelisted_display_name_format(self, detector: JunkDetector):
        """Should handle 'Name <email@domain>' format."""
        detector.add_whitelist_entry("friend@example.com", entry_type="sender")
        assert detector.is_whitelisted("John Doe <friend@example.com>")

    def test_is_whitelisted_false_for_unknown(self, detector: JunkDetector):
        assert not detector.is_whitelisted("random@unknown.com")

    def test_whitelist_domain_in_sample_config(self, detector_with_sample: JunkDetector):
        """Sample config has uber.com and experian.com whitelisted."""
        assert detector_with_sample.is_whitelisted("admin@uber.com")
        assert detector_with_sample.is_whitelisted("support@experian.com")
        assert detector_with_sample.is_whitelisted("anyone@chase.com")


# ===================================================================
# 4. Blacklist tests
# ===================================================================


class TestBlacklist:
    """Blacklisted senders/domains should auto-score high."""

    def test_blacklisted_domain_auto_scores_high(self, detector: JunkDetector):
        detector.add_blacklist_entry("spam-domain.tk", entry_type="domain")
        result = detector.analyze_email(
            _make_email(
                subject="Normal subject",
                from_addr="user@spam-domain.tk",
            )
        )
        assert result.junk_score == 10
        assert result.likelihood == "high"
        assert result.is_likely_junk

    def test_blacklisted_sender_auto_scores_high(self, detector: JunkDetector):
        detector.add_blacklist_entry("known-spammer@evil.com", entry_type="sender")
        result = detector.analyze_email(
            _make_email(
                subject="Hi there",
                from_addr="known-spammer@evil.com",
            )
        )
        assert result.junk_score == 10
        assert result.likelihood == "high"

    def test_blacklist_is_case_insensitive(self, detector: JunkDetector):
        detector.add_blacklist_entry("BAD.COM", entry_type="domain")
        assert detector.is_blacklisted("anyone@bad.com")

    def test_is_blacklisted_false_for_unknown(self, detector: JunkDetector):
        assert not detector.is_blacklisted("innocent@normal.com")

    def test_blacklist_domain_in_sample_config(self, detector_with_sample: JunkDetector):
        assert detector_with_sample.is_blacklisted("user@spam-domain.tk")
        assert detector_with_sample.is_blacklisted("user@phishing.ml")
        assert detector_with_sample.is_blacklisted("known-spammer@example.ga")


# ===================================================================
# 5. Custom pattern tests
# ===================================================================


class TestCustomPatterns:
    """Custom JunkRule patterns should be evaluated and disabled ones skipped."""

    def test_custom_rule_matches(self, detector: JunkDetector):
        detector.create_rule(
            name="Crypto scam",
            field="subject",
            pattern=r"bitcoin.*guaranteed.*return",
            score=3,
        )
        result = detector.analyze_email(_make_email(subject="Bitcoin guaranteed return of 500%"))
        assert result.junk_score >= 3
        assert any("Crypto scam" in i for i in result.indicators)

    def test_disabled_rule_is_skipped(self, detector: JunkDetector):
        detector.create_rule(
            name="Disabled rule",
            field="subject",
            pattern=r"test-pattern-xyz",
            score=5,
            enabled=False,
        )
        result = detector.analyze_email(_make_email(subject="This has test-pattern-xyz in it"))
        # The disabled rule should contribute nothing
        assert result.junk_score == 0

    def test_custom_rule_body_field(self, detector: JunkDetector):
        detector.create_rule(
            name="MLM pitch",
            field="body",
            pattern=r"multi.*level.*marketing",
            score=4,
        )
        result = detector.analyze_email(_make_email(body="Join our multi level marketing empire today"))
        assert result.junk_score >= 4

    def test_custom_rule_sender_field(self, detector: JunkDetector):
        detector.create_rule(
            name="Bad sender",
            field="sender",
            pattern=r"@evil-corp\.com$",
            score=3,
        )
        result = detector.analyze_email(_make_email(from_addr="contact@evil-corp.com"))
        assert result.junk_score >= 3

    def test_invalid_regex_in_custom_rule_is_skipped(self, detector: JunkDetector):
        """Invalid regex should not crash, just be skipped."""
        detector.create_rule(
            name="Bad regex",
            field="subject",
            pattern=r"[invalid((",
            score=5,
        )
        # Should not raise
        result = detector.analyze_email(_make_email(subject="anything"))
        assert result.junk_score == 0

    def test_sample_config_custom_pattern(self, detector_with_sample: JunkDetector):
        """Sample config has a 'Crypto scam subject' rule."""
        result = detector_with_sample.analyze_email(_make_email(subject="Bitcoin guaranteed return of 1000%"))
        assert any("Crypto scam" in i for i in result.indicators)


# ===================================================================
# 6. Threshold tests
# ===================================================================


class TestThresholds:
    """Configurable thresholds should change classification."""

    def test_default_thresholds(self, detector: JunkDetector):
        """Default: low=1, medium=2, high=4."""
        cfg = detector.load_config()
        assert cfg.thresholds == {"low": 1, "medium": 2, "high": 4}

    def test_custom_thresholds_change_classification(self, detector: JunkDetector):
        """With higher thresholds, the same score leads to lower classification."""
        cfg = detector.load_config()
        cfg.thresholds = {"low": 5, "medium": 10, "high": 20}
        detector.save_config(cfg)

        result = detector.analyze_email(_make_email(subject="Congratulations you won a prize"))
        # Score of 2 is below new "low" of 5
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_very_low_thresholds(self, detector: JunkDetector):
        """With very low thresholds, even minor signals become 'high'."""
        cfg = detector.load_config()
        cfg.thresholds = {"low": 0, "medium": 0, "high": 1}
        detector.save_config(cfg)

        result = detector.analyze_email(_make_email(from_addr="user@suspicious.ga", subject="Hello"))
        # Score of 1 from .ga TLD
        assert result.likelihood == "high"

    def test_is_likely_junk_uses_medium_threshold(self, detector: JunkDetector):
        """is_likely_junk is True when score >= medium threshold."""
        cfg = detector.load_config()
        cfg.thresholds = {"low": 1, "medium": 100, "high": 200}
        detector.save_config(cfg)

        result = detector.analyze_email(_make_email(subject="Congratulations you won (Free money)"))
        # Score >= 4 but medium threshold is 100
        assert not result.is_likely_junk


# ===================================================================
# 7. Config persistence tests
# ===================================================================


class TestConfigPersistence:
    """Config should persist correctly via JsonStore."""

    def test_load_creates_default_when_missing(self, mock_config):
        config_path = os.path.join(mock_config.data_dir, "junk_config.json")
        assert not os.path.exists(config_path)
        det = JunkDetector(mock_config)
        assert os.path.exists(config_path)
        cfg = det.load_config()
        assert cfg.schema_version == 1
        assert cfg.custom_patterns == []
        assert cfg.whitelist == {"domains": [], "senders": []}
        assert cfg.blacklist == {"domains": [], "senders": []}
        assert cfg.thresholds == {"low": 1, "medium": 2, "high": 4}

    def test_save_and_reload_preserves_config(self, mock_config):
        det = JunkDetector(mock_config)
        cfg = det.load_config()
        cfg.whitelist["domains"].append("saved-domain.com")
        cfg.blacklist["senders"].append("bad@saved.com")
        cfg.thresholds["high"] = 10
        det.save_config(cfg)

        # Create a new detector reading from the same file
        det2 = JunkDetector(mock_config)
        cfg2 = det2.load_config()
        assert "saved-domain.com" in cfg2.whitelist["domains"]
        assert "bad@saved.com" in cfg2.blacklist["senders"]
        assert cfg2.thresholds["high"] == 10

    def test_whitelist_crud_persists(self, mock_config):
        det = JunkDetector(mock_config)

        # Add
        assert det.add_whitelist_entry("good.com", "domain")
        assert det.add_whitelist_entry("friend@nice.com", "sender")

        # Verify via new detector
        det2 = JunkDetector(mock_config)
        assert det2.is_whitelisted("user@good.com")
        assert det2.is_whitelisted("friend@nice.com")

        # Remove
        assert det2.remove_whitelist_entry("good.com", "domain")
        det3 = JunkDetector(mock_config)
        assert not det3.is_whitelisted("user@good.com")
        assert det3.is_whitelisted("friend@nice.com")

    def test_blacklist_crud_persists(self, mock_config):
        det = JunkDetector(mock_config)

        assert det.add_blacklist_entry("evil.tk", "domain")
        assert det.add_blacklist_entry("spammer@bad.com", "sender")

        det2 = JunkDetector(mock_config)
        assert det2.is_blacklisted("anyone@evil.tk")
        assert det2.is_blacklisted("spammer@bad.com")

        assert det2.remove_blacklist_entry("evil.tk", "domain")
        det3 = JunkDetector(mock_config)
        assert not det3.is_blacklisted("anyone@evil.tk")
        assert det3.is_blacklisted("spammer@bad.com")

    def test_rule_crud_persists(self, mock_config):
        det = JunkDetector(mock_config)

        rule = det.create_rule("Test rule", "subject", r"test-pattern", score=3)
        rule_id = rule.id

        # Reload and verify
        det2 = JunkDetector(mock_config)
        cfg = det2.load_config()
        assert len(cfg.custom_patterns) == 1
        assert cfg.custom_patterns[0].name == "Test rule"
        assert cfg.custom_patterns[0].score == 3

        # Update
        assert det2.update_rule(rule_id, score=5, name="Updated rule")
        det3 = JunkDetector(mock_config)
        cfg3 = det3.load_config()
        assert cfg3.custom_patterns[0].name == "Updated rule"
        assert cfg3.custom_patterns[0].score == 5

        # Delete
        assert det3.delete_rule(rule_id)
        det4 = JunkDetector(mock_config)
        assert len(det4.load_config().custom_patterns) == 0

    def test_add_duplicate_whitelist_returns_false(self, detector: JunkDetector):
        assert detector.add_whitelist_entry("dup.com", "domain") is True
        assert detector.add_whitelist_entry("dup.com", "domain") is False

    def test_remove_nonexistent_whitelist_returns_false(self, detector: JunkDetector):
        assert detector.remove_whitelist_entry("nope.com", "domain") is False

    def test_add_duplicate_blacklist_returns_false(self, detector: JunkDetector):
        assert detector.add_blacklist_entry("dup.com", "domain") is True
        assert detector.add_blacklist_entry("dup.com", "domain") is False

    def test_remove_nonexistent_blacklist_returns_false(self, detector: JunkDetector):
        assert detector.remove_blacklist_entry("nope.com", "domain") is False

    def test_delete_nonexistent_rule_returns_false(self, detector: JunkDetector):
        assert detector.delete_rule("nonexistent-id") is False

    def test_update_nonexistent_rule_returns_false(self, detector: JunkDetector):
        assert detector.update_rule("nonexistent-id", score=5) is False

    def test_sample_config_loads_correctly(self, detector_with_sample: JunkDetector):
        cfg = detector_with_sample.load_config()
        assert cfg.schema_version == 1
        assert len(cfg.custom_patterns) == 1
        assert cfg.custom_patterns[0].id == "custom-1"
        assert "uber.com" in cfg.whitelist["domains"]
        assert "spam-domain.tk" in cfg.blacklist["domains"]

    def test_raw_json_matches_expected_default(self, mock_config):
        JunkDetector(mock_config)
        config_path = os.path.join(mock_config.data_dir, "junk_config.json")
        with open(config_path) as f:
            data = json.load(f)
        assert data["schema_version"] == 1
        assert data["custom_patterns"] == []
        assert data["whitelist"] == {"domains": [], "senders": []}
        assert data["blacklist"] == {"domains": [], "senders": []}
        assert data["thresholds"] == {"low": 1, "medium": 2, "high": 4}


# ===================================================================
# 8. Edge cases
# ===================================================================


class TestEdgeCases:
    """Edge-case handling and robustness."""

    def test_empty_email_data(self, detector: JunkDetector):
        result = detector.analyze_email({})
        assert result.junk_score == 0
        assert result.likelihood == "unlikely"
        assert not result.is_likely_junk

    def test_missing_body_field(self, detector: JunkDetector):
        result = detector.analyze_email({"subject": "Hello", "from": "user@example.com"})
        assert result.junk_score == 0

    def test_missing_subject_field(self, detector: JunkDetector):
        result = detector.analyze_email({"from": "user@example.com", "body": "Some text"})
        assert result.junk_score == 0

    def test_missing_from_field(self, detector: JunkDetector):
        result = detector.analyze_email({"subject": "Hello", "body": "Some text"})
        assert result.junk_score == 0

    def test_very_long_subject(self, detector: JunkDetector):
        long_subject = "A" * 10000
        result = detector.analyze_email(_make_email(subject=long_subject))
        # All caps, len > 10, caps_ratio == 1.0 > 0.5
        assert any("capital letters" in i.lower() for i in result.indicators)

    def test_unicode_subject(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="Bonjour! Votre commande est prete"))
        assert result.likelihood == "unlikely"

    def test_unicode_body(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(body="Hola, tu pedido esta listo para recoger"))
        assert result.likelihood == "unlikely"

    def test_email_id_preserved_in_result(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(email_id="42"))
        assert result.email_id == "42"

    def test_email_id_missing_defaults_empty(self, detector: JunkDetector):
        result = detector.analyze_email({"subject": "Test"})
        assert result.email_id == ""

    def test_email_with_display_name_from(self, detector: JunkDetector):
        """Handle 'Display Name <email@domain>' format in from field."""
        detector.add_whitelist_entry("safe.com", "domain")
        result = detector.analyze_email(
            _make_email(
                subject="Spam subject: urgent action required",
                from_addr="John Smith <user@safe.com>",
            )
        )
        # Should be whitelisted
        assert result.junk_score == 0

    def test_caps_ratio_not_triggered_for_short_subjects(self, detector: JunkDetector):
        """Subjects <= 10 chars should not trigger excessive caps check."""
        result = detector.analyze_email(_make_email(subject="HELLO"))
        assert not any("capital letters" in i.lower() for i in result.indicators)

    def test_result_is_junk_analysis_instance(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email())
        assert isinstance(result, JunkAnalysis)

    def test_result_to_dict_roundtrip(self, detector: JunkDetector):
        result = detector.analyze_email(_make_email(subject="Congratulations you won a prize", email_id="99"))
        d = result.to_dict()
        rebuilt = JunkAnalysis.from_dict(d)
        assert rebuilt.junk_score == result.junk_score
        assert rebuilt.likelihood == result.likelihood
        assert rebuilt.indicators == result.indicators
        assert rebuilt.email_id == "99"

    def test_numeric_email_id_is_stringified(self, detector: JunkDetector):
        result = detector.analyze_email({"id": 123, "subject": "Test", "from": "a@b.com", "body": ""})
        assert result.email_id == "123"


# ===================================================================
# 9. Whitelist/Blacklist CRUD return values
# ===================================================================


class TestCrudReturnValues:
    """CRUD methods should return correct booleans."""

    def test_add_whitelist_sender(self, detector: JunkDetector):
        assert detector.add_whitelist_entry("me@example.com", "sender") is True
        cfg = detector.load_config()
        assert "me@example.com" in cfg.whitelist["senders"]

    def test_add_blacklist_sender(self, detector: JunkDetector):
        assert detector.add_blacklist_entry("bad@evil.com", "sender") is True
        cfg = detector.load_config()
        assert "bad@evil.com" in cfg.blacklist["senders"]

    def test_remove_whitelist_sender(self, detector: JunkDetector):
        detector.add_whitelist_entry("me@example.com", "sender")
        assert detector.remove_whitelist_entry("me@example.com", "sender") is True
        cfg = detector.load_config()
        assert "me@example.com" not in cfg.whitelist["senders"]

    def test_remove_blacklist_sender(self, detector: JunkDetector):
        detector.add_blacklist_entry("bad@evil.com", "sender")
        assert detector.remove_blacklist_entry("bad@evil.com", "sender") is True
        cfg = detector.load_config()
        assert "bad@evil.com" not in cfg.blacklist["senders"]


# ===================================================================
# 10. Rule CRUD edge cases
# ===================================================================


class TestRuleCrud:
    """Rule creation, update, and deletion edge cases."""

    def test_create_rule_generates_unique_id(self, detector: JunkDetector):
        r1 = detector.create_rule("Rule A", "subject", "pat-a")
        r2 = detector.create_rule("Rule B", "subject", "pat-b")
        assert r1.id != r2.id

    def test_create_rule_with_defaults(self, detector: JunkDetector):
        rule = detector.create_rule("Defaults", "body", "some-pattern")
        assert rule.score == 2
        assert rule.enabled is True

    def test_update_rule_partial_fields(self, detector: JunkDetector):
        rule = detector.create_rule("Original", "subject", "original-pat", score=1)
        detector.update_rule(rule.id, name="Renamed")
        cfg = detector.load_config()
        updated = [r for r in cfg.custom_patterns if r.id == rule.id][0]
        assert updated.name == "Renamed"
        assert updated.score == 1  # unchanged
        assert updated.pattern == "original-pat"  # unchanged

    def test_update_rule_enable_disable(self, detector: JunkDetector):
        rule = detector.create_rule("Toggle", "subject", "toggle-pat", enabled=True)
        detector.update_rule(rule.id, enabled=False)
        cfg = detector.load_config()
        updated = [r for r in cfg.custom_patterns if r.id == rule.id][0]
        assert updated.enabled is False

    def test_update_ignores_unknown_fields(self, detector: JunkDetector):
        rule = detector.create_rule("Safe", "subject", "safe-pat")
        result = detector.update_rule(rule.id, unknown_field="value")
        assert result is True  # found the rule, but unknown fields are ignored
        cfg = detector.load_config()
        assert cfg.custom_patterns[0].name == "Safe"  # unchanged

    def test_delete_removes_correct_rule(self, detector: JunkDetector):
        r1 = detector.create_rule("Keep", "subject", "keep-pat")
        r2 = detector.create_rule("Delete", "subject", "delete-pat")
        detector.delete_rule(r2.id)
        cfg = detector.load_config()
        assert len(cfg.custom_patterns) == 1
        assert cfg.custom_patterns[0].id == r1.id

    def test_multiple_rules_all_scored(self, detector: JunkDetector):
        detector.create_rule("R1", "subject", r"multi-rule-a", score=1)
        detector.create_rule("R2", "subject", r"multi-rule-b", score=2)
        result = detector.analyze_email(_make_email(subject="multi-rule-a and multi-rule-b together"))
        assert result.junk_score >= 3
