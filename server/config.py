"""Environment-driven settings. Every value has a safe default so the app runs
with zero configuration during local development."""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from .net import lan_ips

try:  # load a local .env if present; harmless if the package is missing
    from dotenv import load_dotenv

    load_dotenv()
except ImportError:  # pragma: no cover
    pass


@dataclass(frozen=True)
class Settings:
    host: str
    port: int
    public_url: str               # join-link / QR base. Explicit ISAFAN_PUBLIC_URL,
                                  # else an auto-detected LAN address, else "" (use
                                  # the origin the host screen was opened with).
    public_url_candidates: tuple[str, ...]  # all reachable bases, best guess first
    public_url_source: str        # "config" | "detected" | "origin"
    data_dir: Path
    storage_backend: str          # "local" now; "s3" added in a later phase
    game_code_length: int
    max_players: int
    static_dir: Path              # built SPA; served only if this dir exists
    dev_cors_origin: str          # Vite dev server origin, for local development
    game_ttl_seconds: int         # retention window for stored audio / metadata
    purge_interval_seconds: int   # how often the retention sweep runs (0 = off)
    create_rate: int              # game-create burst allowed per client IP (0 = off)
    create_rate_window: int       # seconds for that burst to refill
    ffmpeg_path: str              # override; "" = bundled (imageio-ffmpeg) or PATH
    audio_sample_rate: int        # canonical WAV sample rate
    max_clip_seconds: int         # reject recordings longer than this
    max_upload_bytes: int         # reject uploads larger than this
    ssl_certfile: str             # set both to serve HTTPS (e.g. an mkcert pair)
    ssl_keyfile: str              # so phones on the LAN can record in-page


def _int(name: str, default: int) -> int:
    try:
        return int(os.environ.get(name, "").strip() or default)
    except ValueError:
        return default


def _resolve_public_url(port: int) -> tuple[str, tuple[str, ...], str]:
    """(chosen base, all candidate bases, source). Explicit env wins; otherwise
    fall back to auto-detected LAN addresses; otherwise empty (client uses its
    own origin)."""
    explicit = os.environ.get("ISAFAN_PUBLIC_URL", "").strip().rstrip("/")
    if explicit:
        return explicit, (explicit,), "config"
    try:
        candidates = tuple(f"http://{ip}:{port}" for ip in lan_ips())
    except Exception:  # detection must never break startup
        candidates = ()
    if candidates:
        return candidates[0], candidates, "detected"
    return "", (), "origin"


def load_settings() -> Settings:
    port = _int("ISAFAN_PORT", 8000)
    public_url, public_url_candidates, public_url_source = _resolve_public_url(port)
    return Settings(
        host=os.environ.get("ISAFAN_HOST", "0.0.0.0"),
        port=port,
        public_url=public_url,
        public_url_candidates=public_url_candidates,
        public_url_source=public_url_source,
        data_dir=Path(os.environ.get("ISAFAN_DATA_DIR", "data")),
        storage_backend=os.environ.get("ISAFAN_STORAGE", "local"),
        game_code_length=_int("ISAFAN_CODE_LENGTH", 4),
        max_players=_int("ISAFAN_MAX_PLAYERS", 10),
        static_dir=Path(os.environ.get("ISAFAN_STATIC_DIR", "web/dist")),
        dev_cors_origin=os.environ.get("ISAFAN_DEV_CORS_ORIGIN", "http://localhost:5173"),
        game_ttl_seconds=_int("ISAFAN_GAME_TTL", 24 * 60 * 60),
        purge_interval_seconds=_int("ISAFAN_PURGE_INTERVAL", 60 * 60),
        create_rate=_int("ISAFAN_CREATE_RATE", 10),
        create_rate_window=_int("ISAFAN_CREATE_RATE_WINDOW", 60),
        ffmpeg_path=os.environ.get("ISAFAN_FFMPEG", "").strip(),
        audio_sample_rate=_int("ISAFAN_AUDIO_SR", 16_000),
        max_clip_seconds=_int("ISAFAN_MAX_CLIP_SECONDS", 45),
        max_upload_bytes=_int("ISAFAN_MAX_UPLOAD_BYTES", 25 * 1024 * 1024),
        ssl_certfile=os.environ.get("ISAFAN_SSL_CERT", "").strip(),
        ssl_keyfile=os.environ.get("ISAFAN_SSL_KEY", "").strip(),
    )


settings = load_settings()
