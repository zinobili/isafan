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

import time

from fastapi import APIRouter, Form, HTTPException, UploadFile
from fastapi.responses import FileResponse

from .clips import is_allowed_clip_name, media_type_for
from .game import GameRegistry, Phase
from .ingest import ingest_reversed
from .storage import Storage
from .ws import Hub


def build_router(registry: GameRegistry, storage: Storage, hub: Hub) -> APIRouter:
    router = APIRouter(prefix="/api/games/{code}")

    @router.post("/original")
    async def upload_original(code: str, file: UploadFile, playerId: str = Form("")):
        game = registry.get(code)
        if not game:
            raise HTTPException(404, "no game with that code")
        if game.mode != "solo" and playerId != game.host_id:
            raise HTTPException(403, "only the host records the original")

        duration, ext = await ingest_reversed(
            file, storage,
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
        duration, ext = await ingest_reversed(
            file, storage,
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
        if not is_allowed_clip_name(name):
            raise HTTPException(404, "unknown clip")
        path = storage.local_path(f"games/{code}/{name}")
        if path is None or not path.is_file():
            raise HTTPException(404, "clip not found")
        return FileResponse(
            path,
            media_type=media_type_for(name),
            headers={"Cache-Control": "no-store"},
        )

    return router
