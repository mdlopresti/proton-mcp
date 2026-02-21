"""Filter rules MCP resource."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.filter_rules import FilterRuleEngine

logger = logging.getLogger(__name__)


def register_resources(mcp: FastMCP, config: Config) -> None:
    """Register filter rule resources with the MCP server."""
    filter_engine = FilterRuleEngine(config)

    @mcp.resource("proton://filter-rules")
    def filter_rules() -> str:
        """Get all email filtering rules."""
        try:
            rules = filter_engine.load_rules()
            return json.dumps([r.to_dict() for r in rules], indent=2)
        except Exception as e:
            return json.dumps({"error": f"Failed to load filter rules: {e}"})
