"""Audio upload + download.

POST /api/games/{code}/original    the sung take; reversed + transcoded, moves
                                   the game to REVERSED_PLAYBACK.
POST /api/games/{code}/attempts    one player's mimic; reversed + transcoded,
                                   appended to the game's attempts.
GET  /api/games/{code}/audio/{name}   serve a stored clip (allow-listed names).

In multi-device mode `/original` is host-only and `/attempts` requires a known
playerId. Solo mode (one device, pass-the-phone) skips both checks.
"""

from __future__ import annotations

import re
import tempfile
import time
from pathlib import Path

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from . import audio
from .config import settings
from .game import GameRegistry, Phase
from .storage import Storage
from .ws import Hub

_EXT_BY_MIME = {
    "audio/webm": "webm",
    "video/webm": "webm",
    "audio/ogg": "ogg",
    "audio/mp4": "mp4",
    "video/mp4": "mp4",
    "audio/aac": "aac",
    "audio/mpeg": "mp3",
    "audio/wav": "wav",
    "audio/x-wav": "wav",
    "audio/wave": "wav",
}
_MEDIA_TYPE_BY_EXT = {
    "wav": "audio/wav",
    "webm": "audio/webm",
    "ogg": "audio/ogg",
    "mp4": "audio/mp4",
    "aac": "audio/aac",
    "mp3": "audio/mpeg",
}
_SOURCE_EXTS = tuple(_MEDIA_TYPE_BY_EXT)
_ATTEMPT_REVERSED_RE = re.compile(r"^attempt_[A-Za-z0-9_-]{1,16}_reversed\.wav$")
_ATTEMPT_SOURCE_RE = re.compile(
    r"^attempt_[A-Za-z0-9_-]{1,16}_source\.(" + "|".join(_SOURCE_EXTS) + r")$"
)


async def _read_capped(file: UploadFile, limit: int) -> bytes:
    buf = bytearray()
    while chunk := await file.read(1 << 16):
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(413, f"recording too large (limit {limit} bytes)")
    return bytes(buf)


def _ext_for(file: UploadFile) -> str:
    if file.content_type:
        base = _EXT_BY_MIME.get(file.content_type.split(";")[0].strip().lower())
        if base:
            return base
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    return suffix if suffix in _MEDIA_TYPE_BY_EXT else "bin"


async def _ingest_reversed(
    file: UploadFile,
    code: str,
    storage: Storage,
    *,
    source_key: str,
    reversed_key: str,
    forward_key: str | None = None,
) -> tuple[float, str]:
    """Read an upload, store it, produce + store its reversed WAV (and, if
    `forward_key` is given, a non-reversed WAV too — used so the reveal screen
    can play the original the way it was actually sung). Returns
    (duration_seconds, source_ext)."""
    if not audio.ffmpeg_available():
        raise HTTPException(503, "audio processing unavailable (ffmpeg missing)")

    raw = await _read_capped(file, settings.max_upload_bytes)
    if not raw:
        raise HTTPException(400, "empty upload")
    ext = _ext_for(file)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"src.{ext}"
        src.write_bytes(raw)
        out = Path(tmp) / "reversed.wav"

        try:
            audio.reverse_to_wav(src, out)
        except audio.FfmpegError:
            raise HTTPException(400, "could not read that file as audio")

        duration = audio.wav_duration_seconds(out)
        if not duration:
            raise HTTPException(400, "recording was empty")
        if duration > settings.max_clip_seconds:
            raise HTTPException(
                400, f"recording is {duration:.0f}s; limit is {settings.max_clip_seconds}s"
            )

        storage.put_bytes(f"{source_key}.{ext}", raw)
        storage.put_bytes(reversed_key, out.read_bytes())

        if forward_key:
            fwd = Path(tmp) / "forward.wav"
            try:
                audio.transcode_to_wav(src, fwd)
                storage.put_bytes(forward_key, fwd.read_bytes())
            except audio.FfmpegError:
                pass  # non-fatal — the forward copy is a comparison aid

    return duration, ext


def build_router(registry: GameRegistry, storage: Storage, hub: Hub) -> APIRouter:
    router = APIRouter(prefix="/api/games/{code}")

    @router.post("/original")
    async def upload_original(code: str, file: UploadFile, playerId: str = Form("")):
        game = registry.get(code)
        if not game:
            raise HTTPException(404, "no game with that code")
        if game.mode != "solo" and playerId != game.host_id:
            raise HTTPException(403, "only the host records the original")

        duration, ext = await _ingest_reversed(
            file, code, storage,
            source_key=f"games/{code}/original_source",
            reversed_key=f"games/{code}/original_reversed.wav",
            forward_key=f"games/{code}/original_forward.wav",
        )
        game.original = {
            "durationMs": round(duration * 1000),
            "sourceExt": ext,
            "uploadedBy": playerId,
            "at": time.time(),
        }
        game.phase = Phase.REVERSED_PLAYBACK
        registry.persist(game)
        await hub.broadcast(code)
        return {"ok": True, **game.original_public()}

    @router.post("/attempts")
    async def upload_attempt(
        code: str, file: UploadFile, name: str = Form(""), playerId: str = Form("")
    ):
        game = registry.get(code)
        if not game:
            raise HTTPException(404, "no game with that code")
        if not game.original:
            raise HTTPException(409, "no original recorded yet")

        if game.mode == "solo":
            # pass-the-phone: takes append, phase advances leniently
            if game.phase is not Phase.AUDIENCE_RECORDING:
                game.phase = Phase.AUDIENCE_RECORDING
        else:
            if playerId not in game.players:
                raise HTTPException(403, "join the game before submitting a take")
            if game.phase is not Phase.AUDIENCE_RECORDING:
                raise HTTPException(409, "the round isn't taking takes right now")
            # one take per player — a resubmission replaces the previous one
            prev = next((a for a in game.attempts if a["by"] == playerId), None)
            if prev:
                storage.delete(f"games/{code}/attempt_{prev['id']}_reversed.wav")
                storage.delete(f"games/{code}/attempt_{prev['id']}_source.{prev['sourceExt']}")
                game.attempts = [a for a in game.attempts if a["id"] != prev["id"]]

        eid = game.new_attempt_id()
        duration, ext = await _ingest_reversed(
            file, code, storage,
            source_key=f"games/{code}/attempt_{eid}_source",
            reversed_key=f"games/{code}/attempt_{eid}_reversed.wav",
        )
        entry = game.add_attempt(
            id=eid, name=name, source_ext=ext, duration_ms=round(duration * 1000), by=playerId
        )
        registry.persist(game)
        await hub.broadcast(code)
        return {
            "id": eid,
            "name": entry["name"],
            "durationMs": entry["durationMs"],
            "url": game.audio_url(f"attempt_{eid}_reversed.wav"),
        }

    @router.get("/audio/{name}")
    def get_audio(code: str, name: str):
        if name in ("original_reversed.wav", "original_forward.wav") or (
            name.startswith("original_source.") and name.split(".")[-1] in _SOURCE_EXTS
        ):
            key = f"games/{code}/{name}"
        elif _ATTEMPT_REVERSED_RE.match(name) or _ATTEMPT_SOURCE_RE.match(name):
            key = f"games/{code}/{name}"
        else:
            raise HTTPException(404, "unknown clip")

        path = storage.local_path(key)
        if path is None or not path.is_file():
            raise HTTPException(404, "clip not found")
        ext = name.rsplit(".", 1)[-1]
        return FileResponse(
            path,
            media_type=_MEDIA_TYPE_BY_EXT.get(ext, "application/octet-stream"),
            headers={"Cache-Control": "no-store"},
        )

    return router
