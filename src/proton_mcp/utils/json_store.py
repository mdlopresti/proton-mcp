"""Shared JSON storage utility with atomic writes and schema versioning."""

from __future__ import annotations

import fcntl
import json
import logging
import os
import tempfile
from typing import Any

logger = logging.getLogger(__name__)


class JsonStore:
    """Thread-safe JSON file storage with atomic writes and schema version checking.

    Provides a simple interface for persisting dictionaries as JSON files
    with the following guarantees:

    - **Atomic writes**: Data is written to a temporary file in the same
      directory and then renamed via :func:`os.replace`, so readers never
      see a partially-written file.
    - **File locking**: Uses :func:`fcntl.flock` (``LOCK_EX`` for writes,
      ``LOCK_SH`` for reads) to coordinate concurrent access from multiple
      processes.
    - **Schema versioning**: Every stored file contains a
      ``"schema_version"`` key. A :class:`ValueError` is raised on load if
      the on-disk version does not match the expected version.

    Args:
        file_path: Absolute or relative path to the JSON file.
        schema_version: Expected schema version (default ``1``).
        default_data: Default data dict used when creating a new file.
            If *None*, an empty dict is used.
    """

    def __init__(
        self,
        file_path: str,
        schema_version: int = 1,
        default_data: dict | None = None,
    ) -> None:
        self.file_path = file_path
        self.schema_version = schema_version
        self.default_data: dict[str, Any] = default_data if default_data is not None else {}

    def load(self) -> dict[str, Any]:
        """Load and return the JSON data. Creates default if file doesn't exist.

        If the file does not exist, it is created with the default data
        (augmented with ``"schema_version"``).

        Returns:
            The parsed dictionary from the JSON file.

        Raises:
            ValueError: If the file's ``schema_version`` does not match
                the expected version.
        """
        if not os.path.exists(self.file_path):
            logger.info("JSON store file not found, creating with defaults: %s", self.file_path)
            initial_data = {**self.default_data, "schema_version": self.schema_version}
            self.save(initial_data)
            return initial_data

        try:
            with open(self.file_path, encoding="utf-8") as f:
                fcntl.flock(f, fcntl.LOCK_SH)
                try:
                    data = json.load(f)
                finally:
                    fcntl.flock(f, fcntl.LOCK_UN)
        except json.JSONDecodeError as exc:
            logger.error("Failed to parse JSON from %s: %s", self.file_path, exc)
            raise

        file_version = data.get("schema_version")
        if file_version != self.schema_version:
            raise ValueError(
                f"Schema version mismatch in {self.file_path}: expected {self.schema_version}, got {file_version}"
            )

        return dict(data)

    def save(self, data: dict[str, Any]) -> None:
        """Atomically write data to the JSON file (write to temp, then rename).

        The data dict is augmented with ``"schema_version"`` before writing.
        A temporary file is created in the same directory as the target and
        then atomically renamed via :func:`os.replace`.

        Args:
            data: The dictionary to persist as JSON.
        """
        data["schema_version"] = self.schema_version

        # Ensure the parent directory exists
        dir_path = os.path.dirname(self.file_path)
        if dir_path:
            os.makedirs(dir_path, exist_ok=True)

        # Write to a temp file in the same directory, then atomically replace
        fd, tmp_path = tempfile.mkstemp(dir=dir_path or ".", suffix=".tmp")
        try:
            with os.fdopen(fd, "w", encoding="utf-8") as tmp_f:
                fcntl.flock(tmp_f, fcntl.LOCK_EX)
                try:
                    json.dump(data, tmp_f, indent=2)
                    tmp_f.flush()
                    os.fsync(tmp_f.fileno())
                finally:
                    fcntl.flock(tmp_f, fcntl.LOCK_UN)
            os.replace(tmp_path, self.file_path)
            logger.debug("Saved JSON store to %s", self.file_path)
        except Exception:
            # Clean up temp file on failure
            try:
                os.unlink(tmp_path)
            except OSError:
                pass
            raise
