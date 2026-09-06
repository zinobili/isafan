"""Storage abstraction.

Everything the game persists (game.json now, audio files later) goes through a
`Storage` instance addressed by string keys like ``games/ABCD/game.json``. The
MVP ships `LocalDiskStorage`; an S3/R2-backed implementation can be dropped in
later without touching callers (see the plan doc, "hosting later").
"""

from __future__ import annotations

import shutil
import time
from abc import ABC, abstractmethod
from pathlib import Path


class Storage(ABC):
    # --- core operations backends must implement ---

    @abstractmethod
    def put_bytes(self, key: str, data: bytes) -> None: ...

    @abstractmethod
    def get_bytes(self, key: str) -> bytes: ...

    @abstractmethod
    def exists(self, key: str) -> bool: ...

    @abstractmethod
    def delete(self, key: str) -> None: ...

    @abstractmethod
    def delete_prefix(self, prefix: str) -> None: ...

    @abstractmethod
    def list_prefix(self, prefix: str) -> list[str]: ...

    @abstractmethod
    def modified_at(self, key: str) -> float | None: ...

    @abstractmethod
    def local_path(self, key: str) -> Path | None:
        """A real filesystem path for `key` if the backend has one (lets the API
        stream a file directly). `None` for backends without local files."""

    @abstractmethod
    def purge_older_than(self, max_age_seconds: float, prefix: str = "games") -> list[str]:
        """Delete immediate children of `prefix` older than the cutoff. Returns
        the keys removed. The 24h retention task builds on this."""

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

    def exists(self, key: str) -> bool:
        return self._resolve(key).exists()

    def delete(self, key: str) -> None:
        p = self._resolve(key)
        if p.is_dir():
            shutil.rmtree(p, ignore_errors=True)
        else:
            p.unlink(missing_ok=True)

    def delete_prefix(self, prefix: str) -> None:
        self.delete(prefix)

    def list_prefix(self, prefix: str) -> list[str]:
        base = self._resolve(prefix)
        if not base.exists():
            return []
        if base.is_file():
            return [prefix]
        out: list[str] = []
        for p in sorted(base.rglob("*")):
            if p.is_file():
                out.append(p.relative_to(self._root).as_posix())
        return out

    def modified_at(self, key: str) -> float | None:
        p = self._resolve(key)
        try:
            return p.stat().st_mtime
        except OSError:
            return None

    def local_path(self, key: str) -> Path | None:
        return self._resolve(key)

    def purge_older_than(self, max_age_seconds: float, prefix: str = "games") -> list[str]:
        base = self._resolve(prefix)
        removed: list[str] = []
        if not base.is_dir():
            return removed
        now = time.time()
        for child in base.iterdir():
            try:
                age = now - child.stat().st_mtime
            except OSError:
                continue
            if age > max_age_seconds:
                if child.is_dir():
                    shutil.rmtree(child, ignore_errors=True)
                else:
                    child.unlink(missing_ok=True)
                removed.append(f"{prefix}/{child.name}")
        return removed


def build_storage(backend: str, data_dir: Path) -> Storage:
    if backend == "local":
        return LocalDiskStorage(data_dir)
    raise ValueError(f"unknown storage backend: {backend!r}")
