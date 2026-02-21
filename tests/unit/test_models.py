"""Comprehensive tests for email and configuration data models."""

from proton_mcp.models.email import (
    DetectionPattern,
    EmailSummary,
    EmailWithHtml,
    FilterRule,
    FullEmail,
    JunkAnalysis,
    JunkConfig,
    JunkRule,
    UnsubscribeHistoryEntry,
    UnsubscribeMethod,
    UnsubscribePreference,
)

# ---------------------------------------------------------------------------
# EmailSummary
# ---------------------------------------------------------------------------


class TestEmailSummary:
    def test_construction_all_fields(self):
        s = EmailSummary(
            id="123",
            subject="Test Subject",
            from_addr="alice@example.com",
            date="2026-02-20",
            body_preview="Hello world",
        )
        assert s.id == "123"
        assert s.subject == "Test Subject"
        assert s.from_addr == "alice@example.com"
        assert s.date == "2026-02-20"
        assert s.body_preview == "Hello world"

    def test_default_body_preview(self):
        s = EmailSummary(id="1", subject="Hi", from_addr="a@b.com", date="2026-01-01")
        assert s.body_preview == ""

    def test_to_dict(self):
        s = EmailSummary(
            id="42",
            subject="Subject",
            from_addr="sender@test.com",
            date="2026-02-20",
            body_preview="preview",
        )
        d = s.to_dict()
        assert d == {
            "id": "42",
            "subject": "Subject",
            "from_addr": "sender@test.com",
            "date": "2026-02-20",
            "body_preview": "preview",
        }

    def test_from_dict(self):
        data = {
            "id": "42",
            "subject": "Subject",
            "from_addr": "sender@test.com",
            "date": "2026-02-20",
            "body_preview": "preview",
        }
        s = EmailSummary.from_dict(data)
        assert s.id == "42"
        assert s.body_preview == "preview"

    def test_from_dict_missing_optional(self):
        data = {
            "id": "1",
            "subject": "Hi",
            "from_addr": "a@b.com",
            "date": "2026-01-01",
        }
        s = EmailSummary.from_dict(data)
        assert s.body_preview == ""

    def test_round_trip(self):
        original = EmailSummary(
            id="99",
            subject="Round Trip",
            from_addr="rt@test.com",
            date="2026-03-01",
            body_preview="This is a preview",
        )
        assert EmailSummary.from_dict(original.to_dict()) == original

    def test_round_trip_defaults(self):
        original = EmailSummary(id="1", subject="X", from_addr="a@b.com", date="d")
        assert EmailSummary.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# FullEmail
# ---------------------------------------------------------------------------


class TestFullEmail:
    def test_construction_all_fields(self):
        e = FullEmail(
            id="10",
            subject="Full",
            from_addr="from@x.com",
            to_addr="to@x.com",
            date="2026-02-20",
            body="Body text here",
        )
        assert e.id == "10"
        assert e.to_addr == "to@x.com"
        assert e.body == "Body text here"

    def test_to_dict(self):
        e = FullEmail(
            id="10",
            subject="Full",
            from_addr="from@x.com",
            to_addr="to@x.com",
            date="2026-02-20",
            body="Body text",
        )
        d = e.to_dict()
        assert d == {
            "id": "10",
            "subject": "Full",
            "from_addr": "from@x.com",
            "to_addr": "to@x.com",
            "date": "2026-02-20",
            "body": "Body text",
        }

    def test_from_dict(self):
        data = {
            "id": "10",
            "subject": "Full",
            "from_addr": "from@x.com",
            "to_addr": "to@x.com",
            "date": "2026-02-20",
            "body": "Body text",
        }
        e = FullEmail.from_dict(data)
        assert e.id == "10"
        assert e.body == "Body text"

    def test_round_trip(self):
        original = FullEmail(
            id="20",
            subject="RT",
            from_addr="a@b.com",
            to_addr="c@d.com",
            date="2026-01-15",
            body="The full body",
        )
        assert FullEmail.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# EmailWithHtml
# ---------------------------------------------------------------------------


