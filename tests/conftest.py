"""Shared test fixtures for proton_mcp tests."""

import tempfile
from pathlib import Path
from unittest.mock import MagicMock

import pytest

FIXTURES_DIR = Path(__file__).parent / "fixtures"


@pytest.fixture
def fixtures_dir():
    """Path to the test fixtures directory."""
    return FIXTURES_DIR


@pytest.fixture
def temp_dir():
    """Temporary directory for test data files."""
    with tempfile.TemporaryDirectory() as tmpdir:
        yield Path(tmpdir)


@pytest.fixture
def mock_config(temp_dir):
    """Mock Config object for testing."""
    config = MagicMock()
    config.imap_host = "127.0.0.1"
    config.imap_port = 1143
    config.smtp_host = "127.0.0.1"
    config.smtp_port = 1025
    config.email = "test@proton.me"
    config.password = "test-bridge-password"
    config.data_dir = str(temp_dir)
    return config


@pytest.fixture
def mock_imap():
    """Mock IMAP4 connection."""
    imap = MagicMock()
    imap.select.return_value = ("OK", [b"10"])
    imap.uid.return_value = ("OK", [])
    imap.close.return_value = ("OK", [b"Closing"])
    imap.logout.return_value = ("BYE", [b"Logging out"])
    return imap


@pytest.fixture
def mock_smtp():
    """Mock SMTP connection."""
    smtp = MagicMock()
    smtp.starttls.return_value = (220, b"Ready")
    smtp.login.return_value = (235, b"Authenticated")
    smtp.sendmail.return_value = {}
    return smtp
