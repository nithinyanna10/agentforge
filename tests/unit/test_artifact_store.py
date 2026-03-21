"""Tests for artifact_store module."""

from __future__ import annotations

import json
import tempfile
from pathlib import Path

import pytest

from agentforge.core.artifact_store import (
    FileArtifactStore,
    InMemoryArtifactStore,
    get_json,
    put_json,
)


def test_in_memory_put_get_roundtrip() -> None:
    store = InMemoryArtifactStore()
    meta = store.put("k1", b"hello", content_type="text/plain", labels={"a": "1"})
    assert meta.byte_length == 5
    art = store.get("k1")
    assert art is not None
    assert art.body == b"hello"
    assert art.meta.sha256


def test_in_memory_delete_and_list() -> None:
    store = InMemoryArtifactStore()
    store.put("a/x", b"1")
    store.put("a/y", b"2")
    store.put("b/z", b"3")
    assert set(store.list_keys(prefix="a/")) == {"a/x", "a/y"}
    assert store.delete("a/x") is True
    assert store.get("a/x") is None


def test_put_json_get_json() -> None:
    store = InMemoryArtifactStore()
    put_json(store, "cfg", {"x": [1, 2]})
    obj = get_json(store, "cfg")
    assert obj == {"x": [1, 2]}


def test_file_store_roundtrip() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = FileArtifactStore(td)
        store.put("nested/key", b"data", labels={"env": "test"})
        art = store.get("nested/key")
        assert art is not None
        assert art.body == b"data"
        assert "nested/key" in store.list_keys()


def test_file_store_integrity_error() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = FileArtifactStore(td)
        store.put("k", b"ok")
        body_path = Path(td) / "k"
        assert body_path.is_file()
        body_path.write_bytes(b"x")
        with pytest.raises(ValueError, match="integrity"):
            store.get("k")


def test_file_store_rejects_traversal() -> None:
    with tempfile.TemporaryDirectory() as td:
        store = FileArtifactStore(td)
        with pytest.raises(ValueError):
            store.put("../evil", b"x")


def test_open_default_uses_memory_without_env(monkeypatch: pytest.MonkeyPatch) -> None:
    from agentforge.core import artifact_store as mod

    monkeypatch.delenv("AGENTFORGE_ARTIFACT_DIR", raising=False)
    s = mod.open_default_artifact_store()
    assert isinstance(s, mod.InMemoryArtifactStore)
