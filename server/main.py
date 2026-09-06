"""FastAPI app: health + game-existence REST, the WebSocket endpoint, and (when
a built SPA is present) static hosting with a history-API fallback so deep links
like /host survive a hard refresh."""

from __future__ import annotations

from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import FileResponse, JSONResponse

from . import __version__
from .config import settings
from .game import GameRegistry
from .storage import build_storage
from .ws import Hub

storage = build_storage(settings.storage_backend, settings.data_dir)
registry = GameRegistry(storage, settings.game_code_length, settings.max_players)
hub = Hub(registry)

app = FastAPI(title="isafan", version=__version__)

# Only needed while the Vite dev server serves the UI from another origin.
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.dev_cors_origin],
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict:
    return {"status": "ok", "version": __version__, "games": len(registry.all())}


@app.get("/api/config")
def client_config() -> dict:
    """Values the SPA needs at runtime. `publicUrl` is "" unless configured, in
    which case the host screen builds the join link / QR from it instead of the
    origin it was opened with."""
    return {"publicUrl": settings.public_url}


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


@app.websocket("/ws")
async def ws_endpoint(ws: WebSocket) -> None:
    await hub.handle(ws)


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
