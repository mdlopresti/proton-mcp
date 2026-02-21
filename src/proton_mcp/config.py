"""Configuration management for ProtonMCP server."""

from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


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
        """Create Config from environment variables.

        Loads a ``.env`` file (if present) via ``python-dotenv``, then reads
        the following environment variables:

        - ``BRIDGE_IMAP_HOST`` (default: ``127.0.0.1``)
        - ``BRIDGE_IMAP_PORT`` (default: ``1143``)
        - ``BRIDGE_SMTP_HOST`` (default: ``127.0.0.1``)
        - ``BRIDGE_SMTP_PORT`` (default: ``1025``)
        - ``PROTON_EMAIL`` (**required**)
        - ``PROTON_BRIDGE_PASSWORD`` (**required**)
        - ``PROTON_DATA_DIR`` (default: directory containing this module)

        Raises:
            ValueError: If ``PROTON_EMAIL`` or ``PROTON_BRIDGE_PASSWORD`` are
                missing or empty.
        """
        load_dotenv()

        email = os.getenv("PROTON_EMAIL", "")
        password = os.getenv("PROTON_BRIDGE_PASSWORD", "")

        if not email:
            raise ValueError(
                "PROTON_EMAIL environment variable is required but not set"
            )
        if not password:
            raise ValueError(
                "PROTON_BRIDGE_PASSWORD environment variable is required but not set"
            )

        default_data_dir = os.path.dirname(os.path.abspath(__file__))

        return cls(
            imap_host=os.getenv("BRIDGE_IMAP_HOST", "127.0.0.1"),
            imap_port=int(os.getenv("BRIDGE_IMAP_PORT", "1143")),
            smtp_host=os.getenv("BRIDGE_SMTP_HOST", "127.0.0.1"),
            smtp_port=int(os.getenv("BRIDGE_SMTP_PORT", "1025")),
            email=email,
            password=password,
            data_dir=os.getenv("PROTON_DATA_DIR", default_data_dir),
        )
