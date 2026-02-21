"""Unsubscribe detection and execution service with persistent configuration."""

from __future__ import annotations

import logging
import os
import re
import uuid
from datetime import datetime, timezone
from html.parser import HTMLParser
from typing import Any

import requests

from proton_mcp.config import Config
from proton_mcp.models.email import (
    DetectionPattern,
    UnsubscribeHistoryEntry,
    UnsubscribeMethod,
    UnsubscribePreference,
)
from proton_mcp.utils.json_store import JsonStore
from proton_mcp.utils.url_safety import is_safe_url

logger = logging.getLogger(__name__)

# Anchor text patterns that indicate an unsubscribe link
_UNSUB_TEXT_PATTERNS = [
    re.compile(r"unsubscribe", re.IGNORECASE),
    re.compile(r"opt[\s-]?out", re.IGNORECASE),
    re.compile(r"no longer receive", re.IGNORECASE),
    re.compile(r"manage[\s-]?preferences", re.IGNORECASE),
    re.compile(r"email[\s-]?preferences", re.IGNORECASE),
]

# Contextual patterns: "click here" or "here" near "unsubscribe" text
_CONTEXT_CLICK_PATTERNS = [
    re.compile(r"click\s+here", re.IGNORECASE),
    re.compile(r"^here$", re.IGNORECASE),
]

# Default detection patterns for tracker domains
_DEFAULT_DETECTION_PATTERNS = [
    {
        "id": "builtin-klaviyo",
        "name": "Klaviyo tracker",
        "pattern": r"ctrk\.klclick\.com",
        "type": "tracker_domain",
        "enabled": True,
    },
    {
        "id": "builtin-sendgrid",
        "name": "SendGrid tracker",
        "pattern": r"ct\.sendgrid\.net",
        "type": "tracker_domain",
        "enabled": True,
    },
    {
        "id": "builtin-mailchimp",
        "name": "Mailchimp tracker",
        "pattern": r"list-manage\.com",
        "type": "tracker_domain",
        "enabled": True,
    },
]

_DEFAULT_CONFIG = {
    "schema_version": 1,
    "sender_preferences": [],
    "detection_patterns": list(_DEFAULT_DETECTION_PATTERNS),
    "history": [],
}

# Browser-like headers for HTTP requests
_BROWSER_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
    "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "en-US,en;q=0.5",
    "Accept-Encoding": "gzip, deflate",
    "Connection": "keep-alive",
}


