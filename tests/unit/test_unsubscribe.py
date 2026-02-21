"""Comprehensive tests for the UnsubscribeService.

Covers:
- RFC 2369 header parsing (mailto, https, multiple URLs, malformed)
- RFC 8058 one-click detection
- HTML body detection (anchor text, tracker-wrapped URLs, edge cases)
- Text body detection (URL near unsubscribe text, no false positives)
- SSRF protection (localhost, private IPs)
- Deduplication (same URL from multiple sources, different URLs preserved)
- execute_unsubscribe (GET, POST one-click, failures, unsafe URL rejection)
- Sender preference CRUD (add, get, remove, persistence)
- History logging (log attempt, get history, persistence)
- Detection pattern CRUD (built-in patterns, add, remove)
- BUG FIX: anchor-text-based detection, tracker-wrapped URLs
"""

from __future__ import annotations

import json
import os
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from proton_mcp.models.email import (
    DetectionPattern,
    UnsubscribeHistoryEntry,
    UnsubscribeMethod,
)
from proton_mcp.services.unsubscribe import UnsubscribeService

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _make_email(
    list_unsubscribe: str = "",
    list_unsubscribe_post: str = "",
    html_body: str = "",
    text_body: str = "",
    body: str = "",
    subject: str = "Test Email",
    from_addr: str = "sender@example.com",
    email_id: str = "1",
) -> dict:
    return {
        "id": email_id,
        "subject": subject,
        "from": from_addr,
        "list_unsubscribe": list_unsubscribe,
        "list_unsubscribe_post": list_unsubscribe_post,
        "html_body": html_body,
        "text_body": text_body,
        "body": body,
    }


def _read_fixture_html(fixtures_dir: Path, filename: str) -> str:
    return (fixtures_dir / "sample_html" / filename).read_text()


# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def service(mock_config) -> UnsubscribeService:
    """Fresh UnsubscribeService with default config in a temp directory."""
    return UnsubscribeService(mock_config)


@pytest.fixture
def service_with_sample(mock_config, fixtures_dir) -> UnsubscribeService:
    """UnsubscribeService pre-loaded with the sample config fixture."""
    src = fixtures_dir / "sample_unsubscribe_config.json"
    dst = Path(mock_config.data_dir) / "unsubscribe_config.json"
    dst.write_text(src.read_text())
    return UnsubscribeService(mock_config)


# ===================================================================
# 1. RFC 2369 header parsing
# ===================================================================


