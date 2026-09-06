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
    HOST_RECORDING = "HOST_RECORDING"          # host is taking the song
    REVERSED_PLAYBACK = "REVERSED_PLAYBACK"    # everyone hears it backwards
    AUDIENCE_RECORDING = "AUDIENCE_RECORDING"  # players record their mimic
    REVEAL = "REVEAL"                          # play the takes forwards + vote


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
    original: dict | None = None  # {"durationMs", "sourceExt", "uploadedBy", "at"}
    # One entry per submitted mimic; each has a reversed clip stored alongside.
    attempts: list[dict] = field(default_factory=list)  # {"id","name","sourceExt","durationMs","by","at"}
    # voter player id -> attempt id (each voter counts once; changeable)
    votes: dict[str, str] = field(default_factory=dict)
    # host toggle: also let the audience hear the song the right way round
    reveal_original: bool = False

    def audio_url(self, name: str) -> str:
        return f"/api/games/{self.code}/audio/{name}"

    def original_public(self) -> dict | None:
        if not self.original:
            return None
        return {
            "durationMs": self.original["durationMs"],
            "url": self.audio_url("original_reversed.wav"),      # what players mimic
            "forwardUrl": self.audio_url("original_forward.wav"),  # the song as sung
        }

    @staticmethod
    def new_attempt_id() -> str:
        return secrets.token_hex(4)  # 8 hex chars: clean filenames, no _ or -

    def add_attempt(
        self, *, id: str, name: str, source_ext: str, duration_ms: int, by: str = ""
    ) -> dict:
        entry = {
            "id": id,
            "name": _clean_name(name),
            "sourceExt": source_ext,
            "durationMs": duration_ms,
            "by": by,
            "at": time.time(),
        }
        self.attempts.append(entry)
        return entry

    def attempts_public(self) -> list[dict]:
        return [
            {
                "id": a["id"],
                "name": a["name"],
                "by": a["by"],
                "durationMs": a["durationMs"],
                "url": self.audio_url(f"attempt_{a['id']}_reversed.wav"),
            }
            for a in self.attempts
        ]

    def attempt(self, attempt_id: str | None) -> dict | None:
        return next((a for a in self.attempts if a["id"] == attempt_id), None)

    def cast_vote(self, voter_id: str, attempt_id: str | None) -> bool:
        target = self.attempt(attempt_id)
        if not target:
            return False
        if target["by"] and target["by"] == voter_id:
            return False  # no voting for your own take
        self.votes[voter_id] = target["id"]
        return True

    def reset_for_new_round(self) -> None:
        self.round_no += 1
        self.original = None
        self.attempts = []
        self.votes = {}
        self.reveal_original = False
        self.phase = Phase.HOST_RECORDING

    def add_player(self, name: str, as_host: bool = False) -> Player:
        pid = secrets.token_urlsafe(9)
        player = Player(id=pid, name=_clean_name(name))
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
            "attempts": self.attempts_public(),
            "votes": dict(self.votes),
            "revealOriginal": self.reveal_original,
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
                "attempts": self.attempts,
                "votes": self.votes,
                "revealOriginal": self.reveal_original,
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