class TestEmailWithHtml:
    def test_construction_all_fields(self):
        e = EmailWithHtml(
            id="30",
            subject="HTML Email",
            from_addr="from@x.com",
            to_addr="to@x.com",
            date="2026-02-20",
            body="Plain body",
            html_body="<p>HTML body</p>",
            text_body="text body",
            list_unsubscribe="<https://unsub.example.com>",
            list_unsubscribe_post="List-Unsubscribe=One-Click",
        )
        assert e.html_body == "<p>HTML body</p>"
        assert e.list_unsubscribe == "<https://unsub.example.com>"
        assert e.list_unsubscribe_post == "List-Unsubscribe=One-Click"

    def test_default_optional_fields(self):
        e = EmailWithHtml(
            id="31",
            subject="Minimal HTML",
            from_addr="a@b.com",
            to_addr="c@d.com",
            date="2026-01-01",
            body="body",
        )
        assert e.html_body == ""
        assert e.text_body == ""
        assert e.list_unsubscribe == ""
        assert e.list_unsubscribe_post == ""

    def test_inherits_full_email(self):
        e = EmailWithHtml(
            id="30",
            subject="HTML",
            from_addr="a@b.com",
            to_addr="c@d.com",
            date="d",
            body="b",
        )
        assert isinstance(e, FullEmail)

    def test_to_dict_includes_parent_fields(self):
        e = EmailWithHtml(
            id="30",
            subject="HTML",
            from_addr="from@x.com",
            to_addr="to@x.com",
            date="2026-02-20",
            body="Plain body",
            html_body="<p>HTML</p>",
            text_body="text",
            list_unsubscribe="<https://unsub.example.com>",
            list_unsubscribe_post="One-Click",
        )
        d = e.to_dict()
        # Parent fields
        assert d["id"] == "30"
        assert d["subject"] == "HTML"
        assert d["from_addr"] == "from@x.com"
        assert d["to_addr"] == "to@x.com"
        assert d["date"] == "2026-02-20"
        assert d["body"] == "Plain body"
        # Child fields
        assert d["html_body"] == "<p>HTML</p>"
        assert d["text_body"] == "text"
        assert d["list_unsubscribe"] == "<https://unsub.example.com>"
        assert d["list_unsubscribe_post"] == "One-Click"

    def test_from_dict(self):
        data = {
            "id": "30",
            "subject": "HTML",
            "from_addr": "from@x.com",
            "to_addr": "to@x.com",
            "date": "2026-02-20",
            "body": "Plain body",
            "html_body": "<p>HTML</p>",
            "text_body": "text",
            "list_unsubscribe": "<https://unsub.example.com>",
            "list_unsubscribe_post": "One-Click",
        }
        e = EmailWithHtml.from_dict(data)
        assert isinstance(e, EmailWithHtml)
        assert e.html_body == "<p>HTML</p>"
        assert e.body == "Plain body"

    def test_from_dict_missing_optional(self):
        data = {
            "id": "31",
            "subject": "Minimal",
            "from_addr": "a@b.com",
            "to_addr": "c@d.com",
            "date": "d",
            "body": "b",
        }
        e = EmailWithHtml.from_dict(data)
        assert e.html_body == ""
        assert e.list_unsubscribe == ""

    def test_round_trip(self):
        original = EmailWithHtml(
            id="30",
            subject="HTML RT",
            from_addr="from@x.com",
            to_addr="to@x.com",
            date="2026-02-20",
            body="Plain body",
            html_body="<p>HTML</p>",
            text_body="text",
            list_unsubscribe="<https://unsub.example.com>",
            list_unsubscribe_post="One-Click",
        )
        assert EmailWithHtml.from_dict(original.to_dict()) == original

    def test_round_trip_defaults(self):
        original = EmailWithHtml(
            id="31",
            subject="Min",
            from_addr="a@b.com",
            to_addr="c@d.com",
            date="d",
            body="b",
        )
        assert EmailWithHtml.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# JunkAnalysis
# ---------------------------------------------------------------------------


