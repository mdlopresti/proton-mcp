"""End-to-end integration tests for MCP tools.

Tests call the actual registered tool functions (not via MCP protocol)
with IMAP/SMTP mocked at the imaplib/smtplib level. This verifies that
the full stack -- tool -> service -> client -> mock IMAP -- works correctly.
"""

from __future__ import annotations

import json

from proton_mcp.server import create_server

from .conftest import make_batch_fetch_response, make_fetch_response, make_raw_email

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------


def _get_tool(server, tool_name: str):
    """Look up a registered tool function by name."""
    tools = server._tool_manager.list_tools()
    for tool in tools:
        if tool.name == tool_name:
            return tool
    raise KeyError(f"Tool '{tool_name}' not found among {[t.name for t in tools]}")


def _call_tool(server, tool_name: str, **kwargs) -> dict | list:
    """Call a registered tool function by name and parse JSON result."""
    tool = _get_tool(server, tool_name)
    # The tool function is the callable stored in the tool manager
    # FastMCP stores the function reference in tool.fn
    result_str = tool.fn(**kwargs)
    return json.loads(result_str)


# ===========================================================================
# search_emails
# ===========================================================================


class TestSearchEmails:
    """End-to-end test: search_emails tool."""

    def test_search_returns_formatted_results(self, integration_config, integration_env_vars, patch_imap):
        raw1 = make_raw_email(subject="Meeting Notes", from_addr="alice@example.com")
        raw2 = make_raw_email(subject="Project Update", from_addr="bob@example.com")

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"101 102"])
            if cmd == "fetch":
                return ("OK", make_batch_fetch_response([("101", raw1), ("102", raw2)]))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "search_emails", query="ALL", max_results=10)

        assert isinstance(result, list)
        assert len(result) == 2
        assert result[0]["subject"] == "Meeting Notes"
        assert result[1]["subject"] == "Project Update"
        assert "from_addr" in result[0]
        assert "date" in result[0]

    def test_search_with_no_results(self, integration_config, integration_env_vars, patch_imap):
        patch_imap.uid.return_value = ("OK", [b""])

        server = create_server()
        result = _call_tool(server, "search_emails", query="FROM nonexistent@nowhere.com")

        assert isinstance(result, list)
        assert len(result) == 0


# ===========================================================================
# get_email_content
# ===========================================================================


class TestGetEmailContent:
    """End-to-end test: get_email_content tool."""

    def test_returns_full_email(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(
            subject="Important Report",
            from_addr="boss@company.com",
            to_addr="test@proton.me",
            body="Please review the attached report.",
        )

        def uid_side_effect(cmd, *args):
            if cmd == "fetch":
                return ("OK", make_fetch_response("42", raw))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "get_email_content", email_id="42")

        assert result["subject"] == "Important Report"
        assert result["from_addr"] == "boss@company.com"
        assert "review the attached report" in result["body"]

    def test_returns_error_for_missing_email(self, integration_config, integration_env_vars, patch_imap):
        patch_imap.uid.return_value = ("OK", [None])

        server = create_server()
        result = _call_tool(server, "get_email_content", email_id="999")

        assert "error" in result


# ===========================================================================
# send_email
# ===========================================================================


class TestSendEmail:
    """End-to-end test: send_email tool."""

    def test_sends_email_successfully(self, integration_config, integration_env_vars, patch_smtp):
        server = create_server()
        result = _call_tool(
            server,
            "send_email",
            to="recipient@example.com",
            subject="Test Email",
            body="Hello from integration test.",
        )

        assert result["status"] == "success"
        assert "sent" in result["message"].lower()
        patch_smtp.send_message.assert_called_once()


# ===========================================================================
# filter_junk_emails
# ===========================================================================


class TestFilterJunkEmails:
    """End-to-end test: filter_junk_emails tool."""

    def test_identifies_junk_email(self, integration_config, integration_env_vars, patch_imap):
        clean_email = make_raw_email(
            subject="Quarterly Review",
            from_addr="manager@company.com",
            body="Here are the quarterly results.",
        )
        spam_email = make_raw_email(
            subject="CONGRATULATIONS YOU WON $1,000,000!!!",
            from_addr="winner@sketchy.tk",
            body="Click here now to claim your lottery inheritance million bitcoin investment.",
        )

        call_count = [0]

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"101 102"])
            if cmd == "fetch":
                call_count[0] += 1
                return (
                    "OK",
                    make_batch_fetch_response([("101", clean_email), ("102", spam_email)]),
                )
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "filter_junk_emails", max_emails=10)

        assert isinstance(result, list)
        # First element is the summary
        summary = result[0]["summary"]
        assert summary["total_analyzed"] >= 1
        assert summary["junk_detected"] >= 1

        # Find the spam email in results
        spam_results = [r for r in result[1:] if r.get("junk_analysis", {}).get("is_likely_junk")]
        assert len(spam_results) >= 1


