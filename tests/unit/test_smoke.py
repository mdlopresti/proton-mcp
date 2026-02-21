"""Smoke test to verify test infrastructure works."""

import os
from unittest.mock import patch


def test_import_version():
    from proton_mcp import __version__

    assert __version__ == "0.1.0"


def test_create_server(tmp_path):
    env = {
        "PROTON_EMAIL": "test@proton.me",
        "PROTON_BRIDGE_PASSWORD": "test-password",
        "PROTON_DATA_DIR": str(tmp_path),
    }
    with patch.dict(os.environ, env, clear=False):
        from proton_mcp.server import create_server

        server = create_server()
        assert server.name == "ProtonEmailServer"
