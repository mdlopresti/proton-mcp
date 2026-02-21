"""Email and configuration data models.

All models are dataclasses with to_dict() and from_dict() methods
for JSON serialization. These contracts define the interfaces that
all services must use.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any


@dataclass
class EmailSummary:
    id: str
    subject: str
    from_addr: str
    date: str
    body_preview: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "from_addr": self.from_addr,
            "date": self.date,
            "body_preview": self.body_preview,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmailSummary:
        return cls(
            id=data["id"],
            subject=data["subject"],
            from_addr=data["from_addr"],
            date=data["date"],
            body_preview=data.get("body_preview", ""),
        )


@dataclass
class FullEmail:
    id: str
    subject: str
    from_addr: str
    to_addr: str
    date: str
    body: str

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "subject": self.subject,
            "from_addr": self.from_addr,
            "to_addr": self.to_addr,
            "date": self.date,
            "body": self.body,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FullEmail:
        return cls(
            id=data["id"],
            subject=data["subject"],
            from_addr=data["from_addr"],
            to_addr=data["to_addr"],
            date=data["date"],
            body=data["body"],
        )


@dataclass
class EmailWithHtml(FullEmail):
    html_body: str = ""
    text_body: str = ""
    list_unsubscribe: str = ""
    list_unsubscribe_post: str = ""

    def to_dict(self) -> dict[str, Any]:
        d = super().to_dict()
        d["html_body"] = self.html_body
        d["text_body"] = self.text_body
        d["list_unsubscribe"] = self.list_unsubscribe
        d["list_unsubscribe_post"] = self.list_unsubscribe_post
        return d

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmailWithHtml:
        return cls(
            id=data["id"],
            subject=data["subject"],
            from_addr=data["from_addr"],
            to_addr=data["to_addr"],
            date=data["date"],
            body=data["body"],
            html_body=data.get("html_body", ""),
            text_body=data.get("text_body", ""),
            list_unsubscribe=data.get("list_unsubscribe", ""),
            list_unsubscribe_post=data.get("list_unsubscribe_post", ""),
        )


@dataclass
class JunkAnalysis:
    is_likely_junk: bool
    junk_score: int
    likelihood: str  # "unlikely", "low", "medium", "high"
    indicators: list[str] = field(default_factory=list)
    email_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "is_likely_junk": self.is_likely_junk,
            "junk_score": self.junk_score,
            "likelihood": self.likelihood,
            "indicators": list(self.indicators),
            "email_id": self.email_id,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JunkAnalysis:
        return cls(
            is_likely_junk=data["is_likely_junk"],
            junk_score=data["junk_score"],
            likelihood=data["likelihood"],
            indicators=data.get("indicators", []),
            email_id=data.get("email_id", ""),
        )


@dataclass
class UnsubscribeMethod:
    type: str  # "http", "mailto"
    method: str  # "click", "one_click", "email"
    url: str = ""
    address: str = ""
    source: str = ""  # "header", "html_body", "text_body"
    one_click: bool = False

    def to_dict(self) -> dict[str, Any]:
        return {
            "type": self.type,
            "method": self.method,
            "url": self.url,
            "address": self.address,
            "source": self.source,
            "one_click": self.one_click,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnsubscribeMethod:
        return cls(
            type=data["type"],
            method=data["method"],
            url=data.get("url", ""),
            address=data.get("address", ""),
            source=data.get("source", ""),
            one_click=data.get("one_click", False),
        )


@dataclass
class FilterRule:
    id: str
    name: str
    conditions: dict[str, Any] = field(default_factory=dict)
    actions: dict[str, Any] = field(default_factory=dict)
    enabled: bool = True
    created_at: str = ""
    last_applied: str | None = None
    emails_processed: int = 0

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "conditions": dict(self.conditions),
            "actions": dict(self.actions),
            "enabled": self.enabled,
            "created_at": self.created_at,
            "last_applied": self.last_applied,
            "emails_processed": self.emails_processed,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilterRule:
        return cls(
            id=data["id"],
            name=data["name"],
            conditions=data.get("conditions", {}),
            actions=data.get("actions", {}),
            enabled=data.get("enabled", True),
            created_at=data.get("created_at", ""),
            last_applied=data.get("last_applied"),
            emails_processed=data.get("emails_processed", 0),
        )


@dataclass
class JunkRule:
    id: str
    name: str
    field: str  # "subject", "sender", "body"
    pattern: str  # regex pattern
    score: int = 2
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "field": self.field,
            "pattern": self.pattern,
            "score": self.score,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JunkRule:
        return cls(
            id=data["id"],
            name=data["name"],
            field=data["field"],
            pattern=data["pattern"],
            score=data.get("score", 2),
            enabled=data.get("enabled", True),
        )


@dataclass
class JunkConfig:
    schema_version: int = 1
    custom_patterns: list[JunkRule] = field(default_factory=list)
    whitelist: dict[str, list[str]] = field(default_factory=lambda: {"domains": [], "senders": []})
    blacklist: dict[str, list[str]] = field(default_factory=lambda: {"domains": [], "senders": []})
    thresholds: dict[str, int] = field(default_factory=lambda: {"low": 1, "medium": 2, "high": 4})

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema_version": self.schema_version,
            "custom_patterns": [p.to_dict() for p in self.custom_patterns],
            "whitelist": {k: list(v) for k, v in self.whitelist.items()},
            "blacklist": {k: list(v) for k, v in self.blacklist.items()},
            "thresholds": dict(self.thresholds),
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JunkConfig:
        raw_patterns = data.get("custom_patterns", [])
        patterns = [JunkRule.from_dict(p) if isinstance(p, dict) else p for p in raw_patterns]
        return cls(
            schema_version=data.get("schema_version", 1),
            custom_patterns=patterns,
            whitelist=data.get("whitelist", {"domains": [], "senders": []}),
            blacklist=data.get("blacklist", {"domains": [], "senders": []}),
            thresholds=data.get("thresholds", {"low": 1, "medium": 2, "high": 4}),
        )


@dataclass
class UnsubscribePreference:
    action: str  # "always_unsubscribe", "never_unsubscribe"
    domain: str = ""
    sender: str = ""

    def to_dict(self) -> dict[str, Any]:
        return {
            "action": self.action,
            "domain": self.domain,
            "sender": self.sender,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnsubscribePreference:
        return cls(
            action=data["action"],
            domain=data.get("domain", ""),
            sender=data.get("sender", ""),
        )


@dataclass
class DetectionPattern:
    id: str
    name: str
    pattern: str  # regex pattern
    type: str = "tracker_domain"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        return {
            "id": self.id,
            "name": self.name,
            "pattern": self.pattern,
            "type": self.type,
            "enabled": self.enabled,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectionPattern:
        return cls(
            id=data["id"],
            name=data["name"],
            pattern=data["pattern"],
            type=data.get("type", "tracker_domain"),
            enabled=data.get("enabled", True),
        )


@dataclass
class UnsubscribeHistoryEntry:
    sender: str
    method: str  # "one_click", "http", "mailto"
    url: str
    date: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        return {
            "sender": self.sender,
            "method": self.method,
            "url": self.url,
            "date": self.date,
            "success": self.success,
        }

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnsubscribeHistoryEntry:
        return cls(
            sender=data["sender"],
            method=data["method"],
            url=data["url"],
            date=data["date"],
            success=data["success"],
        )
