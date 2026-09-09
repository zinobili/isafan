"""Storage abstraction.

Everything the game persists (game.json, audio clips) goes through a `Storage`
instance addressed by string keys like ``games/ABCD/original_reversed.wav``.
`LocalDiskStorage` is the default; `S3Storage` (``ISAFAN_STORAGE=s3``) puts the
same keys in an S3/R2 bucket. Callers never touch the filesystem directly —
they serve clips via `file_response` and read sizes/times via `size` /
`modified_at` / `total_bytes` — so both backends are interchangeable.
"""

from __future__ import annotations

import os
import shutil
from abc import ABC, abstractmethod
from pathlib import Path

from starlette.responses import FileResponse, Response


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
    def size(self, key: str) -> int | None:
        """Size in bytes of the object at `key`, or None if it doesn't exist."""

    @abstractmethod
    def modified_at(self, key: str) -> float | None:
        """Last-modified time of `key` as a unix timestamp, or None if missing."""

    @abstractmethod
    def total_bytes(self) -> int:
        """Total size of everything in the store (for the admin status page)."""

    @abstractmethod
    def local_path(self, key: str) -> Path | None:
        """A real filesystem path for `key` if the backend has one (lets the API
        stream a file directly). `None` for backends without local files —
        callers should use `file_response` instead of assuming a path."""

    @abstractmethod
    def file_response(self, key: str, *, media_type: str) -> Response | None:
        """A ready-to-return HTTP response that serves the object at `key`, or
        None if it is missing. Local disk streams the file off disk; other
        backends read it into memory (clips are small)."""

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

    def size(self, key: str) -> int | None:
        p = self._resolve(key)
        try:
            return p.stat().st_size if p.is_file() else None
        except OSError:
            return None

    def modified_at(self, key: str) -> float | None:
        p = self._resolve(key)
        try:
            return p.stat().st_mtime if p.exists() else None
        except OSError:
            return None

    def total_bytes(self) -> int:
        total = 0
        for root, _dirs, files in os.walk(self._root):
            for name in files:
                try:
                    total += (Path(root) / name).stat().st_size
                except OSError:
                    pass
        return total

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)

    def file_response(self, key: str, *, media_type: str) -> Response | None:
        p = self._resolve(key)
        if not p.is_file():
            return None
        return FileResponse(
            p, media_type=media_type, headers={"Cache-Control": "no-store"}
        )


def build_storage(backend: str, data_dir: Path) -> Storage:
    if backend == "local":
        return LocalDiskStorage(data_dir)
    if backend == "s3":
        from .s3storage import S3Storage

        return S3Storage.from_env()
    raise ValueError(f"unknown storage backend: {backend!r}")
