"""End-to-end integration tests for MCP resources.

Tests verify that all 6 resources return valid data when called through
the actual registered resource functions.
"""

from __future__ import annotations

import json

from proton_mcp.server import create_server

from .conftest import make_batch_fetch_response, make_raw_email

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_resource_fn(server, uri_suffix: str):
    """Look up a registered resource function by URI suffix."""
    resources = server._resource_manager.list_resources()
    for resource in resources:
        if str(resource.uri).endswith(uri_suffix):
            return resource
    raise KeyError(f"Resource ending with '{uri_suffix}' not found among {[str(r.uri) for r in resources]}")


def _call_resource(server, uri_suffix: str) -> str | dict | list:
    """Call a registered resource and return its output.

    Resources return strings. We try to JSON-parse them; if that fails,
    we return the raw string.
    """
    resource = _get_resource_fn(server, uri_suffix)
    result_str = resource.fn()
    try:
        return json.loads(result_str)
    except (json.JSONDecodeError, TypeError):
        return result_str


# ===========================================================================
# proton://inbox-summary
# ===========================================================================


class TestInboxSummaryResource:
    """Test the inbox-summary resource returns formatted text."""

    def test_returns_inbox_summary(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(subject="Hello World", from_addr="alice@example.com")

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"101"])
            if cmd == "fetch":
                return ("OK", make_batch_fetch_response([("101", raw)]))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_resource(server, "inbox-summary")

        # inbox-summary returns plain text, not JSON
        assert isinstance(result, str)
        assert "Hello World" in result
        assert "alice@example.com" in result

    def test_empty_inbox_summary(self, integration_config, integration_env_vars, patch_imap):
        patch_imap.uid.return_value = ("OK", [b""])

        server = create_server()
        result = _call_resource(server, "inbox-summary")

        assert isinstance(result, str)
        assert "Total shown: 0" in result


# ===========================================================================
# proton://mailboxes
# ===========================================================================


class TestMailboxesResource:
    """Test the mailboxes resource returns folder list."""

    def test_returns_mailbox_list(self, integration_config, integration_env_vars, patch_imap):
        server = create_server()
        result = _call_resource(server, "mailboxes")

        assert isinstance(result, list)
        assert "INBOX" in result
        assert "Sent" in result
        assert "Trash" in result


# ===========================================================================
# proton://filter-rules
# ===========================================================================


class TestFilterRulesResource:
    """Test the filter-rules resource returns rule list."""

    def test_returns_empty_rules_initially(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_resource(server, "filter-rules")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_returns_created_rules(self, integration_config, integration_env_vars):
        from proton_mcp.services.filter_rules import FilterRuleEngine

        server = create_server()
        engine = FilterRuleEngine(integration_config)
        engine.create_rule(
            "Test Rule",
            {"from": "test@example.com"},
            {"mark_as_read": True},
        )

        result = _call_resource(server, "filter-rules")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["name"] == "Test Rule"


# ===========================================================================
# proton://junk-config
# ===========================================================================


class TestJunkConfigResource:
    """Test the junk-config resource returns configuration."""

    def test_returns_junk_config(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_resource(server, "junk-config")

        assert isinstance(result, dict)
        assert "whitelist" in result
        assert "blacklist" in result
        assert "thresholds" in result
        assert "custom_patterns" in result


# ===========================================================================
# proton://unsubscribe/config
# ===========================================================================


class TestUnsubscribeConfigResource:
    """Test the unsubscribe config resource returns preferences and patterns."""

    def test_returns_unsubscribe_config(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_resource(server, "unsubscribe/config")

        assert isinstance(result, dict)
        assert "sender_preferences" in result
        assert "detection_patterns" in result
        # Should have built-in detection patterns
        assert len(result["detection_patterns"]) >= 3


# ===========================================================================
# proton://unsubscribe/history
# ===========================================================================


class TestUnsubscribeHistoryResource:
    """Test the unsubscribe history resource returns attempt history."""

    def test_returns_empty_history_initially(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_resource(server, "unsubscribe/history")

        assert isinstance(result, list)
        assert len(result) == 0

    def test_returns_history_after_logging(self, integration_config, integration_env_vars):
        from proton_mcp.services.unsubscribe import UnsubscribeService

        server = create_server()
        unsub = UnsubscribeService(integration_config)
        unsub.log_attempt(
            sender="newsletter@example.com",
            method="one_click",
            url="https://example.com/unsubscribe",
            success=True,
        )

        result = _call_resource(server, "unsubscribe/history")

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["sender"] == "newsletter@example.com"
        assert result[0]["success"] is True
