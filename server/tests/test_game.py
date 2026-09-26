import json

import pytest

from server.game import CODE_ALPHABET, Game, GameRegistry, Phase
from server.storage import LocalDiskStorage


@pytest.fixture
def reg(tmp_path):
    return GameRegistry(LocalDiskStorage(tmp_path), code_length=4, max_players=3)


def test_new_code_shape_and_uniqueness(reg):
    codes = {reg.create().code for _ in range(20)}
    assert len(codes) == 20
    for c in codes:
        assert len(c) == 4 and all(ch in CODE_ALPHABET for ch in c)


def test_get_is_case_insensitive(reg):
    g = reg.create()
    assert reg.get(g.code.lower()) is g
    assert reg.get("  " + g.code + " ") is g
    assert reg.get(None) is None
    assert reg.get("ZZZZ") is None


def test_add_player_first_becomes_host():
    g = Game(code="ABCD")
    a = g.add_player("Alice", as_host=True)
    b = g.add_player("Bob", as_host=True)  # second as_host request is ignored
    assert g.host_id == a.id and a.is_host and not b.is_host


def test_remove_player_migrates_host():
    g = Game(code="ABCD")
    a = g.add_player("Alice", as_host=True)
    b = g.add_player("Bob")
    g.remove_player(a.id)
    assert g.host_id == b.id and g.players[b.id].is_host


def test_blank_name_falls_back():
    g = Game(code="ABCD")
    assert g.add_player("   ").name == "Player"
    assert g.add_player("x" * 50).name == "x" * 24


def test_add_and_replace_attempt():
    g = Game(code="ABCD")
    eid = g.new_attempt_id()
    g.add_attempt(id=eid, name="Nora", source_ext="webm", duration_ms=1200, by="p1")
    pub = g.attempts_public()[0]
    assert pub["id"] == eid and pub["by"] == "p1"
    assert pub["url"] == f"/api/games/ABCD/audio/{g.media_key}/attempt_{eid}_reversed.wav"


def test_cast_vote_rules():
    g = Game(code="ABCD")
    g.add_attempt(id="a1", name="Nora", source_ext="webm", duration_ms=1, by="p1")
    g.add_attempt(id="a2", name="Ola", source_ext="webm", duration_ms=1, by="p2")
    assert g.cast_vote("p1", "a2") is True          # ok
    assert g.cast_vote("p1", "a1") is False         # own take
    assert g.cast_vote("p2", "nope") is False       # unknown take
    assert g.cast_vote("p1", "a2") is True          # changeable
    assert g.votes == {"p1": "a2"}


def test_reset_for_new_round_clears_everything():
    g = Game(code="ABCD")
    g.original = {"durationMs": 1}
    g.add_attempt(id="a1", name="x", source_ext="webm", duration_ms=1, by="p1")
    g.votes["p2"] = "a1"
    g.phase = Phase.REVEAL
    g.reset_for_new_round()
    assert (g.round_no, g.original, g.attempts, g.votes) == (1, None, [], {})
    assert g.phase is Phase.HOST_RECORDING


def test_public_and_json_shapes():
    g = Game(code="ABCD", mode="solo")
    g.add_player("Alice", as_host=True)
    pub = g.public()
    assert set(pub) == {
        "code", "mode", "phase", "hostId", "roundNo", "createdAt",
        "players", "original", "attempts", "votes", "revealOriginal",
    }
    assert pub["original"] is None and pub["attempts"] == [] and pub["revealOriginal"] is False
    parsed = json.loads(g.to_json())
    assert parsed["players"][0]["name"] == "Alice" and "joinedAt" in parsed["players"][0]


def test_registry_persists_game_json(reg):
    g = reg.create(mode="solo")
    saved = json.loads(reg._storage.get_text(f"games/{g.code}/game.json"))
    assert saved["code"] == g.code and saved["mode"] == "solo"