class TestJunkAnalysis:
    def test_construction_all_fields(self):
        j = JunkAnalysis(
            is_likely_junk=True,
            junk_score=5,
            likelihood="high",
            indicators=["suspicious domain", "urgent language"],
            email_id="msg-42",
        )
        assert j.is_likely_junk is True
        assert j.junk_score == 5
        assert j.likelihood == "high"
        assert len(j.indicators) == 2
        assert j.email_id == "msg-42"

    def test_default_values(self):
        j = JunkAnalysis(is_likely_junk=False, junk_score=0, likelihood="unlikely")
        assert j.indicators == []
        assert j.email_id == ""

    def test_to_dict(self):
        j = JunkAnalysis(
            is_likely_junk=True,
            junk_score=3,
            likelihood="medium",
            indicators=["caps", "excl"],
            email_id="msg-1",
        )
        d = j.to_dict()
        assert d == {
            "is_likely_junk": True,
            "junk_score": 3,
            "likelihood": "medium",
            "indicators": ["caps", "excl"],
            "email_id": "msg-1",
        }

    def test_to_dict_copies_indicators(self):
        indicators = ["test"]
        j = JunkAnalysis(is_likely_junk=False, junk_score=0, likelihood="unlikely", indicators=indicators)
        d = j.to_dict()
        d["indicators"].append("mutated")
        assert j.indicators == ["test"]  # original not mutated

    def test_from_dict(self):
        data = {
            "is_likely_junk": True,
            "junk_score": 4,
            "likelihood": "high",
            "indicators": ["phishing"],
            "email_id": "x",
        }
        j = JunkAnalysis.from_dict(data)
        assert j.is_likely_junk is True
        assert j.indicators == ["phishing"]

    def test_from_dict_missing_optional(self):
        data = {
            "is_likely_junk": False,
            "junk_score": 0,
            "likelihood": "unlikely",
        }
        j = JunkAnalysis.from_dict(data)
        assert j.indicators == []
        assert j.email_id == ""

    def test_round_trip(self):
        original = JunkAnalysis(
            is_likely_junk=True,
            junk_score=6,
            likelihood="high",
            indicators=["crypto scam", "fake urgency"],
            email_id="msg-99",
        )
        assert JunkAnalysis.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# UnsubscribeMethod
# ---------------------------------------------------------------------------


class TestUnsubscribeMethod:
    def test_construction_all_fields(self):
        u = UnsubscribeMethod(
            type="http",
            method="one_click",
            url="https://unsub.example.com/abc",
            address="",
            source="header",
            one_click=True,
        )
        assert u.type == "http"
        assert u.one_click is True

    def test_default_values(self):
        u = UnsubscribeMethod(type="mailto", method="email")
        assert u.url == ""
        assert u.address == ""
        assert u.source == ""
        assert u.one_click is False

    def test_to_dict(self):
        u = UnsubscribeMethod(
            type="http",
            method="click",
            url="https://unsub.example.com",
            source="html_body",
        )
        d = u.to_dict()
        assert d["type"] == "http"
        assert d["url"] == "https://unsub.example.com"
        assert d["one_click"] is False

    def test_from_dict(self):
        data = {
            "type": "mailto",
            "method": "email",
            "address": "unsub@lists.example.com",
            "source": "header",
        }
        u = UnsubscribeMethod.from_dict(data)
        assert u.address == "unsub@lists.example.com"
        assert u.url == ""

    def test_round_trip(self):
        original = UnsubscribeMethod(
            type="http",
            method="one_click",
            url="https://unsub.example.com/xyz",
            address="",
            source="header",
            one_click=True,
        )
        assert UnsubscribeMethod.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# FilterRule
# ---------------------------------------------------------------------------


