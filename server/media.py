"""Audio upload + download.

POST /api/games/{code}/original   host uploads the sung take; the server reverses
                                  + transcodes it and moves the game to
                                  REVERSED_PLAYBACK.
GET  /api/games/{code}/audio/{name}   serve a stored clip (allow-listed names).
"""

from __future__ import annotations

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


def build_router(registry: GameRegistry, storage: Storage, hub: Hub) -> APIRouter:
    router = APIRouter(prefix="/api/games/{code}")

    @router.post("/original")
    async def upload_original(code: str, file: UploadFile, playerId: str = Form(...)):
        game = registry.get(code)
        if not game:
            raise HTTPException(404, "no game with that code")
        if playerId != game.host_id:
            raise HTTPException(403, "only the host records the original")
        if not audio.ffmpeg_available():
            raise HTTPException(503, "audio processing unavailable (ffmpeg missing)")

        raw = await _read_capped(file, settings.max_upload_bytes)
        if not raw:
            raise HTTPException(400, "empty upload")
        ext = _ext_for(file)

        with tempfile.TemporaryDirectory() as tmp:
            src = Path(tmp) / f"src.{ext}"
            src.write_bytes(raw)

            duration = audio.probe_duration_seconds(src)
            if duration is None:
                raise HTTPException(400, "could not read that file as audio")
            if duration > settings.max_clip_seconds:
                raise HTTPException(
                    400,
                    f"recording is {duration:.0f}s; limit is {settings.max_clip_seconds}s",
                )

            reversed_wav = Path(tmp) / "original_reversed.wav"
            try:
                audio.reverse_to_wav(src, reversed_wav)
            except audio.FfmpegError as e:
                raise HTTPException(422, str(e))

            storage.put_bytes(f"games/{code}/original_source.{ext}", raw)
            storage.put_bytes(
                f"games/{code}/original_reversed.wav", reversed_wav.read_bytes()
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

    @router.get("/audio/{name}")
    def get_audio(code: str, name: str):
        if name == "original_reversed.wav":
            key = f"games/{code}/original_reversed.wav"
        elif name.startswith("original_source.") and name.split(".")[-1] in _SOURCE_EXTS:
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
