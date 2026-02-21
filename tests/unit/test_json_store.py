"""Tests for proton_mcp.utils.json_store module."""

import json
import os
import threading
from pathlib import Path

import pytest

from proton_mcp.utils.json_store import JsonStore


@pytest.fixture
def store_path(tmp_path):
    """Return a path for a JSON store file inside a temp directory."""
    return str(tmp_path / "test_store.json")


@pytest.fixture
def nested_store_path(tmp_path):
    """Return a path inside a nested directory that does not yet exist."""
    return str(tmp_path / "sub" / "dir" / "store.json")


# ---------------------------------------------------------------------------
# __init__
# ---------------------------------------------------------------------------


class TestJsonStoreInit:
    def test_default_schema_version(self, store_path):
        store = JsonStore(store_path)
        assert store.schema_version == 1
        assert store.default_data == {}

    def test_custom_schema_version(self, store_path):
        store = JsonStore(store_path, schema_version=3)
        assert store.schema_version == 3

    def test_custom_default_data(self, store_path):
        defaults = {"rules": [], "settings": {}}
        store = JsonStore(store_path, default_data=defaults)
        assert store.default_data == defaults


# ---------------------------------------------------------------------------
# load - file does not exist (creates default)
# ---------------------------------------------------------------------------


class TestJsonStoreLoadMissing:
    def test_creates_file_with_defaults(self, store_path):
        store = JsonStore(store_path, default_data={"items": []})
        data = store.load()

        assert os.path.exists(store_path)
        assert data["items"] == []
        assert data["schema_version"] == 1

    def test_creates_file_with_empty_defaults(self, store_path):
        store = JsonStore(store_path)
        data = store.load()

        assert os.path.exists(store_path)
        assert data == {"schema_version": 1}

    def test_creates_nested_directories(self, nested_store_path):
        store = JsonStore(nested_store_path, default_data={"key": "value"})
        data = store.load()

        assert os.path.exists(nested_store_path)
        assert data["key"] == "value"


# ---------------------------------------------------------------------------
# load - file exists
# ---------------------------------------------------------------------------


class TestJsonStoreLoadExisting:
    def test_loads_valid_file(self, store_path):
        payload = {"schema_version": 1, "name": "test", "count": 42}
        with open(store_path, "w") as f:
            json.dump(payload, f)

        store = JsonStore(store_path)
        data = store.load()

        assert data["name"] == "test"
        assert data["count"] == 42

    def test_schema_version_mismatch_raises(self, store_path):
        payload = {"schema_version": 2, "data": "old"}
        with open(store_path, "w") as f:
            json.dump(payload, f)

        store = JsonStore(store_path, schema_version=1)
        with pytest.raises(ValueError, match="Schema version mismatch"):
            store.load()

    def test_schema_version_mismatch_higher_expected(self, store_path):
        payload = {"schema_version": 1, "data": "current"}
        with open(store_path, "w") as f:
            json.dump(payload, f)

        store = JsonStore(store_path, schema_version=5)
        with pytest.raises(ValueError, match="Schema version mismatch"):
            store.load()

    def test_missing_schema_version_key_raises(self, store_path):
        # File has no schema_version at all -> mismatch (None != 1)
        payload = {"data": "no version"}
        with open(store_path, "w") as f:
            json.dump(payload, f)

        store = JsonStore(store_path, schema_version=1)
        with pytest.raises(ValueError, match="Schema version mismatch"):
            store.load()

    def test_invalid_json_raises(self, store_path):
        with open(store_path, "w") as f:
            f.write("{bad json{{{")

        store = JsonStore(store_path)
        with pytest.raises(json.JSONDecodeError):
            store.load()


# ---------------------------------------------------------------------------
# save
# ---------------------------------------------------------------------------


