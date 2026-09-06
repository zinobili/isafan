"""WebSocket hub: connection lifecycle + lobby fan-out.

Message protocol (JSON text frames).

client -> server:
  {"type": "ping"}
  {"type": "echo", "payload": <any>}                 # Phase 1 round-trip check
  {"type": "create", "name": str, "mode": "multi"}
  {"type": "join",   "code": str, "name": str}
  {"type": "rejoin", "code": str, "playerId": str}   # after a reconnect
  {"type": "leave"}

server -> client:
  {"type": "pong"}
  {"type": "echo", "payload": <any>}
  {"type": "joined", "playerId": str, "code": str, "game": <GameView>}
  {"type": "game", "game": <GameView>}               # broadcast on any change
  {"type": "error", "code": str, "message": str}
"""

from __future__ import annotations

import json

from fastapi import WebSocket, WebSocketDisconnect

from .game import GameRegistry, Phase


# Latecomers may still join up to the point where the audience starts recording.
_JOINABLE_PHASES = {
    Phase.LOBBY,
    Phase.HOST_RECORDING,
    Phase.REVERSING,
    Phase.REVERSED_PLAYBACK,
}


class Hub:
    def __init__(self, registry: GameRegistry) -> None:
        self._registry = registry
        # code -> { player_id -> WebSocket }
        self._conns: dict[str, dict[str, WebSocket]] = {}

    # ------------------------------------------------------------------ send

    @staticmethod
    async def _send(ws: WebSocket, msg: dict) -> None:
        try:
            await ws.send_text(json.dumps(msg))
        except Exception:
            pass

    @staticmethod
    async def _err(ws: WebSocket, code: str, message: str) -> None:
        await Hub._send(ws, {"type": "error", "code": code, "message": message})

    async def _broadcast(self, code: str | None) -> None:
        if not code:
            return
        game = self._registry.get(code)
        if not game:
            return
        payload = {"type": "game", "game": game.public()}
        for ws in list(self._conns.get(code, {}).values()):
            await self._send(ws, payload)

    async def broadcast(self, code: str) -> None:
        """Public: let HTTP handlers push fresh game state after a mutation."""
        await self._broadcast(code)

    # --------------------------------------------------------------- lifecycle

    async def handle(self, ws: WebSocket) -> None:
        await ws.accept()
        code: str | None = None
        player_id: str | None = None
        try:
            while True:
                raw = await ws.receive_text()
                try:
                    msg = json.loads(raw)
                except json.JSONDecodeError:
                    await self._err(ws, "bad_json", "message was not valid JSON")
                    continue
                if not isinstance(msg, dict):
                    await self._err(ws, "bad_message", "message must be a JSON object")
                    continue

                mtype = msg.get("type")
                if mtype == "ping":
                    await self._send(ws, {"type": "pong"})
                elif mtype == "echo":
                    await self._send(ws, {"type": "echo", "payload": msg.get("payload")})
                elif mtype == "create":
                    code, player_id = await self._create(ws, msg, code, player_id)
                elif mtype == "join":
                    code, player_id = await self._join(ws, msg, code, player_id)
                elif mtype == "rejoin":
                    code, player_id = await self._rejoin(ws, msg, code, player_id)
                elif mtype == "leave":
                    await self._detach(code, player_id, remove=True)
                    code, player_id = None, None
                elif mtype == "start_recording":
                    await self._host_set_phase(ws, code, player_id, Phase.HOST_RECORDING, clear_round=True)
                elif mtype == "reset_round":
                    await self._host_set_phase(ws, code, player_id, Phase.LOBBY, clear_round=True)
                elif mtype == "start_audience_recording":
                    await self._start_audience_recording(ws, code, player_id)
                elif mtype == "start_reveal":
                    await self._host_set_phase(ws, code, player_id, Phase.REVEAL)
                elif mtype == "next_round":
                    await self._next_round(ws, code, player_id)
                elif mtype == "vote":
                    await self._vote(ws, code, player_id, msg.get("attemptId"))
                else:
                    await self._err(ws, "unknown_type", f"unknown message type: {mtype!r}")
        except WebSocketDisconnect:
            pass
        finally:
            await self._detach(code, player_id, remove=False)

    # ------------------------------------------------------------------ verbs

    async def _create(self, ws, msg, cur_code, cur_pid):
        await self._detach(cur_code, cur_pid, remove=True)
        mode = msg.get("mode") if msg.get("mode") in ("multi", "solo") else "multi"
        game = self._registry.create(mode=mode)
        player = game.add_player(msg.get("name", ""), as_host=True)
        self._attach(game.code, player.id, ws)
        self._registry.persist(game)
        # Only connection in the room — `joined` already carries full state.
        await self._send(ws, {
            "type": "joined", "playerId": player.id, "code": game.code, "game": game.public(),
        })
        return game.code, player.id

    async def _join(self, ws, msg, cur_code, cur_pid):
        game = self._registry.get(msg.get("code"))
        if not game:
            await self._err(ws, "game_not_found", "no game with that code")
            return cur_code, cur_pid
        if game.phase not in _JOINABLE_PHASES:
            await self._err(ws, "game_started", "this game is already in progress")
            return cur_code, cur_pid
        if len(game.players) >= self._registry.max_players:
            await self._err(ws, "game_full", "this game is full")
            return cur_code, cur_pid

        await self._detach(cur_code, cur_pid, remove=True)
        player = game.add_player(msg.get("name", ""))
        self._attach(game.code, player.id, ws)
        self._registry.persist(game)
        await self._send(ws, {
            "type": "joined", "playerId": player.id, "code": game.code, "game": game.public(),
        })
        await self._broadcast(game.code)
        return game.code, player.id

    async def _rejoin(self, ws, msg, cur_code, cur_pid):
        game = self._registry.get(msg.get("code"))
        pid = msg.get("playerId")
        if not game or pid not in game.players:
            await self._err(ws, "game_not_found", "that session is no longer available")
            return cur_code, cur_pid

        await self._detach(cur_code, cur_pid, remove=True)
        game.players[pid].connected = True
        self._attach(game.code, pid, ws)
        await self._send(ws, {
            "type": "joined", "playerId": pid, "code": game.code, "game": game.public(),
        })
        await self._broadcast(game.code)
        return game.code, pid

    async def _host_game(self, ws, code, player_id):
        game = self._registry.get(code)
        if not game:
            await self._err(ws, "game_not_found", "no game with that code")
            return None
        if player_id != game.host_id:
            await self._err(ws, "not_host", "only the host can do that")
            return None
        return game

    async def _host_set_phase(self, ws, code, player_id, phase: Phase, *, clear_round=False):
        game = await self._host_game(ws, code, player_id)
        if not game:
            return
        game.phase = phase
        if clear_round:
            game.original = None
            game.attempts = []
            game.votes = {}
        self._registry.persist(game)
        await self._broadcast(code)

    async def _start_audience_recording(self, ws, code, player_id):
        game = await self._host_game(ws, code, player_id)
        if not game:
            return
        if not game.original:
            await self._err(ws, "no_original", "record the song first")
            return
        game.phase = Phase.AUDIENCE_RECORDING
        self._registry.persist(game)
        await self._broadcast(code)

    async def _next_round(self, ws, code, player_id):
        game = await self._host_game(ws, code, player_id)
        if not game:
            return
        game.reset_for_new_round()
        self._registry.persist(game)
        await self._broadcast(code)

    async def _vote(self, ws, code, player_id, attempt_id):
        game = self._registry.get(code)
        if not game or player_id not in game.players:
            await self._err(ws, "not_in_game", "join the game to vote")
            return
        if not game.cast_vote(player_id, attempt_id):
            await self._err(ws, "bad_vote", "you can't vote for that take")
            return
        self._registry.persist(game)
        await self._broadcast(code)

    # ------------------------------------------------------------- conn table

    def _attach(self, code: str, player_id: str, ws: WebSocket) -> None:
        self._conns.setdefault(code, {})[player_id] = ws

    async def _detach(self, code: str | None, player_id: str | None, *, remove: bool) -> None:
        if not code or not player_id:
            return
        conns = self._conns.get(code)
        if conns:
            conns.pop(player_id, None)
            if not conns:
                self._conns.pop(code, None)

        game = self._registry.get(code)
        if not game or player_id not in game.players:
            return
        if remove:
            game.remove_player(player_id)
            if not game.players:
                self._registry.drop(code)
                return
        else:
            game.players[player_id].connected = False
        self._registry.persist(game)
        await self._broadcast(code)
