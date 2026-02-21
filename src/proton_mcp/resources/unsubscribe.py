"""Unsubscribe configuration and history MCP resources."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.unsubscribe import UnsubscribeService

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, config: Config) -> None:
    """Register unsubscribe resources with the MCP server."""
    unsub_service = UnsubscribeService(config)

    @mcp.resource("proton://unsubscribe/config")
    def unsubscribe_config() -> str:
        """Get unsubscribe configuration including sender preferences and detection patterns."""
        try:
            cfg = unsub_service.load_config()
            # Return config without history for the config resource
            result = {
                "sender_preferences": cfg.get("sender_preferences", []),
                "detection_patterns": cfg.get("detection_patterns", []),
            }
            return json.dumps(result, indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to load unsubscribe config: {e}"})

    @mcp.resource("proton://unsubscribe/history")
    def unsubscribe_history() -> str:
        """Get history of unsubscribe attempts."""
        try:
            history = unsub_service.get_history()
            return json.dumps([h.to_dict() for h in history], indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to load unsubscribe history: {e}"})
