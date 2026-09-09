"""SongLibrary: manifest CRUD + clip ingest under assets/songs/."""

from io import BytesIO

import anyio
import pytest
from fastapi import HTTPException, UploadFile
from starlette.datastructures import Headers

from server.songs import SongLibrary, clean_lines, slugify
from server.storage import LocalDiskStorage


@pytest.fixture
def lib(tmp_path):
    return SongLibrary(LocalDiskStorage(tmp_path))


def _add(lib, name, raw, *, mime="audio/webm", filename="take.webm", max_seconds=60):
    async def go():
        up = UploadFile(
            filename=filename,
            file=BytesIO(raw),
            headers=Headers({"content-type": mime}),
        )
        return await lib.add(name, up, max_seconds=max_seconds)
    return anyio.run(go)


def test_slugify():
    assert slugify("Happy Birthday to You!") == "happy-birthday-to-you"
    assert slugify("  --Twinkle--  ") == "twinkle"
    assert slugify("???") == "song"


def test_add_writes_manifest_and_three_clips(lib, webm_bytes):
    entry = _add(lib, "Happy Birthday", webm_bytes)
    assert entry["slug"] == "happy-birthday" and entry["enabled"] is True
    assert entry["durationMs"] > 0 and entry["sourceExt"] == "webm"
    assert entry["lines"] == []

    store = lib._storage
    for name in ("source.webm", "reversed.wav", "forward.wav"):
        assert store.local_path(f"assets/songs/happy-birthday/{name}").is_file()
    assert [s["slug"] for s in lib.list()] == ["happy-birthday"]


def test_slug_dedup(lib, webm_bytes):
    a = _add(lib, "Row Your Boat", webm_bytes)
    b = _add(lib, "row your boat", webm_bytes)
    assert (a["slug"], b["slug"]) == ("row-your-boat", "row-your-boat-2")


def test_name_falls_back_to_filename(lib, webm_bytes):
    entry = _add(lib, "   ", webm_bytes, filename="Jingle Bells.webm")
    assert entry["name"] == "Jingle Bells" and entry["slug"] == "jingle-bells"


def test_rename_enable_delete(lib, webm_bytes):
    _add(lib, "Song One", webm_bytes)
    assert lib.rename("song-one", "Renamed")["name"] == "Renamed"
    assert lib.rename("song-one", "   ") is None
    assert lib.set_enabled("song-one", False)["enabled"] is False

    assert lib.delete("song-one") is True
    assert lib.list() == []
    assert lib._storage.local_path("assets/songs/song-one") is not None
    assert not lib._storage.local_path("assets/songs/song-one").exists()
    assert lib.delete("song-one") is False


def test_clip_key(lib, webm_bytes):
    _add(lib, "Clip Keys", webm_bytes)
    assert lib.clip_key("clip-keys", "reversed") == "assets/songs/clip-keys/reversed.wav"
    assert lib.clip_key("clip-keys", "source") == "assets/songs/clip-keys/source.webm"
    assert lib.clip_key("clip-keys", "bogus") is None
    assert lib.clip_key("missing", "reversed") is None


def test_set_lines_normalises(lib, webm_bytes):
    _add(lib, "Relay Song", webm_bytes)
    updated = lib.set_lines(
        "relay-song",
        [
            {"startMs": 900, "endMs": 1800, "label": " verse 2 "},
            {"startMs": -50, "endMs": 20, "label": "x" * 100},
            {"startMs": 5000, "endMs": 1000, "label": "end before start -> clamped"},
            {"startMs": "nope", "endMs": 1},          # dropped
            {"endMs": 1},                              # missing startMs -> dropped
        ],
    )
    assert updated["lines"] == [
        {"startMs": 0, "endMs": 20, "label": "x" * 60},
        {"startMs": 900, "endMs": 1800, "label": "verse 2"},
        {"startMs": 5000, "endMs": 5000, "label": "end before start -> clamped"},
    ]


def test_add_rejects_overlong_upload(lib, webm_long):
    with pytest.raises(HTTPException) as ei:
        _add(lib, "Too Long", webm_long, max_seconds=5)
    assert ei.value.status_code == 400
    assert lib.list() == []


def test_add_rejects_non_audio(lib):
    with pytest.raises(HTTPException) as ei:
        _add(lib, "Junk", b"this is not audio at all")
    assert ei.value.status_code == 400


def test_clean_lines_is_pure():
    assert clean_lines(None) == []
    assert clean_lines([{"startMs": 10, "endMs": 5}]) == [
        {"startMs": 10, "endMs": 10, "label": ""}
    ]