class TestFilterRule:
    def test_construction_all_fields(self):
        r = FilterRule(
            id="rule-1",
            name="GitHub Notifications",
            conditions={"from": "notifications@github.com"},
            actions={"move_to_folder": "GitHub"},
            enabled=True,
            created_at="2026-01-15T10:00:00Z",
            last_applied="2026-02-20T08:30:00Z",
            emails_processed=150,
        )
        assert r.id == "rule-1"
        assert r.emails_processed == 150

    def test_default_values(self):
        r = FilterRule(id="r1", name="Test Rule")
        assert r.conditions == {}
        assert r.actions == {}
        assert r.enabled is True
        assert r.created_at == ""
        assert r.last_applied is None
        assert r.emails_processed == 0

    def test_to_dict(self):
        r = FilterRule(
            id="rule-2",
            name="Spam Filter",
            conditions={"subject_contains": "buy now"},
            actions={"move_to_folder": "Spam", "mark_as_read": True},
            enabled=False,
            created_at="2026-01-01",
            last_applied=None,
            emails_processed=0,
        )
        d = r.to_dict()
        assert d["id"] == "rule-2"
        assert d["enabled"] is False
        assert d["last_applied"] is None
        assert d["conditions"] == {"subject_contains": "buy now"}

    def test_to_dict_copies_dicts(self):
        conditions = {"from": "x@y.com"}
        r = FilterRule(id="r", name="n", conditions=conditions)
        d = r.to_dict()
        d["conditions"]["from"] = "mutated"
        assert r.conditions["from"] == "x@y.com"

    def test_from_dict(self):
        data = {
            "id": "rule-3",
            "name": "VIP",
            "conditions": {"sender_domain": "important.com"},
            "actions": {"mark_as_important": True},
            "enabled": True,
            "created_at": "2026-02-01",
            "last_applied": "2026-02-20",
            "emails_processed": 42,
        }
        r = FilterRule.from_dict(data)
        assert r.name == "VIP"
        assert r.last_applied == "2026-02-20"

    def test_from_dict_missing_optional(self):
        data = {"id": "r1", "name": "Min"}
        r = FilterRule.from_dict(data)
        assert r.conditions == {}
        assert r.enabled is True
        assert r.last_applied is None
        assert r.emails_processed == 0

    def test_round_trip(self):
        original = FilterRule(
            id="rule-rt",
            name="Round Trip Rule",
            conditions={"from": "test@example.com", "subject_contains": "invoice"},
            actions={"move_to_folder": "Finance", "mark_as_important": True},
            enabled=True,
            created_at="2026-01-01",
            last_applied="2026-02-15",
            emails_processed=77,
        )
        assert FilterRule.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# JunkRule
# ---------------------------------------------------------------------------


class TestJunkRule:
    def test_construction_all_fields(self):
        r = JunkRule(
            id="junk-1",
            name="Crypto Spam",
            field="subject",
            pattern=r"bitcoin|crypto|blockchain",
            score=3,
            enabled=True,
        )
        assert r.field == "subject"
        assert r.score == 3

    def test_default_values(self):
        r = JunkRule(id="j1", name="Test", field="body", pattern=".*")
        assert r.score == 2
        assert r.enabled is True

    def test_to_dict(self):
        r = JunkRule(
            id="junk-2",
            name="Pharma",
            field="body",
            pattern=r"viagra|cialis",
            score=5,
            enabled=False,
        )
        d = r.to_dict()
        assert d == {
            "id": "junk-2",
            "name": "Pharma",
            "field": "body",
            "pattern": r"viagra|cialis",
            "score": 5,
            "enabled": False,
        }

    def test_from_dict(self):
        data = {
            "id": "junk-3",
            "name": "Lottery",
            "field": "subject",
            "pattern": r"winner|lottery|million",
            "score": 4,
            "enabled": True,
        }
        r = JunkRule.from_dict(data)
        assert r.name == "Lottery"
        assert r.score == 4

    def test_from_dict_missing_optional(self):
        data = {
            "id": "j1",
            "name": "Min",
            "field": "sender",
            "pattern": ".*@spam.com",
        }
        r = JunkRule.from_dict(data)
        assert r.score == 2
        assert r.enabled is True

    def test_round_trip(self):
        original = JunkRule(
            id="junk-rt",
            name="Round Trip",
            field="sender",
            pattern=r".*@suspicious\.(tk|ml|ga)",
            score=4,
            enabled=True,
        )
        assert JunkRule.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# JunkConfig
# ---------------------------------------------------------------------------


