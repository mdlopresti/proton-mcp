"""Smoke test to verify test infrastructure works."""


def test_import_version():
    from proton_mcp import __version__

    assert __version__ == "0.1.0"


def test_create_server():
    from proton_mcp.server import create_server

    server = create_server()
    assert server.name == "ProtonEmailServer"
