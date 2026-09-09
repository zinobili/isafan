"""Preloaded reference songs for the admin song library (Phase 6b).

Stored under the ``assets/songs/`` prefix — outside ``games/``, so the retention
sweep never touches them:

    assets/songs/manifest.json        ordered list of song metadata
    assets/songs/<slug>/source.<ext>  the operator's upload, as received
    assets/songs/<slug>/reversed.wav  canonical reversed clip (what players mimic)
    assets/songs/<slug>/forward.wav   canonical forward clip (preview / reveal)

The manifest is the source of truth for order + metadata. Each entry:

    {slug, name, enabled, sourceExt, durationMs, addedAt,
     lines: [{startMs, endMs, label}]}   # `lines` empty unless it's a relay song
"""

from __future__ import annotations

import json
import re
import time

from fastapi import UploadFile

from .ingest import ingest_reversed
from .storage import Storage

PREFIX = "assets/songs"
MANIFEST_KEY = f"{PREFIX}/manifest.json"
MAX_NAME_LEN = 80
MAX_LABEL_LEN = 60

_SLUG_RE = re.compile(r"[^a-z0-9]+")


def slugify(name: str) -> str:
    return _SLUG_RE.sub("-", (name or "").strip().lower()).strip("-") or "song"


def clean_lines(raw) -> list[dict]:
    """Normalise a relay line list: non-negative ints, end >= start, trimmed
    label, sorted by start. Bad rows are dropped rather than raising."""
    out: list[dict] = []
    for item in raw or []:
        try:
            start = max(0, int(item["startMs"]))
            end = max(start, int(item["endMs"]))
        except (KeyError, TypeError, ValueError):
            continue
        label = str(item.get("label", "")).strip()[:MAX_LABEL_LEN]
        out.append({"startMs": start, "endMs": end, "label": label})
    out.sort(key=lambda ln: ln["startMs"])
    return out


class SongLibrary:
    def __init__(self, storage: Storage) -> None:
        self._storage = storage

    # --- manifest io ---------------------------------------------------

    def _load(self) -> list[dict]:
        try:
            data = json.loads(self._storage.get_text(MANIFEST_KEY))
        except Exception:
            return []
        return data if isinstance(data, list) else []

    def _save(self, songs: list[dict]) -> None:
        self._storage.put_text(MANIFEST_KEY, json.dumps(songs, indent=2))

    # --- reads -------------------------------------------------------

    def list(self) -> list[dict]:
        return self._load()

    def get(self, slug: str) -> dict | None:
        return next((s for s in self._load() if s.get("slug") == slug), None)

    def enabled_public(self) -> list[dict]:
        """The enabled songs, trimmed to what a game client needs to pick one."""
        return [
            {
                "slug": s["slug"],
                "name": s["name"],
                "durationMs": s.get("durationMs", 0),
                "lineCount": len(s.get("lines") or []),
            }
            for s in self._load()
            if s.get("enabled")
        ]

    def copy_original_into(self, slug: str, dest_prefix: str) -> dict | None:
        """Copy an enabled song's reversed / forward / source clips to
        ``{dest_prefix}_reversed.wav`` etc. (e.g. dest_prefix
        ``games/ABCD/original``) so a game can use a library song as its
        original with nothing downstream changed. Returns the song entry, or
        None if the slug is unknown or disabled."""
        song = self.get(slug)
        if not song or not song.get("enabled"):
            return None
        ext = song.get("sourceExt", "bin")
        for src, dst in (
            (f"{PREFIX}/{slug}/reversed.wav", f"{dest_prefix}_reversed.wav"),
            (f"{PREFIX}/{slug}/forward.wav", f"{dest_prefix}_forward.wav"),
            (f"{PREFIX}/{slug}/source.{ext}", f"{dest_prefix}_source.{ext}"),
        ):
            try:
                self._storage.put_bytes(dst, self._storage.get_bytes(src))
            except Exception:
                if dst.endswith("_reversed.wav"):
                    return None  # the reversed clip is mandatory
        return song

    def clip_key(self, slug: str, kind: str) -> str | None:
        """Storage key for a song's `reversed` / `forward` / `source` clip, or
        None if the song or kind is unknown."""
        song = self.get(slug)
        if not song:
            return None
        if kind in ("reversed", "forward"):
            return f"{PREFIX}/{slug}/{kind}.wav"
        if kind == "source":
            return f"{PREFIX}/{slug}/source.{song.get('sourceExt', 'bin')}"
        return None

    # --- writes ----------------------------------------------------

    def _unique_slug(self, name: str, songs: list[dict]) -> str:
        base = slugify(name)
        taken = {s.get("slug") for s in songs}
        if base not in taken:
            return base
        i = 2
        while f"{base}-{i}" in taken:
            i += 1
        return f"{base}-{i}"

    async def add(self, name: str, file: UploadFile, *, max_seconds: int) -> dict:
        name = (name or "").strip()
        if not name:
            name = (file.filename or "Untitled").rsplit(".", 1)[0].strip() or "Untitled"
        name = name[:MAX_NAME_LEN]

        songs = self._load()
        slug = self._unique_slug(name, songs)
        duration, ext = await ingest_reversed(
            file,
            self._storage,
            source_key=f"{PREFIX}/{slug}/source",
            reversed_key=f"{PREFIX}/{slug}/reversed.wav",
            forward_key=f"{PREFIX}/{slug}/forward.wav",
            max_seconds=max_seconds,
        )
        entry = {
            "slug": slug,
            "name": name,
            "enabled": True,
            "sourceExt": ext,
            "durationMs": round(duration * 1000),
            "addedAt": time.time(),
            "lines": [],
        }
        songs.append(entry)
        self._save(songs)
        return entry

    def _update(self, slug: str, **changes) -> dict | None:
        songs = self._load()
        for s in songs:
            if s.get("slug") == slug:
                s.update(changes)
                self._save(songs)
                return s
        return None

    def rename(self, slug: str, name: str) -> dict | None:
        name = (name or "").strip()[:MAX_NAME_LEN]
        return self._update(slug, name=name) if name else None

    def set_enabled(self, slug: str, on: bool) -> dict | None:
        return self._update(slug, enabled=bool(on))

    def set_lines(self, slug: str, lines) -> dict | None:
        return self._update(slug, lines=clean_lines(lines))

    def delete(self, slug: str) -> bool:
        songs = self._load()
        kept = [s for s in songs if s.get("slug") != slug]
        if len(kept) == len(songs):
            return False
        self._storage.delete(f"{PREFIX}/{slug}")
        self._save(kept)
        return True