class _UnsubscribeLinkParser(HTMLParser):
    """HTML parser that extracts links whose anchor text or surrounding context
    suggests an unsubscribe action.

    Uses a two-pass approach:
    1. First pass collects all links and all text content.
    2. After parsing, resolves context-dependent links (tracker URLs, "click here")
       using the full document text, so text after a link is also considered.

    Also detects tracker-wrapped URLs using configurable detection patterns.
    """

    def __init__(self, detection_patterns: list[DetectionPattern] | None = None) -> None:
        super().__init__()
        self.links: list[dict[str, str]] = []
        self._current_href: str | None = None
        self._current_text_parts: list[str] = []
        self._in_anchor = False
        self._detection_patterns = detection_patterns or []
        # Collect ALL links and text for two-pass resolution
        self._all_links: list[dict[str, Any]] = []  # href, anchor_text, confirmed
        self._all_text_parts: list[str] = []  # all text in document order

    def handle_starttag(self, tag: str, attrs: list[tuple[str, str | None]]) -> None:
        if tag == "a":
            self._in_anchor = True
            self._current_text_parts = []
            href = None
            for name, value in attrs:
                if name == "href" and value:
                    href = value
            self._current_href = href

    def handle_endtag(self, tag: str) -> None:
        if tag == "a" and self._in_anchor:
            self._in_anchor = False
            anchor_text = " ".join(self._current_text_parts).strip()
            href = self._current_href

            if href and href.startswith("http"):
                confirmed = False

                # Check if anchor text directly matches unsubscribe patterns
                for pat in _UNSUB_TEXT_PATTERNS:
                    if pat.search(anchor_text):
                        confirmed = True
                        break

                self._all_links.append({
                    "url": href,
                    "text": anchor_text,
                    "confirmed": confirmed,
                })

            self._current_href = None
            self._current_text_parts = []

    def handle_data(self, data: str) -> None:
        text = data.strip()
        if self._in_anchor:
            self._current_text_parts.append(text)
        if text:
            self._all_text_parts.append(text)

    def resolve(self) -> None:
        """Second pass: resolve context-dependent links using full document text.

        Called after feed() completes. Checks "click here"/"here" anchors and
        tracker-wrapped URLs against the full document text for unsubscribe context.
        """
        full_text = " ".join(self._all_text_parts)
        has_unsub_context = bool(re.search(r"unsubscrib", full_text, re.IGNORECASE))

        for link_info in self._all_links:
            if link_info["confirmed"]:
                self.links.append({"url": link_info["url"], "text": link_info["text"]})
                continue

            anchor_text = link_info["text"]
            href = link_info["url"]

            # Check if anchor text is "click here" or "here" near unsubscribe context
            for ctx_pat in _CONTEXT_CLICK_PATTERNS:
                if ctx_pat.search(anchor_text) and has_unsub_context:
                    link_info["confirmed"] = True
                    self.links.append({"url": href, "text": anchor_text})
                    break

            if link_info["confirmed"]:
                continue

            # Check if URL matches tracker patterns (these wrap real unsub links)
            for dp in self._detection_patterns:
                if dp.enabled:
                    try:
                        if re.search(dp.pattern, href) and has_unsub_context:
                            link_info["confirmed"] = True
                            self.links.append({"url": href, "text": anchor_text})
                            break
                    except re.error:
                        pass


