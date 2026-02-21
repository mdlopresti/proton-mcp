"""Tests for proton_mcp.config module."""

import os
from unittest.mock import patch

import pytest

from proton_mcp.config import Config

# The directory where config.py lives, used to verify the default data_dir.
_CONFIG_MODULE_DIR = os.path.dirname(os.path.abspath(Config.__module__.replace(".", os.sep) + ".py"))


def _required_env(**overrides: str) -> dict[str, str]:
    """Return a minimal env dict with required variables, applying overrides."""
    env: dict[str, str] = {
        "PROTON_EMAIL": "user@proton.me",
        "PROTON_BRIDGE_PASSWORD": "bridge-secret",
    }
    env.update(overrides)
    return env


def _full_env(**overrides: str) -> dict[str, str]:
    """Return an env dict with every recognised variable set."""
    env: dict[str, str] = {
        "BRIDGE_IMAP_HOST": "10.0.0.1",
        "BRIDGE_IMAP_PORT": "993",
        "BRIDGE_SMTP_HOST": "10.0.0.2",
        "BRIDGE_SMTP_PORT": "587",
        "PROTON_EMAIL": "user@proton.me",
        "PROTON_BRIDGE_PASSWORD": "bridge-secret",
        "PROTON_DATA_DIR": "/custom/data",
    }
    env.update(overrides)
    return env


class TestConfigFromEnv:
    """Tests for Config.from_env()."""

    @patch("proton_mcp.config.load_dotenv")
    def test_all_env_vars_set(self, mock_dotenv, monkeypatch):
        """When all environment variables are set, Config is created correctly."""
        for key, value in _full_env().items():
            monkeypatch.setenv(key, value)

        cfg = Config.from_env()

        mock_dotenv.assert_called_once()
        assert cfg.imap_host == "10.0.0.1"
        assert cfg.imap_port == 993
        assert cfg.smtp_host == "10.0.0.2"
        assert cfg.smtp_port == 587
        assert cfg.email == "user@proton.me"
        assert cfg.password == "bridge-secret"
        assert cfg.data_dir == "/custom/data"

    @patch("proton_mcp.config.load_dotenv")
    def test_only_required_vars_uses_defaults(self, mock_dotenv, monkeypatch):
        """When only required vars are set, defaults are used for the rest."""
        for key, value in _required_env().items():
            monkeypatch.setenv(key, value)

        # Ensure optional vars are NOT in the environment.
        for key in ("BRIDGE_IMAP_HOST", "BRIDGE_IMAP_PORT", "BRIDGE_SMTP_HOST", "BRIDGE_SMTP_PORT", "PROTON_DATA_DIR"):
            monkeypatch.delenv(key, raising=False)

        cfg = Config.from_env()

        assert cfg.imap_host == "127.0.0.1"
        assert cfg.imap_port == 1143
        assert cfg.smtp_host == "127.0.0.1"
        assert cfg.smtp_port == 1025

    @patch("proton_mcp.config.load_dotenv")
    def test_missing_email_raises(self, mock_dotenv, monkeypatch):
        """Missing PROTON_EMAIL raises ValueError."""
        monkeypatch.setenv("PROTON_BRIDGE_PASSWORD", "secret")
        monkeypatch.delenv("PROTON_EMAIL", raising=False)

        with pytest.raises(ValueError, match="PROTON_EMAIL"):
            Config.from_env()

    @patch("proton_mcp.config.load_dotenv")
    def test_empty_email_raises(self, mock_dotenv, monkeypatch):
        """Empty PROTON_EMAIL raises ValueError."""
        monkeypatch.setenv("PROTON_EMAIL", "")
        monkeypatch.setenv("PROTON_BRIDGE_PASSWORD", "secret")

        with pytest.raises(ValueError, match="PROTON_EMAIL"):
            Config.from_env()

    @patch("proton_mcp.config.load_dotenv")
    def test_missing_password_raises(self, mock_dotenv, monkeypatch):
        """Missing PROTON_BRIDGE_PASSWORD raises ValueError."""
        monkeypatch.setenv("PROTON_EMAIL", "user@proton.me")
        monkeypatch.delenv("PROTON_BRIDGE_PASSWORD", raising=False)

        with pytest.raises(ValueError, match="PROTON_BRIDGE_PASSWORD"):
            Config.from_env()

    @patch("proton_mcp.config.load_dotenv")
    def test_empty_password_raises(self, mock_dotenv, monkeypatch):
        """Empty PROTON_BRIDGE_PASSWORD raises ValueError."""
        monkeypatch.setenv("PROTON_EMAIL", "user@proton.me")
        monkeypatch.setenv("PROTON_BRIDGE_PASSWORD", "")

        with pytest.raises(ValueError, match="PROTON_BRIDGE_PASSWORD"):
            Config.from_env()

    @patch("proton_mcp.config.load_dotenv")
    def test_data_dir_defaults_to_module_directory(self, mock_dotenv, monkeypatch):
        """data_dir defaults to the directory containing config.py."""
        for key, value in _required_env().items():
            monkeypatch.setenv(key, value)
        monkeypatch.delenv("PROTON_DATA_DIR", raising=False)

        cfg = Config.from_env()

        # Both should resolve to the same proton_mcp package directory.
        assert os.path.isdir(cfg.data_dir)
        assert os.path.basename(cfg.data_dir) == "proton_mcp"

    @patch("proton_mcp.config.load_dotenv")
    def test_data_dir_uses_env_var(self, mock_dotenv, monkeypatch):
        """data_dir uses PROTON_DATA_DIR when set."""
        for key, value in _required_env().items():
            monkeypatch.setenv(key, value)
        monkeypatch.setenv("PROTON_DATA_DIR", "/tmp/proton-test-data")

        cfg = Config.from_env()

        assert cfg.data_dir == "/tmp/proton-test-data"

    @patch("proton_mcp.config.load_dotenv")
    def test_port_values_are_int(self, mock_dotenv, monkeypatch):
        """Port values are converted from string env vars to int."""
        for key, value in _full_env(BRIDGE_IMAP_PORT="2143", BRIDGE_SMTP_PORT="2025").items():
            monkeypatch.setenv(key, value)

        cfg = Config.from_env()

        assert isinstance(cfg.imap_port, int)
        assert cfg.imap_port == 2143
        assert isinstance(cfg.smtp_port, int)
        assert cfg.smtp_port == 2025

    @patch("proton_mcp.config.load_dotenv")
    def test_load_dotenv_is_called(self, mock_dotenv, monkeypatch):
        """load_dotenv() is called before reading env vars."""
        for key, value in _required_env().items():
            monkeypatch.setenv(key, value)

        Config.from_env()

        mock_dotenv.assert_called_once()
