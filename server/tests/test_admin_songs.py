"""Admin song library pages: add / list / rename / enable / delete + streaming."""

import re

import pytest

from server.admin import auth
from server.main import song_library, storage


def _login(client, creds):
    client.post("/admin/login", data=creds)


def _csrf(client):
    page = client.get("/admin/songs").text
    return re.search(r'name="csrf" value="([0-9a-f]{32})"', page).group(1)


def _add(client, name, raw, csrf, *, mime="audio/webm"):
    return client.post(
        "/admin/songs",
        data={"name": name, "csrf": csrf},
        files={"file": ("s.webm", raw, mime)},
        follow_redirects=False,
    )


@pytest.fixture(autouse=True)
def _clear_library():
    for s in list(song_library.list()):
        song_library.delete(s["slug"])
    yield
    for s in list(song_library.list()):
        song_library.delete(s["slug"])


def test_add_then_list_and_stream(client, admin_creds, webm_bytes):
    _login(client, admin_creds)
    r = _add(client, "Twinkle Twinkle", webm_bytes, _csrf(client))
    assert r.status_code == 303 and r.headers["location"] == "/admin/songs"

    listing = client.get("/admin/songs")
    assert "Twinkle Twinkle" in listing.text and "/admin/songs/twinkle-twinkle" in listing.text

    detail = client.get("/admin/songs/twinkle-twinkle")
    assert detail.status_code == 200
    assert detail.text.count("<audio") == 3 and "/rename" in detail.text

    rev = client.get("/admin/songs/twinkle-twinkle/audio/reversed")
    assert rev.status_code == 200 and rev.headers["content-type"] == "audio/wav"
    assert rev.content[:4] == b"RIFF"
    src = client.get("/admin/songs/twinkle-twinkle/audio/source")
    assert src.status_code == 200 and src.headers["content-type"] == "audio/webm"
    assert client.get("/admin/songs/twinkle-twinkle/audio/bogus").status_code == 404
    assert client.get("/admin/songs/nope/audio/reversed").status_code == 404


def test_enable_toggle_and_rename(client, admin_creds, webm_bytes):
    _login(client, admin_creds)
    _add(client, "Song A", webm_bytes, _csrf(client))
    csrf = _csrf(client)

    client.post(
        "/admin/songs/song-a/enabled", data={"on": "0", "csrf": csrf}, follow_redirects=False
    )
    assert song_library.get("song-a")["enabled"] is False
    assert "enable</button>" in client.get("/admin/songs").text

    client.post(
        "/admin/songs/song-a/rename",
        data={"name": "Song Renamed", "csrf": csrf},
        follow_redirects=False,
    )
    assert song_library.get("song-a")["name"] == "Song Renamed"


def test_delete_song(client, admin_creds, webm_bytes):
    _login(client, admin_creds)
    _add(client, "Doomed", webm_bytes, _csrf(client))
    assert storage.local_path("assets/songs/doomed/reversed.wav").is_file()

    r = client.post(
        "/admin/songs/doomed/delete", data={"csrf": _csrf(client)}, follow_redirects=False
    )
    assert r.status_code == 303
    assert song_library.get("doomed") is None
    assert not storage.local_path("assets/songs/doomed").exists()


def test_add_non_audio_shows_error_and_adds_nothing(client, admin_creds):
    _login(client, admin_creds)
    r = _add(client, "Junk", b"definitely not audio", _csrf(client))
    assert r.status_code == 303 and r.headers["location"].startswith("/admin/songs?error=")
    assert song_library.list() == []
    assert "could not read that file as audio" in client.get(r.headers["location"]).text


def test_songs_pages_require_auth(client):
    assert client.get("/admin/songs", follow_redirects=False).status_code == 303
    assert (
        client.post("/admin/songs/x/delete", data={"csrf": "x"}, follow_redirects=False).status_code
        == 303
    )
    assert (
        client.get("/admin/songs/x/audio/reversed", follow_redirects=False).status_code == 303
    )


def test_add_rejects_bad_csrf(client, admin_creds, webm_bytes):
    _login(client, admin_creds)
    r = _add(client, "NoCSRF", webm_bytes, "0" * 32)
    assert r.status_code == 403
    assert song_library.list() == []


def test_status_page_reports_song_count(client, admin_creds, webm_bytes):
    _login(client, admin_creds)
    _add(client, "Counted", webm_bytes, _csrf(client))
    page = client.get("/admin").text
    assert "Library songs" in page and "1 · 1 enabled" in page
