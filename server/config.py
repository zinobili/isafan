"""Environment-driven settings. Every value has a safe default so the app runs
with zero configuration during local development."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    data_dir: Path
    storage_backend: str          # "local" now; "s3" added in a later phase
    game_code_length: int
    max_players: int
    static_dir: Path              # built SPA; served only if this dir exists
    dev_cors_origin: str          # Vite dev server origin, for local development
    game_ttl_seconds: int         # retention window for stored audio / metadata
    admin_user: str               # Phase 6
    admin_password_hash: str      # Phase 6


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def load_settings() -> Settings:
    return Settings(
        host=os.environ.get("ISAFAN_HOST", "0.0.0.0"),
        port=_int("ISAFAN_PORT", 8000),
        data_dir=Path(os.environ.get("ISAFAN_DATA_DIR", "data")),
        storage_backend=os.environ.get("ISAFAN_STORAGE", "local"),
        game_code_length=_int("ISAFAN_CODE_LENGTH", 4),
        max_players=_int("ISAFAN_MAX_PLAYERS", 10),
        static_dir=Path(os.environ.get("ISAFAN_STATIC_DIR", "web/dist")),
        dev_cors_origin=os.environ.get("ISAFAN_DEV_CORS_ORIGIN", "http://localhost:5173"),
        game_ttl_seconds=_int("ISAFAN_GAME_TTL", 24 * 60 * 60),
        admin_user=os.environ.get("ISAFAN_ADMIN_USER", "admin"),
        admin_password_hash=os.environ.get("ISAFAN_ADMIN_PASSWORD_HASH", ""),
    )


settings = load_settings()
