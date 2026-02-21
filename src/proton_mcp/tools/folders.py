"""Folder management MCP tools."""

from __future__ import annotations

import json
import logging

from mcp.server.fastmcp import FastMCP

from proton_mcp.config import Config
from proton_mcp.services.folders import FolderService
from proton_mcp.utils.validation import validate_folder_name

logger = logging.getLogger(__name__)


def register_tools(mcp: FastMCP, config: Config) -> None:
    """Register folder management tools with the MCP server."""

    @mcp.tool()
    def create_folder(folder_name: str) -> str:
        """Create a new email folder/mailbox.

        Args:
            folder_name: Name of the folder to create

        Returns:
            Status of the folder creation operation
        """
        try:
            folder_name = validate_folder_name(folder_name)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        try:
            folder_service = FolderService(config)
            success = folder_service.create_folder(folder_name)
            if success:
                return json.dumps({"status": "success", "message": f"Folder '{folder_name}' created successfully"})
            return json.dumps({"status": "error", "message": f"Failed to create folder '{folder_name}'"})
        except NotImplementedError:
            return json.dumps({"status": "error", "message": "Folder service not yet implemented"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error creating folder: {e}"})

    @mcp.tool()
    def delete_folder(folder_name: str) -> str:
        """Delete an existing email folder/mailbox.

        Args:
            folder_name: Name of the folder to delete

        Returns:
            Status of the folder deletion operation
        """
        try:
            folder_name = validate_folder_name(folder_name)
        except ValueError as e:
            return json.dumps({"error": str(e)})

        try:
            folder_service = FolderService(config)
            success = folder_service.delete_folder(folder_name)
            if success:
                return json.dumps({"status": "success", "message": f"Folder '{folder_name}' deleted successfully"})
            return json.dumps({"status": "error", "message": f"Failed to delete folder '{folder_name}'"})
        except NotImplementedError:
            return json.dumps({"status": "error", "message": "Folder service not yet implemented"})
        except Exception as e:
            return json.dumps({"status": "error", "message": f"Error deleting folder: {e}"})
