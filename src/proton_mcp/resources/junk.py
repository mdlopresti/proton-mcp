"""Junk configuration MCP resource."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.junk import JunkDetector

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, config: Config) -> None:
    """Register junk configuration resources with the MCP server."""
    junk_detector = JunkDetector(config)

    @mcp.resource("proton://junk-config")
    def junk_config() -> str:
        """Get current junk detection configuration including custom rules, whitelist, and blacklist."""
        try:
            cfg = junk_detector.load_config()
            return json.dumps(cfg.to_dict(), indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to load junk config: {e}"})
