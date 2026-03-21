"""Named artifact storage for pipeline steps — in-memory and filesystem backends."""

from __future__ import annotations

import hashlib
import json
import os
import threading
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class ArtifactMeta:
    """Metadata for a stored artifact."""

    key: str
    content_type: str
    byte_length: int
    sha256: str
    created_at_epoch: float
    labels: dict[str, str] = field(default_factory=dict)


@dataclass
class StoredArtifact:
    """Payload plus metadata."""

    meta: ArtifactMeta
    body: bytes


class ArtifactStore(ABC):
    """Abstract store for opaque byte blobs keyed by string."""

    @abstractmethod
    def put(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = "application/octet-stream",
        labels: dict[str, str] | None = None,
    ) -> ArtifactMeta:
        """Persist bytes under key; replace if exists."""

    @abstractmethod
    def get(self, key: str) -> StoredArtifact | None:
        """Return artifact or None."""

    @abstractmethod
    def delete(self, key: str) -> bool:
        """Remove key; return True if something was removed."""

    @abstractmethod
    def list_keys(self, *, prefix: str = "") -> list[str]:
        """List keys optionally filtered by prefix."""

    @abstractmethod
    def exists(self, key: str) -> bool:
        """Return True if key is present."""


def _sha256(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


class InMemoryArtifactStore(ArtifactStore):
    """Thread-safe RAM-backed store suitable for tests and single-process pipelines."""

    def __init__(self) -> None:
        self._data: dict[str, StoredArtifact] = {}
        self._lock = threading.RLock()

    def put(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = "application/octet-stream",
        labels: dict[str, str] | None = None,
    ) -> ArtifactMeta:
        if not key.strip():
            raise ValueError("key must be non-empty")
        digest = _sha256(body)
        now = time.time()
        meta = ArtifactMeta(
            key=key,
            content_type=content_type,
            byte_length=len(body),
            sha256=digest,
            created_at_epoch=now,
            labels=dict(labels or {}),
        )
        artifact = StoredArtifact(meta=meta, body=bytes(body))
        with self._lock:
            self._data[key] = artifact
        return meta

    def get(self, key: str) -> StoredArtifact | None:
        with self._lock:
            art = self._data.get(key)
            if art is None:
                return None
            return StoredArtifact(meta=art.meta, body=bytes(art.body))

    def delete(self, key: str) -> bool:
        with self._lock:
            if key in self._data:
                del self._data[key]
                return True
            return False

    def list_keys(self, *, prefix: str = "") -> list[str]:
        with self._lock:
            keys = sorted(self._data.keys())
        if not prefix:
            return keys
        return [k for k in keys if k.startswith(prefix)]

    def exists(self, key: str) -> bool:
        with self._lock:
            return key in self._data


class FileArtifactStore(ArtifactStore):
    """Filesystem-backed store with one file per key under a base directory."""

    def __init__(self, base_dir: str | Path) -> None:
        self._base = Path(base_dir)
        self._base.mkdir(parents=True, exist_ok=True)
        self._meta_dir = self._base / ".meta"
        self._meta_dir.mkdir(parents=True, exist_ok=True)
        self._lock = threading.RLock()

    def _safe_path(self, key: str) -> Path:
        """Map key to nested path; reject path traversal."""
        if ".." in key or key.startswith("/"):
            raise ValueError("invalid key")
        parts = [p for p in key.replace("\\", "/").split("/") if p and p != "."]
        if not parts:
            raise ValueError("invalid key")
        path = self._base.joinpath(*parts)
        try:
            path.resolve().relative_to(self._base.resolve())
        except ValueError as e:
            raise ValueError("invalid key") from e
        path.parent.mkdir(parents=True, exist_ok=True)
        return path

    def _meta_path(self, key: str) -> Path:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return self._meta_dir / f"{digest}.json"

    def put(
        self,
        key: str,
        body: bytes,
        *,
        content_type: str = "application/octet-stream",
        labels: dict[str, str] | None = None,
    ) -> ArtifactMeta:
        path = self._safe_path(key)
        digest = _sha256(body)
        now = time.time()
        meta = ArtifactMeta(
            key=key,
            content_type=content_type,
            byte_length=len(body),
            sha256=digest,
            created_at_epoch=now,
            labels=dict(labels or {}),
        )
        payload = {
            "key": meta.key,
            "content_type": meta.content_type,
            "byte_length": meta.byte_length,
            "sha256": meta.sha256,
            "created_at_epoch": meta.created_at_epoch,
            "labels": meta.labels,
        }
        with self._lock:
            path.write_bytes(body)
            self._meta_path(key).write_text(json.dumps(payload, indent=2), encoding="utf-8")
        return meta

    def get(self, key: str) -> StoredArtifact | None:
        try:
            path = self._safe_path(key)
        except ValueError:
            return None
        mp = self._meta_path(key)
        if not path.is_file() or not mp.is_file():
            return None
        with self._lock:
            body = path.read_bytes()
            raw = json.loads(mp.read_text(encoding="utf-8"))
        meta = ArtifactMeta(
            key=raw["key"],
            content_type=raw["content_type"],
            byte_length=int(raw["byte_length"]),
            sha256=raw["sha256"],
            created_at_epoch=float(raw["created_at_epoch"]),
            labels=dict(raw.get("labels") or {}),
        )
        if _sha256(body) != meta.sha256:
            raise ValueError(f"artifact integrity check failed for {key!r}")
        return StoredArtifact(meta=meta, body=body)

    def delete(self, key: str) -> bool:
        try:
            path = self._safe_path(key)
        except ValueError:
            return False
        mp = self._meta_path(key)
        with self._lock:
            removed = False
            if path.is_file():
                path.unlink()
                removed = True
            if mp.is_file():
                mp.unlink()
            return removed

    def list_keys(self, *, prefix: str = "") -> list[str]:
        keys: list[str] = []
        if not self._base.exists():
            return keys
        for p in self._base.rglob("*"):
            if not p.is_file() or p.parent == self._meta_dir:
                continue
            rel = p.relative_to(self._base)
            if rel.parts and rel.parts[0] == ".meta":
                continue
            key = "/".join(rel.parts)
            if not prefix or key.startswith(prefix):
                keys.append(key)
        return sorted(keys)

    def exists(self, key: str) -> bool:
        try:
            path = self._safe_path(key)
        except ValueError:
            return False
        return path.is_file()


def put_json(store: ArtifactStore, key: str, obj: Any, *, labels: dict[str, str] | None = None) -> ArtifactMeta:
    """Serialize object to UTF-8 JSON and store."""
    raw = json.dumps(obj, ensure_ascii=False, indent=2).encode("utf-8")
    return store.put(key, raw, content_type="application/json", labels=labels)


def get_json(store: ArtifactStore, key: str) -> Any | None:
    """Load JSON artifact or None."""
    art = store.get(key)
    if art is None:
        return None
    return json.loads(art.body.decode("utf-8"))


def open_default_artifact_store(
    env_var: str = "AGENTFORGE_ARTIFACT_DIR",
) -> ArtifactStore:
    """Return FileArtifactStore when env var is set and directory exists or can be created; else in-memory."""
    path = os.environ.get(env_var)
    if path:
        return FileArtifactStore(path)
    return InMemoryArtifactStore()
