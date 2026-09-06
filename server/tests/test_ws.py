"""WebSocket protocol via Starlette's TestClient."""

from server.game import Phase
from server.main import registry


def _recv(ws, mtype, where=None, tries=12):
    """Next message of `mtype` (optionally matching `where`). Skips the earlier
    broadcasts that pile up in a session's queue during multi-client tests."""
    for _ in range(tries):
        msg = ws.receive_json()
        if msg.get("type") == mtype and (where is None or where(msg)):
            return msg
    raise AssertionError(f"never received {mtype!r}")


def _create(ws, mode="multi", name="Host"):
    ws.send_json({"type": "create", "name": name, "mode": mode})
    j = _recv(ws, "joined")
    return j["code"], j["playerId"]


def _join(ws, code, name="P"):
    ws.send_json({"type": "join", "code": code, "name": name})
    pid = _recv(ws, "joined")["playerId"]
    _recv(ws, "game")  # drain the broadcast our own join triggered
    return pid


def test_create_registers_game(client):
    with client.websocket_connect("/ws") as ws:
        code, host_id = _create(ws)
        g = registry.get(code)
        assert g and g.host_id == host_id and g.mode == "multi"


def test_join_broadcasts_to_host(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        with client.websocket_connect("/ws") as p:
            _join(p, code, "Ada")
            g = _recv(host, "game")["game"]
            assert [pl["name"] for pl in g["players"]] == ["Host", "Ada"]


def test_join_blocked_once_round_started(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        registry.get(code).phase = Phase.AUDIENCE_RECORDING
        with client.websocket_connect("/ws") as p:
            p.send_json({"type": "join", "code": code, "name": "Late"})
            assert _recv(p, "error")["code"] == "game_started"


def test_unknown_type_errors(client):
    with client.websocket_connect("/ws") as ws:
        _create(ws)
        ws.send_json({"type": "wat"})
        assert _recv(ws, "error")["code"] == "unknown_type"


def test_host_only_verbs_reject_non_host(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        with client.websocket_connect("/ws") as p:
            _join(p, code)
            p.send_json({"type": "start_audience_recording"})
            assert _recv(p, "error")["code"] == "not_host"
            p.send_json({"type": "next_round"})
            assert _recv(p, "error")["code"] == "not_host"


def test_start_audience_recording_requires_original(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        host.send_json({"type": "start_audience_recording"})
        assert _recv(host, "error")["code"] == "no_original"

        registry.get(code).original = {"durationMs": 1000}
        host.send_json({"type": "start_audience_recording"})
        assert _recv(host, "game")["game"]["phase"] == "AUDIENCE_RECORDING"


def test_reveal_original_toggle(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        host.send_json({"type": "set_reveal_original", "on": True})
        assert _recv(host, "game")["game"]["revealOriginal"] is True
        host.send_json({"type": "set_reveal_original", "on": False})
        assert _recv(host, "game")["game"]["revealOriginal"] is False
        # a non-host can't flip it
        with client.websocket_connect("/ws") as p:
            _join(p, code)
            p.send_json({"type": "set_reveal_original", "on": True})
            assert _recv(p, "error")["code"] == "not_host"


def test_vote_flow_and_next_round(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        with client.websocket_connect("/ws") as p:
            pid = _join(p, code)
            g = registry.get(code)
            g.original = {"durationMs": 1000}
            g.add_attempt(id="a1", name="H", source_ext="webm", duration_ms=1, by="host")
            g.add_attempt(id="a2", name="P", source_ext="webm", duration_ms=1, by=pid)
            g.phase = Phase.REVEAL

            p.send_json({"type": "vote", "attemptId": "a1"})
            assert _recv(p, "game")["game"]["votes"] == {pid: "a1"}

            p.send_json({"type": "vote", "attemptId": "a2"})  # own take
            assert _recv(p, "error")["code"] == "bad_vote"

            host.send_json({"type": "next_round"})
            g2 = _recv(host, "game", where=lambda m: m["game"]["roundNo"] == 1)["game"]
            assert g2["phase"] == "HOST_RECORDING"
            assert g2["attempts"] == [] and g2["votes"] == {}


def test_rejoin_after_drop(client):
    with client.websocket_connect("/ws") as host:
        code, _ = _create(host)
        with client.websocket_connect("/ws") as p:
            pid = _join(p, code)
        # p's context closed -> host sees a broadcast marking p disconnected
        disc = _recv(
            host, "game",
            where=lambda m: any(pl["id"] == pid and not pl["connected"] for pl in m["game"]["players"]),
        )
        assert any(pl["id"] == pid for pl in disc["game"]["players"])

        with client.websocket_connect("/ws") as p2:
            p2.send_json({"type": "rejoin", "code": code, "playerId": pid})
            assert _recv(p2, "joined")["playerId"] == pid
        assert pid in registry.get(code).players
