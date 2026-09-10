"""Numbers for the admin status page. Split out from the route so it's easy to
test. Everything goes through the registry + `Storage` interface; the free/total
volume figures are filesystem-only and simply omitted on a non-local backend."""

from __future__ import annotations

import json
import shutil
import time
from pathlib import Path

from .. import retention
from ..config import Settings
from ..game import GAMES_PREFIX, GameRegistry, read_game_meta
from ..storage import Storage


def _is_clip(name: str) -> bool:
    return name.endswith(".wav") or "_source." in name


def collect(
    registry: GameRegistry,
    storage: Storage,
    settings: Settings,
    *,
    start_time: float,
) -> dict:
    now = time.time()

    active = [
        {
            "code": g.code,
            "mode": g.mode,
            "phase": g.phase.value,
            "round_no": g.round_no,
            "players": len(g.players),
            "connected": sum(1 for p in g.players.values() if p.connected),
            "age_seconds": now - g.created_at,
        }
        for g in sorted(registry.all(), key=lambda g: g.created_at)
    ]

    stored_codes = storage.list_children(GAMES_PREFIX)
    clip_count = 0
    clip_bytes = 0
    created_times: list[float] = []
    for code in stored_codes:
        for name in storage.list_children(f"{GAMES_PREFIX}/{code}"):
            if _is_clip(name):
                clip_count += 1
                clip_bytes += storage.size(f"{GAMES_PREFIX}/{code}/{name}") or 0
        try:
            created_times.append(float(read_game_meta(storage, code)["createdAt"]))
        except (KeyError, TypeError, ValueError):
            pass

    try:
        data_bytes = storage.total_bytes()
    except Exception:
        data_bytes = 0

    disk_free: int | None = None
    disk_total: int | None = None
    local_root = storage.local_path("")  # a real dir on a local backend, else None
    if local_root is not None:
        try:
            probe = local_root if local_root.exists() else Path(local_root.anchor or ".")
            usage = shutil.disk_usage(probe)
            disk_free, disk_total = usage.free, usage.total
        except OSError:
            pass

    try:
        songs = json.loads(storage.get_text("assets/songs/manifest.json"))
        song_count = len(songs)
        song_enabled = sum(1 for s in songs if s.get("enabled"))
    except Exception:
        song_count = song_enabled = 0

    ttl = settings.game_ttl_seconds
    interval = settings.purge_interval_seconds
    last_sweep = retention.last_sweep_at
    purge_enabled = ttl > 0 and interval > 0
    next_sweep = last_sweep + interval if last_sweep and purge_enabled else None

    return {
        "uptime_seconds": now - start_time,
        "active_games": active,
        "stored_game_count": len(stored_codes),
        "clip_count": clip_count,
        "clip_bytes": clip_bytes,
        "song_count": song_count,
        "song_enabled_count": song_enabled,
        "data_bytes": data_bytes,
        "disk_free_bytes": disk_free,
        "disk_total_bytes": disk_total,
        "oldest_game_age_seconds": (now - min(created_times)) if created_times else None,
        "newest_game_age_seconds": (now - max(created_times)) if created_times else None,
        "ttl_seconds": ttl,
        "purge_interval_seconds": interval,
        "purge_enabled": purge_enabled,
        "last_sweep_at": last_sweep,
        "next_sweep_at": next_sweep,
    }
