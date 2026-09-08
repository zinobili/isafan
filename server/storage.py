"""Storage abstraction.

Everything the game persists (game.json, audio clips) goes through a `Storage`
instance addressed by string keys like ``games/ABCD/original_reversed.wav``. The
MVP ships `LocalDiskStorage`; an S3/R2 backend can be added behind the same
interface without touching callers (see the plan doc, "hosting later").
"""

from __future__ import annotations

import shutil
from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def delete(self, key: str) -> None:
        """Remove `key`. A no-op if it doesn't exist."""

    @abstractmethod
    def list_children(self, prefix: str) -> list[str]:
        """Immediate child names under `prefix` — one level of ``ls``, not a deep
        walk. Empty when the prefix holds nothing. Used by retention to
        enumerate stored games (``list_children("games")`` -> room codes)."""

    @abstractmethod
    def local_path(self, key: str) -> Path | None:
        """A real filesystem path for `key` if the backend has one (lets the API
        stream a file directly). `None` for backends without local files."""

    # --- text convenience, shared by all backends ---

    def put_text(self, key: str, text: str) -> None:
        self.put_bytes(key, text.encode("utf-8"))

    def get_text(self, key: str) -> str:
        return self.get_bytes(key).decode("utf-8")


class LocalDiskStorage(Storage):
    def __init__(self, root: Path) -> None:
        self._root = Path(root).resolve()
        self._root.mkdir(parents=True, exist_ok=True)

    def _resolve(self, key: str) -> Path:
        p = (self._root / key).resolve()
        if p != self._root and self._root not in p.parents:
            raise ValueError(f"key escapes storage root: {key!r}")
        return p

    def put_bytes(self, key: str, data: bytes) -> None:
        p = self._resolve(key)
        p.parent.mkdir(parents=True, exist_ok=True)
        tmp = p.with_suffix(p.suffix + ".tmp")
        tmp.write_bytes(data)
        tmp.replace(p)

    def get_bytes(self, key: str) -> bytes:
        return self._resolve(key).read_bytes()

    def delete(self, key: str) -> None:
        p = self._resolve(key)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)

    def list_children(self, prefix: str) -> list[str]:
        p = self._resolve(prefix)
        if not p.is_dir():
            return []
        return sorted(entry.name for entry in p.iterdir())

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)


def build_storage(backend: str, data_dir: Path) -> Storage:
    if backend == "local":
        return LocalDiskStorage(data_dir)
    raise ValueError(f"unknown storage backend: {backend!r}")
