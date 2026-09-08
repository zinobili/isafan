"""Admin manual deletes: whole game + single clip, CSRF- and auth-guarded."""

import re

from server.admin import games
from server.main import registry, storage


def _login(client, creds):
    client.post("/admin/login", data=creds)


def _csrf(client):
    page = client.get("/admin").text
    return re.search(r'name="csrf" value="([0-9a-f]{32})"', page).group(1)


def _game_with_original(client, webm_bytes):
    code = client.post("/api/solo").json()["code"]
    client.post(
        f"/api/games/{code}/original",
        files={"file": ("o.webm", webm_bytes, "audio/webm")},
        data={"playerId": ""},
    )
    return code


def test_delete_single_clip(client, admin_creds, webm_bytes):
    code = _game_with_original(client, webm_bytes)
    _login(client, admin_creds)
    assert storage.local_path(f"games/{code}/original_forward.wav").is_file()

    r = client.post(
        f"/admin/games/{code}/clips/original_forward.wav/delete",
        data={"csrf": _csrf(client)},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == f"/admin/games/{code}"
    assert not storage.local_path(f"games/{code}/original_forward.wav").is_file()
    assert storage.local_path(f"games/{code}/original_reversed.wav").is_file()


def test_delete_whole_game(client, admin_creds, webm_bytes):
    code = _game_with_original(client, webm_bytes)
    _login(client, admin_creds)
    assert registry.get(code) is not None

    r = client.post(
        f"/admin/games/{code}/delete",
        data={"csrf": _csrf(client)},
        follow_redirects=False,
    )
    assert r.status_code == 303 and r.headers["location"] == "/admin/games"
    assert registry.get(code) is None
    assert storage.list_children(f"games/{code}") == []
    assert code not in [g["code"] for g in games.list_games(storage, 3600)]


def test_delete_rejects_bad_csrf(client, admin_creds, webm_bytes):
    code = _game_with_original(client, webm_bytes)
    _login(client, admin_creds)
    r = client.post(
        f"/admin/games/{code}/delete", data={"csrf": "0" * 32}, follow_redirects=False
    )
    assert r.status_code == 403
    assert registry.get(code) is not None
    assert storage.local_path(f"games/{code}/original_reversed.wav").is_file()


def test_delete_requires_auth(client, webm_bytes):
    code = _game_with_original(client, webm_bytes)
    r = client.post(
        f"/admin/games/{code}/delete", data={"csrf": "x"}, follow_redirects=False
    )
    assert r.status_code == 303 and r.headers["location"] == "/admin/login"
    assert registry.get(code) is not None


def test_delete_clip_rejects_non_clip_name(client, admin_creds, webm_bytes):
    code = _game_with_original(client, webm_bytes)
    _login(client, admin_creds)
    r = client.post(
        f"/admin/games/{code}/clips/game.json/delete", data={"csrf": _csrf(client)}
    )
    assert r.status_code == 404
    assert storage.local_path(f"games/{code}/game.json").is_file()