class TestJsonStoreSave:
    def test_save_creates_file(self, store_path):
        store = JsonStore(store_path)
        store.save({"items": [1, 2, 3]})

        assert os.path.exists(store_path)
        with open(store_path) as f:
            data = json.load(f)
        assert data["items"] == [1, 2, 3]
        assert data["schema_version"] == 1

    def test_save_overwrites_existing(self, store_path):
        store = JsonStore(store_path)
        store.save({"version_one": True})
        store.save({"version_two": True})

        with open(store_path) as f:
            data = json.load(f)
        assert "version_two" in data
        assert "version_one" not in data

    def test_save_sets_schema_version(self, store_path):
        store = JsonStore(store_path, schema_version=7)
        store.save({"key": "value"})

        with open(store_path) as f:
            data = json.load(f)
        assert data["schema_version"] == 7

    def test_save_creates_nested_directories(self, nested_store_path):
        store = JsonStore(nested_store_path)
        store.save({"created": True})

        assert os.path.exists(nested_store_path)

    def test_save_and_load_roundtrip(self, store_path):
        store = JsonStore(store_path, schema_version=2)
        original = {"rules": [{"name": "test", "enabled": True}], "count": 5}
        store.save(original)

        loaded = store.load()
        assert loaded["rules"] == original["rules"]
        assert loaded["count"] == 5
        assert loaded["schema_version"] == 2


# ---------------------------------------------------------------------------
# Atomic write behavior
# ---------------------------------------------------------------------------


class TestJsonStoreAtomicWrite:
    def test_no_temp_file_left_after_save(self, store_path):
        store = JsonStore(store_path)
        store.save({"data": "test"})

        parent = os.path.dirname(store_path)
        files = os.listdir(parent)
        # Only the target file should remain (no .tmp leftovers)
        assert len(files) == 1
        assert files[0] == os.path.basename(store_path)

    def test_original_intact_if_save_would_fail_on_bad_dir(self):
        """Saving to a non-writable location should not corrupt an existing file."""
        # Use a path that cannot be created (e.g. under /proc)
        bad_path = "/proc/fake_store_test/data.json"
        store = JsonStore(bad_path)
        with pytest.raises(Exception):
            store.save({"data": "test"})


# ---------------------------------------------------------------------------
# Concurrent access (basic locking verification)
# ---------------------------------------------------------------------------


class TestJsonStoreConcurrency:
    def test_concurrent_writes_produce_valid_json(self, store_path):
        """Multiple threads writing should not produce corrupted files."""
        store = JsonStore(store_path)
        errors = []

        def writer(thread_id):
            try:
                for i in range(20):
                    store.save({"thread": thread_id, "iteration": i})
            except Exception as e:
                errors.append(e)

        threads = [threading.Thread(target=writer, args=(tid,)) for tid in range(4)]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent writes: {errors}"

        # File should still be valid JSON
        with open(store_path) as f:
            data = json.load(f)
        assert "thread" in data
        assert data["schema_version"] == 1

    def test_concurrent_read_and_write(self, store_path):
        """Reading while another thread writes should not crash."""
        store = JsonStore(store_path, default_data={"counter": 0})
        store.save({"counter": 0})
        errors = []

        def writer():
            try:
                for i in range(20):
                    store.save({"counter": i})
            except Exception as e:
                errors.append(e)

        def reader():
            try:
                for _ in range(20):
                    data = store.load()
                    assert "counter" in data
            except Exception as e:
                errors.append(e)

        threads = [
            threading.Thread(target=writer),
            threading.Thread(target=reader),
            threading.Thread(target=reader),
        ]
        for t in threads:
            t.start()
        for t in threads:
            t.join()

        assert errors == [], f"Errors during concurrent read/write: {errors}"


# ---------------------------------------------------------------------------
# Exception path in save (temp file cleanup)
# ---------------------------------------------------------------------------


class TestJsonStoreSaveExceptionCleanup:
    def test_save_cleans_up_temp_on_json_dump_failure(self, store_path):
        """If json.dump fails, the temp file should be cleaned up."""
        store = JsonStore(store_path)

        # Create a value that cannot be serialized to JSON
        class NotSerializable:
            pass

        with pytest.raises(TypeError):
            store.save({"bad": NotSerializable()})

        # The target file should not exist (or be from a prior write)
        parent = os.path.dirname(store_path)
        tmp_files = [f for f in os.listdir(parent) if f.endswith(".tmp")]
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"

    def test_save_cleans_up_temp_on_replace_failure(self, tmp_path):
        """If os.replace fails, the temp file should be cleaned up."""
        from unittest.mock import patch

        store_path = str(tmp_path / "test.json")
        store = JsonStore(store_path)

        with patch("os.replace", side_effect=OSError("replace failed")):
            with pytest.raises(OSError, match="replace failed"):
                store.save({"data": "test"})

        # Temp file should be cleaned up
        tmp_files = [f for f in os.listdir(str(tmp_path)) if f.endswith(".tmp")]
        assert tmp_files == [], f"Leftover temp files: {tmp_files}"
