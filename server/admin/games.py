"""Read stored games for the admin recordings browser — entirely through the
`Storage` interface, so it still works for a game that has left memory (and
after a later move to object storage)."""

from __future__ import annotations

import json
import time

from ..clips import is_allowed_clip_name
from ..storage import Storage


def _read_meta(storage: Storage, code: str) -> dict:
    try:
        return json.loads(storage.get_text(f"games/{code}/game.json"))
    except Exception:
        return {}


def list_games(storage: Storage, ttl_seconds: int) -> list[dict]:
    now = time.time()
    rows: list[dict] = []
    for code in storage.list_children("games"):
        meta = _read_meta(storage, code)
        created = meta.get("createdAt")
        rows.append(
            {
                "code": code,
                "mode": meta.get("mode", "?"),
                "phase": meta.get("phase", "?"),
                "players": len(meta.get("players", [])),
                "attempts": len(meta.get("attempts", [])),
                "created_at": created,
                "age_seconds": (now - created) if created else None,
                "expires_in_seconds": (
                    created + ttl_seconds - now
                    if created and ttl_seconds > 0
                    else None
                ),
            }
        )
    rows.sort(key=lambda r: r["created_at"] or 0, reverse=True)
    return rows


def load_game(storage: Storage, code: str) -> dict | None:
    """Metadata + the clip files actually on disk, grouped into original and
    per-attempt. None when nothing is stored under that code."""
    meta = _read_meta(storage, code)
    present = {
        n for n in storage.list_children(f"games/{code}") if is_allowed_clip_name(n)
    }
    if not meta and not present:
        return None

    original = {
        "reversed": "original_reversed.wav" if "original_reversed.wav" in present else None,
        "forward": "original_forward.wav" if "original_forward.wav" in present else None,
        "source": next(
            (n for n in sorted(present) if n.startswith("original_source.")), None
        ),
    }

    attempts: list[dict] = []
    for a in meta.get("attempts", []):
        aid = str(a.get("id", ""))
        rev = f"attempt_{aid}_reversed.wav"
        src = f"attempt_{aid}_source.{a.get('sourceExt', '')}"
        attempts.append(
            {
                "id": aid,
                "name": a.get("name", ""),
                "by": a.get("by", ""),
                "duration_ms": a.get("durationMs"),
                "reversed": rev if rev in present else None,
                "source": src if src in present else None,
            }
        )

    accounted = {c for a in attempts for c in (a["reversed"], a["source"]) if c}
    orphans = sorted(
        n for n in present if n.startswith("attempt_") and n not in accounted
    )
    return {
        "code": code,
        "meta": meta,
        "original": original,
        "attempts": attempts,
        "orphans": orphans,
    }