class TestRFC2369HeaderParsing:
    """Parse List-Unsubscribe headers per RFC 2369."""

    def test_parse_mailto_url(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<mailto:unsub@example.com>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert methods[0].type == "mailto"
        assert methods[0].method == "email"
        assert methods[0].address == "unsub@example.com"
        assert methods[0].source == "header"

    def test_parse_https_url(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://example.com/unsubscribe?id=123>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert methods[0].type == "http"
        assert methods[0].method == "click"
        assert methods[0].url == "https://example.com/unsubscribe?id=123"
        assert methods[0].source == "header"

    def test_parse_multiple_urls(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe=("<mailto:unsub@example.com>, <https://example.com/unsub>"))
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 2
        types = {m.type for m in methods}
        assert "mailto" in types
        assert "http" in types

    def test_malformed_header_graceful(self, service: UnsubscribeService):
        """Malformed header (no angle brackets) should not crash."""
        email = _make_email(list_unsubscribe="not a valid header value")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_empty_header(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_http_url_from_header(self, service: UnsubscribeService):
        """Also handle plain http:// URLs (not just https)."""
        email = _make_email(list_unsubscribe="<http://example.com/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert methods[0].url == "http://example.com/unsub"


# ===================================================================
# 2. RFC 8058 one-click detection
# ===================================================================


class TestRFC8058OneClick:
    """Detect one-click unsubscribe via List-Unsubscribe-Post header."""

    def test_one_click_detected(self, service: UnsubscribeService):
        email = _make_email(
            list_unsubscribe="<https://example.com/unsub>",
            list_unsubscribe_post="List-Unsubscribe=One-Click",
        )
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert methods[0].one_click is True
        assert methods[0].method == "one_click"

    def test_no_one_click_without_post_header(self, service: UnsubscribeService):
        email = _make_email(
            list_unsubscribe="<https://example.com/unsub>",
            list_unsubscribe_post="",
        )
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert methods[0].one_click is False
        assert methods[0].method == "click"

    def test_one_click_only_applies_to_http_header_methods(self, service: UnsubscribeService):
        """One-click should only mark HTTP methods from headers, not mailto."""
        email = _make_email(
            list_unsubscribe="<mailto:unsub@example.com>, <https://example.com/unsub>",
            list_unsubscribe_post="List-Unsubscribe=One-Click",
        )
        methods = service.find_unsubscribe_links(email)
        mailto = [m for m in methods if m.type == "mailto"]
        http = [m for m in methods if m.type == "http"]
        assert len(mailto) == 1
        assert mailto[0].one_click is False
        assert len(http) == 1
        assert http[0].one_click is True


# ===================================================================
# 3. HTML body detection
# ===================================================================


class TestHTMLBodyDetection:
    """Detect unsubscribe links in HTML email bodies."""

    def test_detect_unsubscribe_anchor_text(self, service: UnsubscribeService):
        html = '<p>Don\'t want these? <a href="https://example.com/unsub">Unsubscribe</a></p>'
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any(m.url == "https://example.com/unsub" for m in http_methods)

    def test_detect_opt_out_anchor_text(self, service: UnsubscribeService):
        html = '<p><a href="https://example.com/optout">Opt Out</a></p>'
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any(m.url == "https://example.com/optout" for m in http_methods)

    def test_detect_manage_preferences(self, service: UnsubscribeService):
        html = '<p><a href="https://example.com/prefs">Manage Preferences</a></p>'
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1

    def test_detect_klaviyo_tracker_wrapped_link(self, service: UnsubscribeService, fixtures_dir):
        """BUG FIX: Detect Klaviyo tracker-wrapped unsubscribe link."""
        html = _read_fixture_html(fixtures_dir, "klaviyo_unsub.html")
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any("klclick.com" in m.url for m in http_methods)

    def test_detect_sendgrid_tracker_wrapped_link(self, service: UnsubscribeService, fixtures_dir):
        """BUG FIX: Detect SendGrid tracker-wrapped unsubscribe link."""
        html = _read_fixture_html(fixtures_dir, "sendgrid_unsub.html")
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any("sendgrid.net" in m.url for m in http_methods)

    def test_detect_rfc2369_html_link(self, service: UnsubscribeService, fixtures_dir):
        """Standard HTML unsubscribe link with 'Unsubscribe' anchor text."""
        html = _read_fixture_html(fixtures_dir, "rfc2369_unsub.html")
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any("lists.example.com" in m.url for m in http_methods)

    def test_skip_non_unsubscribe_links(self, service: UnsubscribeService):
        html = """
        <p><a href="https://example.com/home">Visit our website</a></p>
        <p><a href="https://example.com/shop">Shop now</a></p>
        """
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) == 0

    def test_handle_html_without_unsubscribe_links(self, service: UnsubscribeService):
        html = "<p>Just a regular email with no links at all.</p>"
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_detect_click_here_near_unsubscribe(self, service: UnsubscribeService):
        """BUG FIX: 'click here' anchor text near 'unsubscribe' context."""
        html = """
        <p>If you'd like to unsubscribe,
        <a href="https://example.com/unsub/abc">click here</a>.</p>
        """
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any(m.url == "https://example.com/unsub/abc" for m in http_methods)

    def test_detect_here_near_unsubscribe(self, service: UnsubscribeService):
        """BUG FIX: bare 'here' anchor text near 'unsubscribe' context."""
        html = """
        <p>To unsubscribe from this mailing list, click
        <a href="https://example.com/unsub/xyz">here</a>.</p>
        """
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1


# ===================================================================
# 4. Text body detection
# ===================================================================


class TestTextBodyDetection:
    """Find unsubscribe URLs in plain text email bodies."""

    def test_find_url_near_unsubscribe_text(self, service: UnsubscribeService):
        text = "To unsubscribe, visit https://example.com/unsub/123"
        email = _make_email(body=text)
        methods = service.find_unsubscribe_links(email)
        text_methods = [m for m in methods if m.source == "text_body"]
        assert len(text_methods) >= 1
        assert any("example.com/unsub" in m.url for m in text_methods)

    def test_no_false_positives_in_text(self, service: UnsubscribeService):
        text = "Check out our website at https://example.com/products for great deals!"
        email = _make_email(body=text)
        methods = service.find_unsubscribe_links(email)
        text_methods = [m for m in methods if m.source == "text_body"]
        assert len(text_methods) == 0

    def test_text_body_via_text_body_key(self, service: UnsubscribeService):
        """Should also check text_body key (not just body)."""
        email = _make_email(text_body="Unsubscribe here: https://example.com/unsub/text")
        methods = service.find_unsubscribe_links(email)
        text_methods = [m for m in methods if m.source == "text_body"]
        assert len(text_methods) >= 1

    def test_opt_out_url_in_text(self, service: UnsubscribeService):
        text = "Visit https://example.com/opt-out to stop these emails."
        email = _make_email(body=text)
        methods = service.find_unsubscribe_links(email)
        text_methods = [m for m in methods if m.source == "text_body"]
        assert len(text_methods) >= 1


# ===================================================================
# 5. SSRF protection
# ===================================================================


class TestSSRFProtection:
    """URLs targeting internal networks should be rejected."""

    def test_reject_localhost_url(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://localhost/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_reject_private_ip_url(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://192.168.1.1/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_reject_loopback_ip(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://127.0.0.1/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 0

    def test_allow_public_url(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://example.com/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1


# ===================================================================
# 6. Deduplication
# ===================================================================


class TestDeduplication:
    """Duplicate URLs should be deduplicated across sources."""

    def test_same_url_from_header_and_body(self, service: UnsubscribeService):
        url = "https://example.com/unsub/123"
        html = f'<p><a href="{url}">Unsubscribe</a></p>'
        email = _make_email(
            list_unsubscribe=f"<{url}>",
            html_body=html,
        )
        methods = service.find_unsubscribe_links(email)
        # Should be deduplicated to one entry (header wins since it's first)
        url_methods = [m for m in methods if m.url == url]
        assert len(url_methods) == 1

    def test_different_urls_preserved(self, service: UnsubscribeService):
        url1 = "https://example.com/unsub/header"
        url2 = "https://example.com/unsub/body"
        html = f'<p><a href="{url2}">Unsubscribe</a></p>'
        email = _make_email(
            list_unsubscribe=f"<{url1}>",
            html_body=html,
        )
        methods = service.find_unsubscribe_links(email)
        urls = [m.url for m in methods if m.type == "http"]
        assert url1 in urls
        assert url2 in urls

    def test_mailto_and_http_both_preserved(self, service: UnsubscribeService):
        """Mailto and HTTP methods should not deduplicate against each other."""
        email = _make_email(list_unsubscribe="<mailto:unsub@example.com>, <https://example.com/unsub>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 2


# ===================================================================
# 7. execute_unsubscribe tests
# ===================================================================


class TestExecuteUnsubscribe:
    """Test unsubscribe execution with mocked HTTP requests."""

    @patch("proton_mcp.services.unsubscribe.requests.get")
    def test_successful_get_returns_true(self, mock_get, service: UnsubscribeService):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        method = UnsubscribeMethod(type="http", method="click", url="https://example.com/unsub")
        result = service.execute_unsubscribe(method)
        assert result is True
        mock_get.assert_called_once()

    @patch("proton_mcp.services.unsubscribe.requests.post")
    def test_successful_one_click_post_returns_true(self, mock_post, service: UnsubscribeService):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_post.return_value = mock_response

        method = UnsubscribeMethod(
            type="http",
            method="one_click",
            url="https://example.com/unsub",
            one_click=True,
        )
        result = service.execute_unsubscribe(method)
        assert result is True
        mock_post.assert_called_once()
        # Verify one-click header was sent
        call_kwargs = mock_post.call_args
        assert "List-Unsubscribe" in call_kwargs[1]["headers"]

    @patch("proton_mcp.services.unsubscribe.requests.get")
    def test_failed_request_returns_false(self, mock_get, service: UnsubscribeService):
        mock_response = MagicMock()
        mock_response.status_code = 500
        mock_get.return_value = mock_response

        method = UnsubscribeMethod(type="http", method="click", url="https://example.com/unsub")
        result = service.execute_unsubscribe(method)
        assert result is False

    def test_unsafe_url_rejected(self, service: UnsubscribeService):
        method = UnsubscribeMethod(type="http", method="click", url="https://localhost/unsub")
        result = service.execute_unsubscribe(method)
        assert result is False

    @patch("proton_mcp.services.unsubscribe.requests.get")
    def test_timeout_returns_false(self, mock_get, service: UnsubscribeService):
        import requests as req

        mock_get.side_effect = req.exceptions.Timeout()

        method = UnsubscribeMethod(type="http", method="click", url="https://example.com/unsub")
        result = service.execute_unsubscribe(method)
        assert result is False

    @patch("proton_mcp.services.unsubscribe.requests.get")
    def test_connection_error_returns_false(self, mock_get, service: UnsubscribeService):
        import requests as req

        mock_get.side_effect = req.exceptions.ConnectionError()

        method = UnsubscribeMethod(type="http", method="click", url="https://example.com/unsub")
        result = service.execute_unsubscribe(method)
        assert result is False

    def test_mailto_method_returns_false(self, service: UnsubscribeService):
        """Mailto unsubscribe is not supported for automated execution."""
        method = UnsubscribeMethod(type="mailto", method="email", address="unsub@example.com")
        result = service.execute_unsubscribe(method)
        assert result is False

    @patch("proton_mcp.services.unsubscribe.requests.get")
    def test_execute_logs_attempt_to_history(self, mock_get, service: UnsubscribeService):
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_get.return_value = mock_response

        method = UnsubscribeMethod(type="http", method="click", url="https://example.com/unsub")
        service.execute_unsubscribe(method)

        history = service.get_history()
        assert len(history) == 1
        assert history[0].url == "https://example.com/unsub"
        assert history[0].success is True


# ===================================================================
# 8. Sender preference tests
# ===================================================================


class TestSenderPreferences:
    """CRUD operations for sender preferences."""

    def test_add_and_get_preference(self, service: UnsubscribeService):
        assert service.add_sender_preference("spam@example.com", "always_unsubscribe") is True
        pref = service.get_sender_preference("spam@example.com")
        assert pref is not None
        assert pref.action == "always_unsubscribe"
        assert pref.sender == "spam@example.com"

    def test_add_domain_preference(self, service: UnsubscribeService):
        assert service.add_sender_preference("", "never_unsubscribe", domain="important.com") is True
        pref = service.get_sender_preference("important.com")
        assert pref is not None
        assert pref.action == "never_unsubscribe"

    def test_remove_preference(self, service: UnsubscribeService):
        service.add_sender_preference("removeme@example.com", "always_unsubscribe")
        assert service.remove_sender_preference("removeme@example.com") is True
        pref = service.get_sender_preference("removeme@example.com")
        assert pref is None

    def test_remove_nonexistent_preference(self, service: UnsubscribeService):
        assert service.remove_sender_preference("doesnotexist@example.com") is False

    def test_duplicate_preference_returns_false(self, service: UnsubscribeService):
        service.add_sender_preference("dup@example.com", "always_unsubscribe")
        assert service.add_sender_preference("dup@example.com", "always_unsubscribe") is False

    def test_preference_persists_across_reload(self, mock_config):
        svc1 = UnsubscribeService(mock_config)
        svc1.add_sender_preference("persist@example.com", "never_unsubscribe")

        svc2 = UnsubscribeService(mock_config)
        pref = svc2.get_sender_preference("persist@example.com")
        assert pref is not None
        assert pref.action == "never_unsubscribe"

    def test_get_preference_case_insensitive(self, service: UnsubscribeService):
        service.add_sender_preference("User@Example.COM", "always_unsubscribe")
        pref = service.get_sender_preference("user@example.com")
        assert pref is not None

    def test_domain_preference_matches_sender(self, service: UnsubscribeService):
        """A domain preference should match any sender at that domain."""
        service.add_sender_preference("", "always_unsubscribe", domain="marketing.com")
        pref = service.get_sender_preference("deals@marketing.com")
        assert pref is not None
        assert pref.action == "always_unsubscribe"


# ===================================================================
# 9. History tests
# ===================================================================


class TestHistory:
    """Unsubscribe attempt history logging and retrieval."""

    def test_log_attempt_records_entry(self, service: UnsubscribeService):
        service.log_attempt(
            sender="test@example.com",
            method="click",
            url="https://example.com/unsub",
            success=True,
        )
        history = service.get_history()
        assert len(history) == 1
        assert history[0].sender == "test@example.com"
        assert history[0].method == "click"
        assert history[0].url == "https://example.com/unsub"
        assert history[0].success is True
        assert history[0].date  # Should have a date

    def test_get_history_returns_all_entries(self, service: UnsubscribeService):
        service.log_attempt("a@example.com", "click", "https://a.com/unsub", True)
        service.log_attempt("b@example.com", "one_click", "https://b.com/unsub", False)
        service.log_attempt("c@example.com", "click", "https://c.com/unsub", True)

        history = service.get_history()
        assert len(history) == 3
        assert history[0].sender == "a@example.com"
        assert history[1].sender == "b@example.com"
        assert history[2].sender == "c@example.com"

    def test_history_persists_across_reload(self, mock_config):
        svc1 = UnsubscribeService(mock_config)
        svc1.log_attempt("persist@example.com", "click", "https://example.com/unsub", True)

        svc2 = UnsubscribeService(mock_config)
        history = svc2.get_history()
        assert len(history) == 1
        assert history[0].sender == "persist@example.com"

    def test_history_entries_are_model_instances(self, service: UnsubscribeService):
        service.log_attempt("test@example.com", "click", "https://example.com/unsub", True)
        history = service.get_history()
        assert isinstance(history[0], UnsubscribeHistoryEntry)

    def test_sample_config_has_history(self, service_with_sample: UnsubscribeService):
        history = service_with_sample.get_history()
        assert len(history) == 2
        assert history[0].sender == "deals@old-store.com"
        assert history[0].success is True
        assert history[1].sender == "spam@example.com"
        assert history[1].success is False


# ===================================================================
# 10. Detection pattern tests
# ===================================================================


class TestDetectionPatterns:
    """Detection pattern CRUD operations."""

    def test_builtin_patterns_present_on_init(self, service: UnsubscribeService):
        data = service.load_config()
        patterns = data["detection_patterns"]
        ids = [p["id"] for p in patterns]
        assert "builtin-klaviyo" in ids
        assert "builtin-sendgrid" in ids
        assert "builtin-mailchimp" in ids

    def test_add_custom_pattern(self, service: UnsubscribeService):
        pattern = service.add_detection_pattern(
            name="Custom tracker",
            pattern=r"track\.custom\.com",
            pattern_type="tracker_domain",
        )
        assert pattern.id.startswith("custom-")
        assert pattern.name == "Custom tracker"
        assert pattern.enabled is True

        # Verify it persists
        data = service.load_config()
        ids = [p["id"] for p in data["detection_patterns"]]
        assert pattern.id in ids

    def test_remove_pattern(self, service: UnsubscribeService):
        pattern = service.add_detection_pattern("Temp", r"temp\.com")
        assert service.remove_detection_pattern(pattern.id) is True

        data = service.load_config()
        ids = [p["id"] for p in data["detection_patterns"]]
        assert pattern.id not in ids

    def test_remove_nonexistent_pattern(self, service: UnsubscribeService):
        assert service.remove_detection_pattern("nonexistent-id") is False

    def test_remove_builtin_pattern(self, service: UnsubscribeService):
        """Built-in patterns can also be removed if needed."""
        assert service.remove_detection_pattern("builtin-klaviyo") is True
        data = service.load_config()
        ids = [p["id"] for p in data["detection_patterns"]]
        assert "builtin-klaviyo" not in ids

    def test_added_pattern_is_detection_pattern_model(self, service: UnsubscribeService):
        pattern = service.add_detection_pattern("Model test", r"test\.com")
        assert isinstance(pattern, DetectionPattern)

    def test_custom_pattern_used_in_detection(self, service: UnsubscribeService):
        """Custom tracker patterns should be used in HTML detection."""
        service.add_detection_pattern(
            name="Custom tracker",
            pattern=r"track\.mycompany\.com",
        )
        html = """
        <p>To unsubscribe from these emails,
        <a href="https://track.mycompany.com/unsub/abc123">click here</a>.</p>
        """
        email = _make_email(html_body=html)
        methods = service.find_unsubscribe_links(email)
        http_methods = [m for m in methods if m.source == "html_body"]
        assert len(http_methods) >= 1
        assert any("track.mycompany.com" in m.url for m in http_methods)


# ===================================================================
# 11. check_resubscribe tests
# ===================================================================


class TestCheckResubscribe:
    """Check if a previously unsubscribed sender is still sending."""

    def test_returns_true_for_previously_successful_unsub(self, service: UnsubscribeService):
        service.log_attempt("spammer@example.com", "click", "https://example.com/unsub", True)
        assert service.check_resubscribe("spammer@example.com") is True

    def test_returns_false_for_failed_unsub(self, service: UnsubscribeService):
        service.log_attempt("spammer@example.com", "click", "https://example.com/unsub", False)
        assert service.check_resubscribe("spammer@example.com") is False

    def test_returns_false_for_unknown_sender(self, service: UnsubscribeService):
        assert service.check_resubscribe("unknown@example.com") is False

    def test_case_insensitive(self, service: UnsubscribeService):
        service.log_attempt("Spammer@Example.COM", "click", "https://example.com/unsub", True)
        assert service.check_resubscribe("spammer@example.com") is True


# ===================================================================
# 12. Config initialization and persistence
# ===================================================================


class TestConfigInitialization:
    """Config file creation and loading."""

    def test_creates_config_file_on_init(self, mock_config):
        config_path = os.path.join(mock_config.data_dir, "unsubscribe_config.json")
        assert not os.path.exists(config_path)
        UnsubscribeService(mock_config)
        assert os.path.exists(config_path)

    def test_default_config_structure(self, mock_config):
        svc = UnsubscribeService(mock_config)
        data = svc.load_config()
        assert data["schema_version"] == 1
        assert "sender_preferences" in data
        assert "detection_patterns" in data
        assert "history" in data
        assert isinstance(data["sender_preferences"], list)
        assert isinstance(data["detection_patterns"], list)
        assert isinstance(data["history"], list)

    def test_raw_json_matches_expected_default(self, mock_config):
        UnsubscribeService(mock_config)
        config_path = os.path.join(mock_config.data_dir, "unsubscribe_config.json")
        with open(config_path) as f:
            data = json.load(f)
        assert data["schema_version"] == 1
        assert len(data["detection_patterns"]) == 3
        assert data["sender_preferences"] == []
        assert data["history"] == []

    def test_sample_config_loads_correctly(self, service_with_sample: UnsubscribeService):
        data = service_with_sample.load_config()
        assert data["schema_version"] == 1
        assert len(data["sender_preferences"]) == 2
        assert len(data["detection_patterns"]) == 3
        assert len(data["history"]) == 2


# ===================================================================
# 13. Edge cases
# ===================================================================


class TestEdgeCases:
    """Edge case handling."""

    def test_empty_email_data(self, service: UnsubscribeService):
        methods = service.find_unsubscribe_links({})
        assert methods == []

    def test_html_with_malformed_tags(self, service: UnsubscribeService):
        """Should not crash on malformed HTML."""
        html = '<p>Bad HTML <a href="https://example.com/unsub">Unsubscribe<br>'
        email = _make_email(html_body=html)
        # Should not raise
        methods = service.find_unsubscribe_links(email)
        # May or may not find the link, but should not crash
        assert isinstance(methods, list)

    def test_url_with_special_characters(self, service: UnsubscribeService):
        email = _make_email(list_unsubscribe="<https://example.com/unsub?email=test%40example.com&token=abc123>")
        methods = service.find_unsubscribe_links(email)
        assert len(methods) == 1
        assert "test%40example.com" in methods[0].url

    def test_ftp_scheme_rejected(self, service: UnsubscribeService):
        """Only http/https schemes should be allowed."""
        email = _make_email(list_unsubscribe="<ftp://example.com/unsub>")
        methods = service.find_unsubscribe_links(email)
        # ftp:// won't match the https? regex, so no methods
        assert len(methods) == 0

    def test_no_crash_on_none_values(self, service: UnsubscribeService):
        """Should handle None values in email_data gracefully."""
        email = {
            "list_unsubscribe": None,
            "html_body": None,
            "body": None,
        }
        # Should not raise
        methods = service.find_unsubscribe_links(email)
        assert methods == []
