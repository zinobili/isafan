"""Picking a library song as a game's original (GET /api/songs +
POST /api/games/{code}/original/library)."""

from io import BytesIO

import anyio
import pytest
from fastapi import UploadFile
from starlette.datastructures import Headers

from server.game import Phase
from server.main import registry, song_library


@pytest.fixture
def a_song(webm_bytes):
    async def go():
        up = UploadFile(
            filename="s.webm",
            file=BytesIO(webm_bytes),
            headers=Headers({"content-type": "audio/webm"}),
        )
        return await song_library.add("Test Anthem", up, max_seconds=60)

    entry = anyio.run(go)
    yield entry
    for s in list(song_library.list()):
        song_library.delete(s["slug"])


def test_list_songs_reports_only_enabled(client, a_song):
    got = client.get("/api/songs").json()
    assert got == [
        {"slug": "test-anthem", "name": "Test Anthem",
         "durationMs": a_song["durationMs"], "lineCount": 0}
    ]
    song_library.set_enabled("test-anthem", False)
    assert client.get("/api/songs").json() == []


def test_song_preview_streams_forward_and_reversed(client, a_song):
    for kind in ("forward", "reversed"):
        r = client.get(f"/api/songs/test-anthem/audio/{kind}")
        assert r.status_code == 200
        assert r.headers["content-type"] == "audio/wav"
        assert r.content[:4] == b"RIFF"

    assert client.get("/api/songs/test-anthem/audio/source").status_code == 404
    assert client.get("/api/songs/nope/audio/forward").status_code == 404

    song_library.set_enabled("test-anthem", False)
    assert client.get("/api/songs/test-anthem/audio/forward").status_code == 404


def test_solo_picks_library_song_as_original(client, a_song):
    code = client.post("/api/solo").json()["code"]
    r = client.post(f"/api/games/{code}/original/library", data={"slug": "test-anthem"})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].endswith("original_reversed.wav")
    assert body["forwardUrl"].endswith("original_forward.wav")

    game = registry.get(code)
    assert game.phase is Phase.REVERSED_PLAYBACK
    assert game.original["songSlug"] == "test-anthem"
    assert game.original["durationMs"] == a_song["durationMs"]

    clip = client.get(game.audio_url("original_reversed.wav"))
    assert clip.status_code == 200 and clip.content[:4] == b"RIFF"
    assert client.get(game.audio_url("original_forward.wav")).status_code == 200


def test_multi_pick_is_host_only(client, a_song):
    g = registry.create("multi")
    host = g.add_player("H", as_host=True)
    g.add_player("P")

    assert client.post(
        f"/api/games/{g.code}/original/library",
        data={"slug": "test-anthem", "playerId": "not-host"},
    ).status_code == 403

    r = client.post(
        f"/api/games/{g.code}/original/library",
        data={"slug": "test-anthem", "playerId": host.id},
    )
    assert r.status_code == 200 and registry.get(g.code).phase is Phase.REVERSED_PLAYBACK


def test_pick_rejects_unknown_and_disabled(client, a_song):
    code = client.post("/api/solo").json()["code"]
    assert client.post(
        f"/api/games/{code}/original/library", data={"slug": "nope"}
    ).status_code == 404

    song_library.set_enabled("test-anthem", False)
    assert client.post(
        f"/api/games/{code}/original/library", data={"slug": "test-anthem"}
    ).status_code == 404


def test_pick_needs_a_game(client, a_song):
    assert client.post(
        "/api/games/ZZZZ/original/library", data={"slug": "test-anthem"}
    ).status_code == 404