class TestJunkConfig:
    def test_construction_defaults(self):
        c = JunkConfig()
        assert c.schema_version == 1
        assert c.custom_patterns == []
        assert c.whitelist == {"domains": [], "senders": []}
        assert c.blacklist == {"domains": [], "senders": []}
        assert c.thresholds == {"low": 1, "medium": 2, "high": 4}

    def test_construction_with_patterns(self):
        rules = [
            JunkRule(id="j1", name="R1", field="subject", pattern="spam"),
            JunkRule(id="j2", name="R2", field="body", pattern="scam"),
        ]
        c = JunkConfig(custom_patterns=rules)
        assert len(c.custom_patterns) == 2
        assert c.custom_patterns[0].name == "R1"

    def test_to_dict(self):
        rules = [JunkRule(id="j1", name="R1", field="subject", pattern="spam")]
        c = JunkConfig(
            schema_version=2,
            custom_patterns=rules,
            whitelist={"domains": ["safe.com"], "senders": ["friend@x.com"]},
            blacklist={"domains": ["bad.tk"], "senders": []},
            thresholds={"low": 1, "medium": 3, "high": 5},
        )
        d = c.to_dict()
        assert d["schema_version"] == 2
        assert len(d["custom_patterns"]) == 1
        assert d["custom_patterns"][0]["id"] == "j1"
        assert isinstance(d["custom_patterns"][0], dict)
        assert d["whitelist"]["domains"] == ["safe.com"]
        assert d["thresholds"]["high"] == 5

    def test_to_dict_copies_lists(self):
        c = JunkConfig(whitelist={"domains": ["safe.com"], "senders": []})
        d = c.to_dict()
        d["whitelist"]["domains"].append("mutated.com")
        assert c.whitelist["domains"] == ["safe.com"]

    def test_from_dict_nested_deserialization(self):
        """JunkConfig.from_dict() must deserialize custom_patterns as JunkRule instances."""
        data = {
            "schema_version": 1,
            "custom_patterns": [
                {
                    "id": "j1",
                    "name": "Crypto",
                    "field": "subject",
                    "pattern": "bitcoin",
                    "score": 3,
                    "enabled": True,
                },
                {
                    "id": "j2",
                    "name": "Pharma",
                    "field": "body",
                    "pattern": "viagra",
                    "score": 5,
                    "enabled": False,
                },
            ],
            "whitelist": {"domains": [], "senders": []},
            "blacklist": {"domains": [], "senders": []},
            "thresholds": {"low": 1, "medium": 2, "high": 4},
        }
        c = JunkConfig.from_dict(data)
        assert len(c.custom_patterns) == 2
        assert isinstance(c.custom_patterns[0], JunkRule)
        assert isinstance(c.custom_patterns[1], JunkRule)
        assert c.custom_patterns[0].name == "Crypto"
        assert c.custom_patterns[1].score == 5
        assert c.custom_patterns[1].enabled is False

    def test_from_dict_missing_optional(self):
        data = {}
        c = JunkConfig.from_dict(data)
        assert c.schema_version == 1
        assert c.custom_patterns == []
        assert c.whitelist == {"domains": [], "senders": []}

    def test_round_trip(self):
        rules = [
            JunkRule(id="j1", name="R1", field="subject", pattern="spam", score=3),
            JunkRule(id="j2", name="R2", field="body", pattern="scam", score=5, enabled=False),
        ]
        original = JunkConfig(
            schema_version=2,
            custom_patterns=rules,
            whitelist={"domains": ["good.com"], "senders": ["alice@x.com"]},
            blacklist={"domains": ["bad.tk"], "senders": ["evil@y.com"]},
            thresholds={"low": 1, "medium": 3, "high": 6},
        )
        assert JunkConfig.from_dict(original.to_dict()) == original

    def test_round_trip_defaults(self):
        original = JunkConfig()
        assert JunkConfig.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# UnsubscribePreference
# ---------------------------------------------------------------------------


