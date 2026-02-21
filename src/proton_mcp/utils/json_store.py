"""Shared JSON storage utility with atomic writes and schema versioning."""

from __future__ import annotations

from typing import Any


class JsonStore:
    """Thread-safe JSON file storage with atomic writes and schema version checking."""

    def __init__(self, file_path: str, schema_version: int = 1) -> None:
        raise NotImplementedError

    def load(self) -> dict[str, Any]:
        """Load and return the JSON data. Creates default if file doesn't exist."""
        raise NotImplementedError

    def save(self, data: dict[str, Any]) -> None:
        """Atomically write data to the JSON file (write to temp, then rename)."""
        raise NotImplementedError
