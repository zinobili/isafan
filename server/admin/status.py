"""Numbers for the admin status page. Split out from the route so it's easy to
test. The per-game and per-clip figures go through the registry + `Storage`
interface; the raw disk figures are read from the filesystem directly (local
storage only — an S3 backend would surface these differently)."""

from __future__ import annotations

import json
import os
import shutil
import time
from pathlib import Path

from .. import retention
from ..config import Settings
from ..game import GameRegistry
from ..storage import Storage


def _is_clip(name: str) -> bool:
    return name.endswith(".wav") or "_source." in name


def _dir_bytes(path: Path) -> int:
    total = 0
    for root, _dirs, files in os.walk(path):
        for name in files:
            try:
                total += (Path(root) / name).stat().st_size
            except OSError:
                pass
    return total


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

    stored_codes = storage.list_children("games")
    clip_count = 0
    clip_bytes = 0
    created_times: list[float] = []
    for code in stored_codes:
        for name in storage.list_children(f"games/{code}"):
            if _is_clip(name):
                clip_count += 1
                clip_bytes += storage.size(f"games/{code}/{name}") or 0
        try:
            meta = json.loads(storage.get_text(f"games/{code}/game.json"))
            created_times.append(float(meta["createdAt"]))
        except Exception:
            pass

    data_dir = settings.data_dir
    try:
        data_bytes = _dir_bytes(data_dir)
    except OSError:
        data_bytes = 0
    try:
        probe = data_dir if data_dir.exists() else Path(data_dir.anchor or ".")
        usage = shutil.disk_usage(probe)
        disk_free: int | None = usage.free
        disk_total: int | None = usage.total
    except OSError:
        disk_free = disk_total = None

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