class TestUnsubscribePreference:
    def test_construction_all_fields(self):
        p = UnsubscribePreference(
            action="always_unsubscribe",
            domain="newsletters.example.com",
            sender="news@example.com",
        )
        assert p.action == "always_unsubscribe"
        assert p.domain == "newsletters.example.com"

    def test_default_values(self):
        p = UnsubscribePreference(action="never_unsubscribe")
        assert p.domain == ""
        assert p.sender == ""

    def test_to_dict(self):
        p = UnsubscribePreference(action="always_unsubscribe", domain="x.com")
        d = p.to_dict()
        assert d == {"action": "always_unsubscribe", "domain": "x.com", "sender": ""}

    def test_from_dict(self):
        data = {"action": "never_unsubscribe", "domain": "y.com", "sender": "s@y.com"}
        p = UnsubscribePreference.from_dict(data)
        assert p.sender == "s@y.com"

    def test_from_dict_missing_optional(self):
        data = {"action": "always_unsubscribe"}
        p = UnsubscribePreference.from_dict(data)
        assert p.domain == ""
        assert p.sender == ""

    def test_round_trip(self):
        original = UnsubscribePreference(
            action="always_unsubscribe",
            domain="newsletters.example.com",
            sender="news@example.com",
        )
        assert UnsubscribePreference.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# DetectionPattern
# ---------------------------------------------------------------------------


class TestDetectionPattern:
    def test_construction_all_fields(self):
        p = DetectionPattern(
            id="dp-1",
            name="Pixel Tracker",
            pattern=r"https://track\.example\.com/pixel",
            type="tracker_domain",
            enabled=True,
        )
        assert p.id == "dp-1"
        assert p.type == "tracker_domain"

    def test_default_values(self):
        p = DetectionPattern(id="dp-2", name="Test", pattern=".*")
        assert p.type == "tracker_domain"
        assert p.enabled is True

    def test_to_dict(self):
        p = DetectionPattern(
            id="dp-1",
            name="Pixel",
            pattern=r"track\.example\.com",
            type="tracking_pixel",
            enabled=False,
        )
        d = p.to_dict()
        assert d == {
            "id": "dp-1",
            "name": "Pixel",
            "pattern": r"track\.example\.com",
            "type": "tracking_pixel",
            "enabled": False,
        }

    def test_from_dict(self):
        data = {
            "id": "dp-3",
            "name": "Open Tracker",
            "pattern": r"opentrack\.com",
            "type": "open_tracking",
            "enabled": True,
        }
        p = DetectionPattern.from_dict(data)
        assert p.name == "Open Tracker"
        assert p.type == "open_tracking"

    def test_from_dict_missing_optional(self):
        data = {"id": "dp-4", "name": "Min", "pattern": ".*"}
        p = DetectionPattern.from_dict(data)
        assert p.type == "tracker_domain"
        assert p.enabled is True

    def test_round_trip(self):
        original = DetectionPattern(
            id="dp-rt",
            name="Round Trip",
            pattern=r"https://rt\.example\.com/.*",
            type="link_tracking",
            enabled=False,
        )
        assert DetectionPattern.from_dict(original.to_dict()) == original


# ---------------------------------------------------------------------------
# UnsubscribeHistoryEntry
# ---------------------------------------------------------------------------


class TestUnsubscribeHistoryEntry:
    def test_construction_all_fields(self):
        h = UnsubscribeHistoryEntry(
            sender="news@example.com",
            method="one_click",
            url="https://unsub.example.com/abc",
            date="2026-02-20T10:00:00Z",
            success=True,
        )
        assert h.sender == "news@example.com"
        assert h.success is True

    def test_to_dict(self):
        h = UnsubscribeHistoryEntry(
            sender="spam@bad.com",
            method="http",
            url="https://unsub.bad.com/123",
            date="2026-02-19",
            success=False,
        )
        d = h.to_dict()
        assert d == {
            "sender": "spam@bad.com",
            "method": "http",
            "url": "https://unsub.bad.com/123",
            "date": "2026-02-19",
            "success": False,
        }

    def test_from_dict(self):
        data = {
            "sender": "list@example.com",
            "method": "mailto",
            "url": "mailto:unsub@example.com",
            "date": "2026-01-01",
            "success": True,
        }
        h = UnsubscribeHistoryEntry.from_dict(data)
        assert h.method == "mailto"
        assert h.success is True

    def test_round_trip(self):
        original = UnsubscribeHistoryEntry(
            sender="weekly@digest.com",
            method="one_click",
            url="https://unsub.digest.com/one-click",
            date="2026-02-20T15:30:00Z",
            success=True,
        )
        assert UnsubscribeHistoryEntry.from_dict(original.to_dict()) == original