# ===========================================================================
# create_filter_rule / delete_filter_rule (CRUD cycle)
# ===========================================================================


class TestFilterRuleCRUD:
    """End-to-end test: create and delete filter rules."""

    def test_create_and_delete_filter_rule(self, integration_config, integration_env_vars):
        server = create_server()

        # Create a rule
        create_result = _call_tool(
            server,
            "create_filter_rule",
            name="GitHub Notifications",
            conditions='{"sender_domain": "github.com"}',
            actions='{"move_to_folder": "GitHub", "mark_as_read": true}',
        )

        assert create_result["status"] == "success"
        rule_id = create_result["rule"]["id"]
        assert create_result["rule"]["name"] == "GitHub Notifications"

        # Delete the rule
        delete_result = _call_tool(server, "delete_filter_rule", rule_id=rule_id)

        assert delete_result["status"] == "success"

    def test_create_duplicate_rule_fails(self, integration_config, integration_env_vars):
        server = create_server()

        # Create first rule
        _call_tool(
            server,
            "create_filter_rule",
            name="Unique Rule",
            conditions='{"from": "test@example.com"}',
            actions='{"mark_as_read": true}',
        )

        # Try to create duplicate
        dup_result = _call_tool(
            server,
            "create_filter_rule",
            name="Unique Rule",
            conditions='{"from": "other@example.com"}',
            actions='{"mark_as_read": true}',
        )

        assert dup_result["status"] == "error"
        assert "already exists" in dup_result["message"]

    def test_delete_nonexistent_rule(self, integration_config, integration_env_vars):
        server = create_server()

        result = _call_tool(server, "delete_filter_rule", rule_id="nonexistent-id")

        assert result["status"] == "error"


# ===========================================================================
# bulk_move_emails
# ===========================================================================


class TestBulkMoveEmails:
    """End-to-end test: bulk_move_emails tool."""

    def test_moves_emails_successfully(self, integration_config, integration_env_vars, patch_imap):
        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"101 102 103"])
            if cmd == "copy":
                return ("OK", [b"Done"])
            if cmd == "store":
                return ("OK", [b"Done"])
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(
            server,
            "bulk_move_emails",
            email_ids="101,102,103",
            target_folder="Archive",
        )

        assert result["status"] == "success"
        assert result["moved"] == 3
        assert result["target"] == "Archive"

    def test_move_with_invalid_ids(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_tool(
            server,
            "bulk_move_emails",
            email_ids="abc,def",
            target_folder="Archive",
        )

        assert "error" in result


# ===========================================================================
# create_folder / delete_folder
# ===========================================================================


class TestFolderCRUD:
    """End-to-end test: create_folder and delete_folder tools."""

    def test_create_and_delete_folder(self, integration_config, integration_env_vars, patch_imap):
        server = create_server()

        # Create
        create_result = _call_tool(server, "create_folder", folder_name="TestFolder")
        assert create_result["status"] == "success"
        patch_imap.create.assert_called_once_with("TestFolder")

        # Delete
        delete_result = _call_tool(server, "delete_folder", folder_name="TestFolder")
        assert delete_result["status"] == "success"
        patch_imap.delete.assert_called_once_with("TestFolder")

    def test_create_folder_with_invalid_name(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_tool(server, "create_folder", folder_name="../etc/passwd")

        assert "error" in result or result.get("status") == "error"

    def test_delete_folder_with_empty_name(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_tool(server, "delete_folder", folder_name="  ")

        assert "error" in result or result.get("status") == "error"


# ===========================================================================
# find_unsubscribe_links
# ===========================================================================


class TestFindUnsubscribeLinks:
    """End-to-end test: find_unsubscribe_links tool."""

    def test_detects_header_unsubscribe(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(
            subject="Newsletter #42",
            from_addr="newsletter@example.com",
            body="This is our weekly newsletter. To unsubscribe visit https://example.com/unsub",
            list_unsubscribe="<https://example.com/unsubscribe>, <mailto:unsub@example.com>",
        )

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"201"])
            if cmd == "fetch":
                return ("OK", make_batch_fetch_response([("201", raw)]))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "find_unsubscribe_links", email_id="201")

        assert result["total_methods"] >= 1
        # Should find at least the text body unsubscribe URL
        methods = result["unsubscribe_methods"]
        assert len(methods) >= 1

    def test_no_unsubscribe_in_plain_email(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(
            subject="Hi there",
            from_addr="friend@example.com",
            body="Just wanted to say hello! How are you?",
        )

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"301"])
            if cmd == "fetch":
                return ("OK", make_batch_fetch_response([("301", raw)]))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "find_unsubscribe_links", email_id="301")

        assert result["total_methods"] == 0


