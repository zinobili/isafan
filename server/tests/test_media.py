"""HTTP audio endpoints. Game state is set up directly on the registry — the
WebSocket path that normally drives phases is covered in test_ws.py."""

from server.game import Phase
from server.main import registry, storage


def _files(webm: bytes):
    return {"file": ("take.webm", webm, "audio/webm")}


def test_health_and_config(client):
    h = client.get("/api/health").json()
    assert h["status"] == "ok" and h["ffmpeg"] is True
    cfg = client.get("/api/config").json()
    assert cfg["publicUrl"] == "http://testhost:8000"
    assert cfg["retentionHours"] == 24  # ISAFAN_GAME_TTL default, in whole hours


def test_api_miss_is_json_404_not_spa(client):
    r = client.get("/api/nope")
    assert r.status_code == 404 and r.json() == {"detail": "not found"}


def test_solo_create(client):
    code = client.post("/api/solo").json()["code"]
    assert registry.get(code).mode == "solo"


def test_original_host_only(client, webm_bytes):
    g = registry.create("multi")
    host = g.add_player("H", as_host=True)
    g.add_player("P")

    r = client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes),
                    data={"playerId": "not-host"})
    assert r.status_code == 403

    r = client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes),
                    data={"playerId": host.id})
    assert r.status_code == 200
    body = r.json()
    assert body["url"].endswith("original_reversed.wav")
    assert body["forwardUrl"].endswith("original_forward.wav")
    assert registry.get(g.code).phase is Phase.REVERSED_PLAYBACK


def test_attempt_accepts_phone_recorder_upload(client, webm_bytes):
    """The file-input fallback uploads whatever the phone's recorder produced —
    an m4a-ish name with a vague content-type. It's still real audio, so it
    should be reversed and stored, not rejected."""
    g = registry.create("solo")
    client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes), data={"playerId": ""})
    g.phase = Phase.AUDIENCE_RECORDING

    r = client.post(
        f"/api/games/{g.code}/attempts",
        files={"file": ("memo.m4a", webm_bytes, "audio/x-m4a")},
        data={"name": "Ada", "playerId": ""},
    )
    assert r.status_code == 200
    assert r.json()["url"].endswith("_reversed.wav")
    assert registry.get(g.code).attempts[0]["sourceExt"] == "m4a"


def test_original_rejects_non_audio(client):
    g = registry.create("multi")
    host = g.add_player("H", as_host=True)
    r = client.post(f"/api/games/{g.code}/original",
                    files={"file": ("x.webm", b"junk", "audio/webm")},
                    data={"playerId": host.id})
    assert r.status_code == 400


def test_original_rejects_too_long(client, webm_long):
    g = registry.create("solo")  # conftest sets the clip limit to 5s
    r = client.post(f"/api/games/{g.code}/original", files=_files(webm_long), data={"playerId": ""})
    assert r.status_code == 400 and "limit" in r.json()["detail"]


def test_upload_size_cap_enforced_on_both_paths(client):
    """conftest caps uploads at 2 MB. Oversized bodies are refused (413) on the
    original and the attempt endpoints alike — including via the fallback path
    that names the part like a phone recording."""
    oversized = b"\x00" * (2_000_000 + 1)
    g = registry.create("solo")
    r = client.post(
        f"/api/games/{g.code}/original",
        files={"file": ("original.webm", oversized, "audio/webm")},
        data={"playerId": ""},
    )
    assert r.status_code == 413

    g.original = {"durationMs": 1000}
    g.phase = Phase.AUDIENCE_RECORDING
    r = client.post(
        f"/api/games/{g.code}/attempts",
        files={"file": ("memo.m4a", oversized, "audio/x-m4a")},
        data={"name": "Ada", "playerId": ""},
    )
    assert r.status_code == 413


def test_attempt_accepts_video_recorder_upload(client, webm_bytes):
    """iOS opens the *video* recorder from the file input; the phone posts a
    .mov / video-mimetype part. ffmpeg keeps the audio stream, caps still apply,
    and the stored clip is reachable."""
    g = registry.create("solo")
    client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes), data={"playerId": ""})
    g.phase = Phase.AUDIENCE_RECORDING

    r = client.post(
        f"/api/games/{g.code}/attempts",
        files={"file": ("clip.mov", webm_bytes, "video/quicktime")},
        data={"name": "Ida", "playerId": ""},
    )
    assert r.status_code == 200
    eid = r.json()["id"]
    assert registry.get(g.code).attempts[0]["sourceExt"] == "mov"
    assert client.get(g.audio_url(f"attempt_{eid}_source.mov")).status_code == 200


def test_attempts_multi_phase_gate_and_replace(client, webm_bytes):
    g = registry.create("multi")
    g.add_player("H", as_host=True)
    p = g.add_player("Ada")
    g.original = {"durationMs": 1000}

    # round not open yet
    r = client.post(f"/api/games/{g.code}/attempts", files=_files(webm_bytes),
                    data={"name": "Ada", "playerId": p.id})
    assert r.status_code == 409

    g.phase = Phase.AUDIENCE_RECORDING
    r1 = client.post(f"/api/games/{g.code}/attempts", files=_files(webm_bytes),
                     data={"name": "Ada", "playerId": p.id})
    assert r1.status_code == 200
    first_id = r1.json()["id"]

    r2 = client.post(f"/api/games/{g.code}/attempts", files=_files(webm_bytes),
                     data={"name": "Ada", "playerId": p.id})
    assert r2.status_code == 200 and r2.json()["id"] != first_id
    assert len(registry.get(g.code).attempts) == 1          # replaced, not appended
    # old reversed clip is gone
    assert client.get(g.audio_url(f"attempt_{first_id}_reversed.wav")).status_code == 404


def test_attempts_unknown_player_rejected(client, webm_bytes):
    g = registry.create("multi")
    g.add_player("H", as_host=True)
    g.original = {"durationMs": 1000}
    g.phase = Phase.AUDIENCE_RECORDING
    r = client.post(f"/api/games/{g.code}/attempts", files=_files(webm_bytes),
                    data={"name": "Ghost", "playerId": "nobody"})
    assert r.status_code == 403


def test_audio_allowlist_and_traversal(client, webm_bytes):
    g = registry.create("solo")
    client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes), data={"playerId": ""})

    assert client.get(g.audio_url("original_reversed.wav")).status_code == 200
    for bad in ("game.json", "original_source.exe", "../../etc/passwd", "attempt_x_reversed.mp3"):
        assert client.get(g.audio_url(bad)).status_code == 404


def test_audio_needs_the_games_media_key(client, webm_bytes):
    """The short room code alone must not unlock a game's recordings."""
    g = registry.create("solo")
    client.post(f"/api/games/{g.code}/original", files=_files(webm_bytes), data={"playerId": ""})

    assert client.get(g.audio_url("original_reversed.wav")).status_code == 200
    base = f"/api/games/{g.code}/audio"
    assert client.get(f"{base}/original_reversed.wav").status_code == 404        # no key
    assert client.get(f"{base}/wrong-key/original_reversed.wav").status_code == 404
    other = registry.create("solo")                                             # another game's key
    assert client.get(f"{base}/{other.media_key}/original_reversed.wav").status_code == 404
    # the key never lands in the stored game.json mirror
    assert g.media_key not in storage.get_text(f"games/{g.code}/game.json")
