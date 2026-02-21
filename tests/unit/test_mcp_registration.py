"""Test that MCP tools, resources, and prompts are properly registered."""

import os
from unittest.mock import patch

import pytest


@pytest.fixture
def _env_vars(tmp_path):
    """Set required environment variables for Config.from_env()."""
    env = {
        "PROTON_EMAIL": "test@proton.me",
        "PROTON_BRIDGE_PASSWORD": "test-password",
        "BRIDGE_IMAP_HOST": "127.0.0.1",
        "BRIDGE_IMAP_PORT": "1143",
        "BRIDGE_SMTP_HOST": "127.0.0.1",
        "BRIDGE_SMTP_PORT": "1025",
        "PROTON_DATA_DIR": str(tmp_path),
    }
    with patch.dict(os.environ, env, clear=False):
        yield


@pytest.mark.usefixtures("_env_vars")
class TestMCPRegistration:
    """Verify that create_server registers all expected tools, resources, and prompts."""

    def test_server_creates_successfully(self):
        from proton_mcp.server import create_server

        server = create_server()
        assert server.name == "ProtonEmailServer"

    def test_tool_count(self):
        from proton_mcp.server import create_server

        server = create_server()
        tools = server._tool_manager.list_tools()
        # 4 core + 5 junk + 8 unsubscribe + 2 folders + 4 filter_rules + 6 bulk = 29
        assert len(tools) == 29, f"Expected 29 tools, got {len(tools)}: {[t.name for t in tools]}"

    def test_expected_tool_names(self):
        from proton_mcp.server import create_server

        server = create_server()
        tools = server._tool_manager.list_tools()
        tool_names = {t.name for t in tools}

        expected_tools = {
            # Core (4)
            "search_emails",
            "get_email_content",
            "send_email",
            "get_recent_emails",
            # Junk (5)
            "filter_junk_emails",
            "analyze_email_for_junk",
            "create_junk_rule",
            "update_junk_rule",
            "delete_junk_rule",
            # Unsubscribe (8)
            "find_unsubscribe_links",
            "unsubscribe_from_email",
            "bulk_find_unsubscribe_opportunities",
            "get_mailing_list_senders",
            "add_sender_preference",
            "remove_sender_preference",
            "add_detection_pattern",
            "remove_detection_pattern",
            # Folders (2)
            "create_folder",
            "delete_folder",
            # Filter rules (4)
            "create_filter_rule",
            "delete_filter_rule",
            "update_filter_rule",
            "apply_filter_rules",
            # Bulk (6)
            "bulk_move_emails",
            "bulk_mark_emails_as_read",
            "bulk_mark_emails_as_important",
            "bulk_delete_emails",
            "bulk_get_emails",
            "move_email_to_folder",
        }

        missing = expected_tools - tool_names
        extra = tool_names - expected_tools
        assert not missing, f"Missing tools: {missing}"
        assert not extra, f"Unexpected tools: {extra}"

    def test_resource_count(self):
        from proton_mcp.server import create_server

        server = create_server()
        resources = server._resource_manager.list_resources()
        # inbox-summary + mailboxes + filter-rules + junk-config + unsubscribe/config + unsubscribe/history = 6
        assert len(resources) == 6, f"Expected 6 resources, got {len(resources)}: {[r.uri for r in resources]}"

    def test_expected_resource_uris(self):
        from proton_mcp.server import create_server

        server = create_server()
        resources = server._resource_manager.list_resources()
        uris = {str(r.uri) for r in resources}

        expected_uris = {
            "proton://inbox-summary",
            "proton://mailboxes",
            "proton://filter-rules",
            "proton://junk-config",
            "proton://unsubscribe/config",
            "proton://unsubscribe/history",
        }

        missing = expected_uris - uris
        extra = uris - expected_uris
        assert not missing, f"Missing resources: {missing}"
        assert not extra, f"Unexpected resources: {extra}"

    def test_prompt_count(self):
        from proton_mcp.server import create_server

        server = create_server()
        prompts = server._prompt_manager.list_prompts()
        assert len(prompts) == 2, f"Expected 2 prompts, got {len(prompts)}: {[p.name for p in prompts]}"

    def test_expected_prompt_names(self):
        from proton_mcp.server import create_server

        server = create_server()
        prompts = server._prompt_manager.list_prompts()
        prompt_names = {p.name for p in prompts}

        expected_prompts = {"create_filter_rule", "email_triage"}
        assert prompt_names == expected_prompts, f"Expected {expected_prompts}, got {prompt_names}"