# ===========================================================================
# analyze_email_for_junk
# ===========================================================================


class TestAnalyzeEmailForJunk:
    """End-to-end test: analyze_email_for_junk tool."""

    def test_clean_email_is_not_junk(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(
            subject="Weekly Team Standup Notes",
            from_addr="manager@company.com",
            body="Here are the notes from today's standup meeting.",
        )

        def uid_side_effect(cmd, *args):
            if cmd == "fetch":
                return ("OK", make_fetch_response("42", raw))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "analyze_email_for_junk", email_id="42")

        assert "junk_analysis" in result
        assert result["junk_analysis"]["is_likely_junk"] is False

    def test_obvious_spam_is_junk(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(
            subject="CONGRATULATIONS YOU WON free money",
            from_addr="prince@sketchy.tk",
            body="Urgent respond now to verify account immediately. Winner lottery inheritance million bitcoin investment crypto opportunity.",
        )

        def uid_side_effect(cmd, *args):
            if cmd == "fetch":
                return ("OK", make_fetch_response("99", raw))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "analyze_email_for_junk", email_id="99")

        assert result["junk_analysis"]["is_likely_junk"] is True
        assert result["junk_analysis"]["junk_score"] >= 4


# ===========================================================================
# get_recent_emails
# ===========================================================================


class TestGetRecentEmails:
    """End-to-end test: get_recent_emails tool."""

    def test_returns_recent_emails(self, integration_config, integration_env_vars, patch_imap):
        raw = make_raw_email(subject="Just now", from_addr="recent@example.com")

        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"501"])
            if cmd == "fetch":
                return ("OK", make_batch_fetch_response([("501", raw)]))
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(server, "get_recent_emails", hours=24)

        assert isinstance(result, list)
        assert len(result) == 1
        assert result[0]["subject"] == "Just now"


# ===========================================================================
# Junk rule CRUD
# ===========================================================================


class TestJunkRuleCRUD:
    """End-to-end test: create_junk_rule / delete_junk_rule tools."""

    def test_create_and_delete_junk_rule(self, integration_config, integration_env_vars):
        server = create_server()

        # Create
        create_result = _call_tool(
            server,
            "create_junk_rule",
            name="Block Crypto Spam",
            field="subject",
            pattern=r"crypto.*profit",
            score=3,
        )

        assert create_result["status"] == "success"
        rule_id = create_result["rule"]["id"]

        # Delete
        delete_result = _call_tool(server, "delete_junk_rule", rule_id=rule_id)

        assert delete_result["status"] == "success"

    def test_delete_nonexistent_junk_rule(self, integration_config, integration_env_vars):
        server = create_server()
        result = _call_tool(server, "delete_junk_rule", rule_id="nonexistent-id")

        assert result["status"] == "error"


# ===========================================================================
# Unsubscribe preference CRUD
# ===========================================================================


class TestUnsubscribePreferenceCRUD:
    """End-to-end test: add_sender_preference / remove_sender_preference."""

    def test_add_and_remove_preference(self, integration_config, integration_env_vars):
        server = create_server()

        # Add
        add_result = _call_tool(
            server,
            "add_sender_preference",
            sender="spam@marketing.com",
            action="always_unsubscribe",
        )
        assert add_result["status"] == "success"

        # Remove
        remove_result = _call_tool(
            server,
            "remove_sender_preference",
            sender="spam@marketing.com",
        )
        assert remove_result["status"] == "success"


# ===========================================================================
# move_email_to_folder
# ===========================================================================


class TestMoveEmailToFolder:
    """End-to-end test: move_email_to_folder tool."""

    def test_moves_single_email(self, integration_config, integration_env_vars, patch_imap):
        def uid_side_effect(cmd, *args):
            if cmd == "search":
                return ("OK", [b"101"])
            if cmd == "copy":
                return ("OK", [b"Done"])
            if cmd == "store":
                return ("OK", [b"Done"])
            return ("OK", [b""])

        patch_imap.uid.side_effect = uid_side_effect

        server = create_server()
        result = _call_tool(
            server,
            "move_email_to_folder",
            email_id="101",
            target_folder="Archive",
        )

        assert result["status"] == "success"
