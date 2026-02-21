"""Configuration management for ProtonMCP server."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class Config:
    """Server configuration loaded from environment variables."""

    imap_host: str
    imap_port: int
    smtp_host: str
    smtp_port: int
    email: str
    password: str
    data_dir: str

    @classmethod
    def from_env(cls) -> Config:
        """Create Config from environment variables."""
        raise NotImplementedError
