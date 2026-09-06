"""FastAPI app: health + game-existence REST, the WebSocket endpoint, and (when
a built SPA is present) static hosting with a history-API fallback so deep links
like /host survive a hard refresh."""

from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__, audio, media
from .config import settings
from .game import GameRegistry
from .storage import build_storage
from .ws import Hub

storage = build_storage(settings.storage_backend, settings.data_dir)
registry = GameRegistry(storage, settings.game_code_length, settings.max_players)
hub = Hub(registry)

app = FastAPI(title="isafan", version=__version__)

if settings.public_url:
    _extra = settings.public_url_candidates[1:]
    print(
        f"[isafan] join link base: {settings.public_url}  (source: {settings.public_url_source})"
        + (f"\n[isafan] other addresses to try: {', '.join(_extra)}" if _extra else ""),
        flush=True,
    )
else:
    print(
        "[isafan] join link base: origin of the host screen "
        "(set ISAFAN_PUBLIC_URL to force a LAN IP or tunnel URL)",
        flush=True,
    )

# Only needed while the Vite dev server serves the UI from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dev_cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {
        "status": "ok",
        "version": __version__,
        "games": len(registry.all()),
        "ffmpeg": audio.ffmpeg_available(),
    }


@app.get("/api/config")
def client_config() -> dict:
    """Values the SPA needs at runtime. `publicUrl` is the join-link / QR base
    (explicit ISAFAN_PUBLIC_URL, else an auto-detected LAN address, else "" so
    the client uses its own origin). `publicUrlCandidates` lists every reachable
    base so the host screen can offer alternates when the first can't be reached."""
    return {
        "publicUrl": settings.public_url,
        "publicUrlCandidates": list(settings.public_url_candidates),
    }


@app.get("/api/games/{code}")
def game_summary(code: str):
    game = registry.get(code)
    if not game:
        return JSONResponse({"exists": False}, status_code=404)
    return {
        "exists": True,
        "mode": game.mode,
        "phase": game.phase.value,
        "players": len(game.players),
        "maxPlayers": settings.max_players,
    }


@app.post("/api/solo")
def create_solo() -> dict:
    """One-device / pass-the-phone game. No WebSocket, no players list — the
    single page drives the flow and talks only to the audio endpoints."""
    game = registry.create(mode="solo")
    return {"code": game.code}


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await hub.handle(ws)


app.include_router(media.build_router(registry, storage, hub))


@app.api_route("/api/{_rest:path}", methods=["GET", "POST", "PUT", "DELETE", "PATCH"])
def api_not_found(_rest: str):
    """Anything under /api that no route above matched is a real 404 — don't let
    it fall through to the SPA fallback and return index.html."""
    return JSONResponse({"detail": "not found"}, status_code=404)


# --- static SPA (optional; present after `npm run build`) --------------------

_STATIC = settings.static_dir
_INDEX = _STATIC / "index.html"

if _INDEX.is_file():

    @app.get("/{full_path:path}")
    def spa(full_path: str):
        candidate = _STATIC / full_path
        if full_path and candidate.is_file() and _STATIC.resolve() in candidate.resolve().parents:
            return FileResponse(candidate)
        return FileResponse(_INDEX)
