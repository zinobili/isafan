"""Turn an uploaded audio blob into our canonical clips.

The pipeline — cap the read, hand ffmpeg the bytes, keep the reversed WAV (and
optionally a forward WAV), enforce a duration limit, write everything through
`Storage` — is shared by the in-game upload routes (`media.py`) and the admin
song library (`songs.py`), so it lives here with no game/ws imports.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import anyio
from fastapi import HTTPException, UploadFile

from . import audio
from .clips import EXT_BY_MIME, MEDIA_TYPE_BY_EXT
from .config import settings
from .storage import Storage


async def read_capped(file: UploadFile, limit: int) -> bytes:
    # Reject early when the multipart part declares a size over the limit, so an
    # oversized upload doesn't get buffered up to `limit` first. The streaming
    # check below stays the real guard (a client can lie about / omit the size).
    if file.size is not None and file.size > limit:
        raise HTTPException(413, f"recording too large (limit {limit} bytes)")
    buf = bytearray()
    while chunk := await file.read(1 << 16):
        buf += chunk
        if len(buf) > limit:
            raise HTTPException(413, f"recording too large (limit {limit} bytes)")
    return bytes(buf)


def ext_for(file: UploadFile) -> str:
    if file.content_type:
        base = EXT_BY_MIME.get(file.content_type.split(";")[0].strip().lower())
        if base:
            return base
    suffix = Path(file.filename or "").suffix.lstrip(".").lower()
    return suffix if suffix in MEDIA_TYPE_BY_EXT else "bin"


async def ingest_reversed(
    file: UploadFile,
    storage: Storage,
    *,
    source_key: str,
    reversed_key: str,
    forward_key: str | None = None,
    max_seconds: int | None = None,
) -> tuple[float, str]:
    """Read an upload, store it at ``{source_key}.{ext}``, produce + store its
    reversed WAV at `reversed_key` (and, if `forward_key` is given, a
    non-reversed WAV too). Rejects clips longer than `max_seconds`
    (default ``settings.max_clip_seconds``). Returns (duration_seconds,
    source_ext)."""
    if not audio.ffmpeg_available():
        raise HTTPException(503, "audio processing unavailable (ffmpeg missing)")

    limit_seconds = max_seconds if max_seconds is not None else settings.max_clip_seconds

    raw = await read_capped(file, settings.max_upload_bytes)
    if not raw:
        raise HTTPException(400, "empty upload")
    ext = ext_for(file)

    with tempfile.TemporaryDirectory() as tmp:
        src = Path(tmp) / f"src.{ext}"
        src.write_bytes(raw)
        out = Path(tmp) / "reversed.wav"

        # ffmpeg is blocking; run it off the event loop so concurrent requests
        # (e.g. the reveal page loading every clip at once) aren't stalled.
        try:
            await anyio.to_thread.run_sync(audio.reverse_to_wav, src, out)
        except audio.FfmpegError:
            raise HTTPException(400, "could not read that file as audio")

        duration = audio.wav_duration_seconds(out)
        if not duration:
            raise HTTPException(400, "recording was empty")
        if duration > limit_seconds:
            raise HTTPException(
                400, f"recording is {duration:.0f}s; limit is {limit_seconds}s"
            )

        storage.put_bytes(f"{source_key}.{ext}", raw)
        storage.put_bytes(reversed_key, out.read_bytes())

        if forward_key:
            fwd = Path(tmp) / "forward.wav"
            try:
                await anyio.to_thread.run_sync(audio.transcode_to_wav, src, fwd)
                storage.put_bytes(forward_key, fwd.read_bytes())
            except audio.FfmpegError:
                pass  # non-fatal — the forward copy is a comparison aid

    return duration, ext
