"""Admin recordings browser: server/admin/games helpers + the rendered pages."""

from server.admin import games
from server.game import GameRegistry
from server.storage import LocalDiskStorage


def _login(client, creds):
    client.post("/admin/login", data=creds)


def test_list_and_load_game_from_storage(tmp_path):
    store = LocalDiskStorage(tmp_path)
    reg = GameRegistry(store, code_length=4, max_players=5)
    g = reg.create(mode="solo")
    store.put_bytes(f"games/{g.code}/original_reversed.wav", b"\x00" * 10)
    store.put_bytes(f"games/{g.code}/original_forward.wav", b"\x00" * 10)
    g.add_attempt(id="ab12cd34", name="Ada", source_ext="webm", duration_ms=1500, by="p1")
    reg.persist(g)
    store.put_bytes(f"games/{g.code}/attempt_ab12cd34_reversed.wav", b"\x00" * 10)

    rows = games.list_games(store, ttl_seconds=3600)
    assert [r["code"] for r in rows] == [g.code]
    assert rows[0]["attempts"] == 1 and rows[0]["expires_in_seconds"] > 0

    detail = games.load_game(store, g.code)
    assert detail["original"]["reversed"] == "original_reversed.wav"
    assert detail["original"]["source"] is None
    assert detail["attempts"][0]["reversed"] == "attempt_ab12cd34_reversed.wav"
    assert detail["attempts"][0]["source"] is None          # metadata says webm, none on disk
    assert games.load_game(store, "ZZZZ") is None


def test_load_game_flags_orphan_attempt_clips(tmp_path):
    store = LocalDiskStorage(tmp_path)
    GameRegistry(store, 4, 5)
    store.put_bytes("games/ABCD/attempt_deadbeef_reversed.wav", b"x")  # no game.json
    detail = games.load_game(store, "ABCD")
    assert detail["orphans"] == ["attempt_deadbeef_reversed.wav"]
    assert detail["attempts"] == []


def test_games_pages_render_and_stream_audio(client, admin_creds, webm_bytes):
    code = client.post("/api/solo").json()["code"]
    client.post(
        f"/api/games/{code}/original",
        files={"file": ("o.webm", webm_bytes, "audio/webm")},
        data={"playerId": ""},
    )
    _login(client, admin_creds)

    listing = client.get("/admin/games")
    assert listing.status_code == 200 and code in listing.text

    detail = client.get(f"/admin/games/{code}")
    assert detail.status_code == 200
    assert f"/admin/games/{code}/audio/original_reversed.wav" in detail.text

    clip = client.get(f"/admin/games/{code}/audio/original_reversed.wav")
    assert clip.status_code == 200
    assert clip.headers["content-type"] == "audio/wav"
    assert clip.content[:4] == b"RIFF"


def test_games_browser_requires_auth(client):
    assert client.get("/admin/games", follow_redirects=False).status_code == 303
    assert (
        client.get(
            "/admin/games/ABCD/audio/original_reversed.wav", follow_redirects=False
        ).status_code
        == 303
    )


def test_game_detail_404s_for_unknown(client, admin_creds):
    _login(client, admin_creds)
    assert client.get("/admin/games/NOPE").status_code == 404
    code = client.post("/api/solo").json()["code"]
    # game.json is not an allow-listed clip name
    assert client.get(f"/admin/games/{code}/audio/game.json").status_code == 404
    assert client.get(f"/admin/games/{code}/audio/original_source.exe").status_code == 404
