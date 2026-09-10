"""Retention: delete each game's stored folder (audio + game.json) once it's
older than `ISAFAN_GAME_TTL`.

`purge_expired` is a plain function so it can be called on startup and unit
tested; `retention_loop` runs it on an interval for the life of the process.
Every read/delete goes through the `Storage` interface so this keeps working
after a move to object storage (see backlog Phase 7).
"""

from __future__ import annotations

import asyncio
import time

from .game import GAMES_PREFIX, GameRegistry, read_game_meta
from .storage import Storage

# Wall-clock time the retention loop last finished a sweep; None until the first
# one runs. The admin status page reads this to show "next purge".
last_sweep_at: float | None = None


def _game_age_seconds(storage: Storage, code: str, now: float) -> float | None:
    """Best-effort age of a stored game. Prefers `createdAt` from game.json;
    falls back to the most recent last-modified time across the folder's files.
    Returns None when nothing is readable, so the caller leaves it alone."""
    try:
        return max(0.0, now - float(read_game_meta(storage, code)["createdAt"]))
    except (KeyError, TypeError, ValueError):
        pass
    mtimes = [
        m
        for child in storage.list_children(f"{GAMES_PREFIX}/{code}")
        if (m := storage.modified_at(f"{GAMES_PREFIX}/{code}/{child}")) is not None
    ]
    return max(0.0, now - max(mtimes)) if mtimes else None


def purge_expired(
    registry: GameRegistry, storage: Storage, ttl_seconds: int
) -> list[str]:
    """Delete every stored game folder older than `ttl_seconds` and drop it from
    the in-memory registry. Returns the codes purged. A non-positive ttl
    disables purging (returns [])."""
    if ttl_seconds <= 0:
        return []
    now = time.time()
    purged: list[str] = []
    for code in storage.list_children(GAMES_PREFIX):
        age = _game_age_seconds(storage, code, now)
        if age is None or age < ttl_seconds:
            continue
        storage.delete(f"{GAMES_PREFIX}/{code}")
        registry.drop(code)
        purged.append(code)
    return purged


async def retention_loop(
    registry: GameRegistry,
    storage: Storage,
    ttl_seconds: int,
    interval_seconds: int,
) -> None:
    """Sweep once now, then every `interval_seconds` until cancelled. A failed
    sweep is logged and the loop continues."""
    global last_sweep_at
    while True:
        try:
            purged = await asyncio.to_thread(
                purge_expired, registry, storage, ttl_seconds
            )
            last_sweep_at = time.time()
            if purged:
                print(
                    f"[isafan] retention: purged {len(purged)} expired game(s): "
                    + ", ".join(purged),
                    flush=True,
                )
        except Exception as exc:  # a bad sweep must not kill the loop
            print(f"[isafan] retention sweep failed: {exc!r}", flush=True)
        await asyncio.sleep(max(1, interval_seconds))