class UnsubscribeService:
    """Unsubscribe detection and execution with persistent config.

    Uses JsonStore for config persistence. Supports:
    - RFC 2369 List-Unsubscribe header parsing
    - RFC 8058 One-Click unsubscribe
    - HTML body link detection (including tracker-wrapped URLs)
    - Text body pattern matching
    - Sender preferences (always/never unsubscribe)
    - Detection patterns (configurable tracker domains)
    - History logging of unsubscribe attempts
    """

    def __init__(self, config: Config) -> None:
        config_path = os.path.join(config.data_dir, "unsubscribe_config.json")
        self._store = JsonStore(
            file_path=config_path,
            schema_version=1,
            default_data=dict(_DEFAULT_CONFIG),
        )
        # Load on init to ensure the file exists with defaults
        self._store.load()

    def load_config(self) -> dict[str, Any]:
        """Load unsubscribe config from JSON store."""
        return self._store.load()

    def save_config(self, config_data: dict[str, Any]) -> None:
        """Save unsubscribe config to JSON store."""
        self._store.save(config_data)

    def _get_detection_patterns(self) -> list[DetectionPattern]:
        """Load detection patterns from config as model objects."""
        data = self.load_config()
        return [DetectionPattern.from_dict(p) for p in data.get("detection_patterns", [])]

    def find_unsubscribe_links(self, email_data: dict[str, Any]) -> list[UnsubscribeMethod]:
        """Find all unsubscribe methods in an email.

        Checks: RFC 2369 headers, RFC 8058 one-click, HTML body, text body.
        Deduplicates results and validates URLs for safety.
        """
        methods: list[UnsubscribeMethod] = []

        # 1. RFC 2369 List-Unsubscribe header
        list_unsubscribe = email_data.get("list_unsubscribe", "")
        if list_unsubscribe:
            # Parse mailto: URLs
            mailto_matches = re.findall(r"<mailto:([^>]+)>", list_unsubscribe)
            for mailto in mailto_matches:
                methods.append(
                    UnsubscribeMethod(
                        type="mailto",
                        method="email",
                        address=mailto,
                        source="header",
                    )
                )

            # Parse http/https URLs
            http_matches = re.findall(r"<(https?://[^>]+)>", list_unsubscribe)
            for url in http_matches:
                methods.append(
                    UnsubscribeMethod(
                        type="http",
                        method="click",
                        url=url,
                        source="header",
                    )
                )

        # 2. RFC 8058 One-Click unsubscribe
        list_unsubscribe_post = email_data.get("list_unsubscribe_post", "")
        if list_unsubscribe_post and "List-Unsubscribe=One-Click" in list_unsubscribe_post:
            for m in methods:
                if m.type == "http" and m.source == "header":
                    m.one_click = True
                    m.method = "one_click"

        # 3. HTML body analysis
        html_body = email_data.get("html_body", "")
        if html_body:
            detection_patterns = self._get_detection_patterns()
            parser = _UnsubscribeLinkParser(detection_patterns)
            try:
                parser.feed(html_body)
                parser.resolve()
            except Exception:
                logger.debug("Failed to parse HTML body for unsubscribe links")

            for link in parser.links:
                url = link["url"]
                methods.append(
                    UnsubscribeMethod(
                        type="http",
                        method="click",
                        url=url,
                        source="html_body",
                    )
                )

        # 4. Text body pattern matching
        text_body = email_data.get("body", "") or email_data.get("text_body", "")
        if text_body:
            # Look for URLs near unsubscribe-related text
            text_unsub_patterns = [
                r"(?i)unsubscribe.*?(https?://[^\s<>\"]+)",
                r"(?i)(https?://[^\s<>\"]*unsubscribe[^\s<>\"]*)",
                r"(?i)(https?://[^\s<>\"]*opt.?out[^\s<>\"]*)",
            ]
            for pattern in text_unsub_patterns:
                matches = re.findall(pattern, text_body)
                for match in matches:
                    # match might be a group or a full match
                    url = match if isinstance(match, str) else match[0]
                    if url.startswith("http"):
                        methods.append(
                            UnsubscribeMethod(
                                type="http",
                                method="click",
                                url=url,
                                source="text_body",
                            )
                        )

        # 5. Deduplicate by URL/address
        seen: set[str] = set()
        unique: list[UnsubscribeMethod] = []
        for m in methods:
            identifier = m.url or m.address
            if identifier and identifier not in seen:
                seen.add(identifier)
                unique.append(m)

        # 6. Validate URLs with is_safe_url — reject unsafe ones
        safe: list[UnsubscribeMethod] = []
        for m in unique:
            if m.type == "mailto":
                safe.append(m)
            elif m.url and is_safe_url(m.url):
                safe.append(m)
            else:
                logger.warning("Rejected unsafe unsubscribe URL: %s", m.url)

        return safe

    def execute_unsubscribe(self, method: UnsubscribeMethod) -> bool:
        """Execute an unsubscribe action. Logs attempt to history.

        Supports HTTP GET/POST and one-click unsubscribe.
        Uses url_safety for SSRF protection.
        """
        if method.type == "mailto":
            logger.info("Mailto unsubscribe not supported for automated execution")
            return False

        url = method.url
        if not url or not is_safe_url(url):
            logger.warning("Blocked unsafe unsubscribe URL: %s", url)
            return False

        headers = dict(_BROWSER_HEADERS)
        success = False

        try:
            if method.one_click:
                # RFC 8058 one-click unsubscribe
                headers["List-Unsubscribe"] = "One-Click"
                response = requests.post(  # noqa: S113
                    url, headers=headers, timeout=30, allow_redirects=True
                )
            else:
                # Regular HTTP GET
                response = requests.get(  # noqa: S113
                    url, headers=headers, timeout=30, allow_redirects=True
                )

            success = response.status_code < 400

        except requests.exceptions.Timeout:
            logger.warning("Unsubscribe request timed out: %s", url)
        except requests.exceptions.ConnectionError:
            logger.warning("Connection error for unsubscribe URL: %s", url)
        except requests.exceptions.RequestException as e:
            logger.warning("Unsubscribe request failed: %s", e)

        # Log the attempt
        sender = ""  # Caller can provide sender context externally
        self.log_attempt(sender=sender, method=method.method, url=url, success=success)

        return success

    def get_sender_preference(self, sender: str) -> UnsubscribePreference | None:
        """Get unsubscribe preference for a sender/domain."""
        data = self.load_config()
        sender_lower = sender.lower()
        for pref_data in data.get("sender_preferences", []):
            pref = UnsubscribePreference.from_dict(pref_data)
            if pref.sender and pref.sender.lower() == sender_lower:
                return pref
            if pref.domain and sender_lower.endswith("@" + pref.domain.lower()):
                return pref
            if pref.domain and pref.domain.lower() == sender_lower:
                return pref
        return None

    def add_sender_preference(self, sender: str, action: str, domain: str = "") -> bool:
        """Add a sender preference (always_unsubscribe or never_unsubscribe)."""
        data = self.load_config()
        prefs = data.get("sender_preferences", [])

        # Check for duplicate
        for p in prefs:
            if p.get("sender", "").lower() == sender.lower() and p.get("domain", "").lower() == domain.lower():
                return False

        new_pref = UnsubscribePreference(action=action, domain=domain, sender=sender)
        prefs.append(new_pref.to_dict())
        data["sender_preferences"] = prefs
        self.save_config(data)
        return True

    def remove_sender_preference(self, sender: str) -> bool:
        """Remove a sender preference."""
        data = self.load_config()
        prefs = data.get("sender_preferences", [])
        sender_lower = sender.lower()

        original_len = len(prefs)
        prefs = [
            p
            for p in prefs
            if not (
                p.get("sender", "").lower() == sender_lower
                or p.get("domain", "").lower() == sender_lower
            )
        ]

        if len(prefs) == original_len:
            return False

        data["sender_preferences"] = prefs
        self.save_config(data)
        return True

    def add_detection_pattern(
        self, name: str, pattern: str, pattern_type: str = "tracker_domain", enabled: bool = True
    ) -> DetectionPattern:
        """Add a detection pattern for tracker URLs."""
        data = self.load_config()
        patterns = data.get("detection_patterns", [])

        pattern_id = f"custom-{uuid.uuid4().hex[:8]}"
        new_pattern = DetectionPattern(
            id=pattern_id,
            name=name,
            pattern=pattern,
            type=pattern_type,
            enabled=enabled,
        )
        patterns.append(new_pattern.to_dict())
        data["detection_patterns"] = patterns
        self.save_config(data)
        return new_pattern

    def remove_detection_pattern(self, pattern_id: str) -> bool:
        """Remove a detection pattern by ID."""
        data = self.load_config()
        patterns = data.get("detection_patterns", [])

        original_len = len(patterns)
        patterns = [p for p in patterns if p.get("id") != pattern_id]

        if len(patterns) == original_len:
            return False

        data["detection_patterns"] = patterns
        self.save_config(data)
        return True

    def get_history(self) -> list[UnsubscribeHistoryEntry]:
        """Get unsubscribe attempt history."""
        data = self.load_config()
        return [UnsubscribeHistoryEntry.from_dict(h) for h in data.get("history", [])]

    def log_attempt(self, sender: str, method: str, url: str, success: bool) -> None:
        """Log an unsubscribe attempt to history."""
        data = self.load_config()
        history = data.get("history", [])

        entry = UnsubscribeHistoryEntry(
            sender=sender,
            method=method,
            url=url,
            date=datetime.now(timezone.utc).strftime("%Y-%m-%d"),
            success=success,
        )
        history.append(entry.to_dict())
        data["history"] = history
        self.save_config(data)

    def check_resubscribe(self, sender: str) -> bool:
        """Check if a sender in history is still sending (re-subscribed).

        Returns True if the sender was previously successfully unsubscribed
        (has a success=True entry in history), meaning they may have
        re-subscribed since we're seeing their emails again.
        """
        history = self.get_history()
        sender_lower = sender.lower()
        for entry in history:
            if entry.sender.lower() == sender_lower and entry.success:
                return True
        return False
