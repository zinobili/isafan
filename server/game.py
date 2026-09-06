"""In-memory game model + registry.

One process, one `GameRegistry`, games held in a dict keyed by room code. A
best-effort `game.json` mirror is written to storage so a later admin/retention
pass can see games within the 24h window; live gameplay state is memory-only.
"""

from __future__ import annotations

import json
import secrets
import time
from dataclasses import dataclass, field
from enum import Enum

from .storage import Storage

# Unambiguous alphabet — no 0/O, 1/I, so codes are easy to read aloud / type.
CODE_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"
MAX_NAME_LEN = 24


class Phase(str, Enum):
    LOBBY = "LOBBY"
    HOST_RECORDING = "HOST_RECORDING"
    REVERSING = "REVERSING"
    REVERSED_PLAYBACK = "REVERSED_PLAYBACK"
    AUDIENCE_RECORDING = "AUDIENCE_RECORDING"
    PROCESSING = "PROCESSING"
    REVEAL = "REVEAL"
    VOTE = "VOTE"
    RESULTS = "RESULTS"


@dataclass
class Player:
    id: str
    name: str
    is_host: bool = False
    connected: bool = True
    joined_at: float = field(default_factory=time.time)

    def public(self) -> dict:
        return {
            "id": self.id,
            "name": self.name,
            "isHost": self.is_host,
            "connected": self.connected,
        }


def _clean_name(raw: str) -> str:
    return (raw or "").strip()[:MAX_NAME_LEN] or "Player"


@dataclass
class Game:
    code: str
    mode: str = "multi"                       # "multi" | "solo"
    phase: Phase = Phase.LOBBY
    host_id: str | None = None
    players: dict[str, Player] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    round_no: int = 0
    # Set once the host's recording has been reversed and stored.
    original: dict | None = None  # {"durationMs", "uploadedBy", "at"}

    def audio_url(self, name: str) -> str:
        return f"/api/games/{self.code}/audio/{name}"

    def original_public(self) -> dict | None:
        if not self.original:
            return None
        return {
            "durationMs": self.original["durationMs"],
            "url": self.audio_url("original_reversed.wav"),
        }

    def add_player(self, name: str, as_host: bool = False) -> Player:
        pid = secrets.token_urlsafe(9)
        player = Player(id=pid, name=_clean_name(name), is_host=as_host)
        self.players[pid] = player
        if as_host and self.host_id is None:
            self.host_id = pid
            player.is_host = True
        return player

    def remove_player(self, player_id: str) -> None:
        self.players.pop(player_id, None)
        if self.host_id == player_id:
            self.host_id = next(iter(self.players), None)
            if self.host_id:
                self.players[self.host_id].is_host = True

    def public(self) -> dict:
        return {
            "code": self.code,
            "mode": self.mode,
            "phase": self.phase.value,
            "hostId": self.host_id,
            "roundNo": self.round_no,
            "createdAt": self.created_at,
            "players": [p.public() for p in self.players.values()],
            "original": self.original_public(),
        }

    def to_json(self) -> str:
        return json.dumps(
            {
                "code": self.code,
                "mode": self.mode,
                "phase": self.phase.value,
                "hostId": self.host_id,
                "createdAt": self.created_at,
                "roundNo": self.round_no,
                "original": self.original,
                "players": [
                    {"id": p.id, "name": p.name, "isHost": p.is_host, "joinedAt": p.joined_at}
                    for p in self.players.values()
                ],
            },
            indent=2,
        )


class GameRegistry:
    def __init__(self, storage: Storage, code_length: int, max_players: int) -> None:
        self._games: dict[str, Game] = {}
        self._storage = storage
        self._code_length = code_length
        self._max_players = max_players

    @property
    def max_players(self) -> int:
        return self._max_players

    def _new_code(self) -> str:
        for _ in range(50):
            code = "".join(secrets.choice(CODE_ALPHABET) for _ in range(self._code_length))
            if code not in self._games:
                return code
        raise RuntimeError("could not allocate a unique game code")

    def create(self, mode: str = "multi") -> Game:
        game = Game(code=self._new_code(), mode=mode)
        self._games[game.code] = game
        self.persist(game)
        return game

    def get(self, code: str | None) -> Game | None:
        if not code:
            return None
        return self._games.get(code.strip().upper())

    def all(self) -> list[Game]:
        return list(self._games.values())

    def drop(self, code: str) -> None:
        self._games.pop(code, None)

    def persist(self, game: Game) -> None:
        try:
            self._storage.put_text(f"games/{game.code}/game.json", game.to_json())
        except Exception:
            # Best-effort in this phase; retention/admin come later.
            pass
