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
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> EmailSummary:
        raise NotImplementedError


@dataclass
class FullEmail:
    id: str
    subject: str
    from_addr: str
    to_addr: str
    date: str
    body: str

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FullEmail:
        raise NotImplementedError


@dataclass
class EmailWithHtml(FullEmail):
    html_body: str = ""
    text_body: str = ""
    list_unsubscribe: str = ""
    list_unsubscribe_post: str = ""


@dataclass
class JunkAnalysis:
    is_likely_junk: bool
    junk_score: int
    likelihood: str  # "unlikely", "low", "medium", "high"
    indicators: list[str] = field(default_factory=list)
    email_id: str = ""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


@dataclass
class UnsubscribeMethod:
    type: str  # "http", "mailto"
    method: str  # "click", "one_click", "email"
    url: str = ""
    address: str = ""
    source: str = ""  # "header", "html_body", "text_body"
    one_click: bool = False

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError


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
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> FilterRule:
        raise NotImplementedError


@dataclass
class JunkRule:
    id: str
    name: str
    field: str  # "subject", "sender", "body"
    pattern: str  # regex pattern
    score: int = 2
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JunkRule:
        raise NotImplementedError


@dataclass
class JunkConfig:
    schema_version: int = 1
    custom_patterns: list[JunkRule] = field(default_factory=list)
    whitelist: dict[str, list[str]] = field(default_factory=lambda: {"domains": [], "senders": []})
    blacklist: dict[str, list[str]] = field(default_factory=lambda: {"domains": [], "senders": []})
    thresholds: dict[str, int] = field(default_factory=lambda: {"low": 1, "medium": 2, "high": 4})

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> JunkConfig:
        raise NotImplementedError


@dataclass
class UnsubscribePreference:
    action: str  # "always_unsubscribe", "never_unsubscribe"
    domain: str = ""
    sender: str = ""

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnsubscribePreference:
        raise NotImplementedError


@dataclass
class DetectionPattern:
    id: str
    name: str
    pattern: str  # regex pattern
    type: str = "tracker_domain"
    enabled: bool = True

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> DetectionPattern:
        raise NotImplementedError


@dataclass
class UnsubscribeHistoryEntry:
    sender: str
    method: str  # "one_click", "http", "mailto"
    url: str
    date: str
    success: bool

    def to_dict(self) -> dict[str, Any]:
        raise NotImplementedError

    @classmethod
    def from_dict(cls, data: dict[str, Any]) -> UnsubscribeHistoryEntry:
        raise NotImplementedError
