"""Retention sweep: age-based purge of stored game folders."""

import json
import time

import pytest

from server.game import GameRegistry
from server.retention import purge_expired
from server.storage import LocalDiskStorage


@pytest.fixture
def reg(tmp_path):
    return GameRegistry(LocalDiskStorage(tmp_path), code_length=4, max_players=3)


def _age_game(storage, code, seconds):
    """Backdate a stored game's createdAt by `seconds`."""
    key = f"games/{code}/game.json"
    meta = json.loads(storage.get_text(key))
    meta["createdAt"] = time.time() - seconds
    storage.put_text(key, json.dumps(meta))


def test_purges_only_expired_games(reg):
    storage = reg._storage
    old = reg.create()
    young = reg.create()
    storage.put_bytes(f"games/{old.code}/original_reversed.wav", b"\x00\x01")
    _age_game(storage, old.code, 48 * 3600)

    purged = purge_expired(reg, storage, ttl_seconds=24 * 3600)

    assert purged == [old.code]
    assert reg.get(old.code) is None and reg.get(young.code) is young
    assert storage.list_children("games") == [young.code]


def test_ttl_zero_disables_purge(reg):
    g = reg.create()
    _age_game(reg._storage, g.code, 10 * 24 * 3600)
    assert purge_expired(reg, reg._storage, ttl_seconds=0) == []
    assert reg.get(g.code) is g


def test_falls_back_to_file_mtime_when_json_unreadable(reg, tmp_path):
    import os

    storage = reg._storage
    g = reg.create()
    storage.delete(f"games/{g.code}/game.json")  # only audio left, no metadata
    storage.put_bytes(f"games/{g.code}/original_reversed.wav", b"\x00")
    old = time.time() - 48 * 3600
    os.utime(tmp_path / "games" / g.code / "original_reversed.wav", (old, old))

    assert purge_expired(reg, storage, ttl_seconds=24 * 3600) == [g.code]
    assert not (tmp_path / "games" / g.code).exists()


def test_missing_metadata_and_no_mtime_is_left_alone(reg):
    """A folder we can't age (no json, no readable file times) is never deleted."""
    storage = reg._storage
    g = reg.create()
    storage.delete(f"games/{g.code}/game.json")
    storage.modified_at = lambda key: None  # hide every file time
    assert purge_expired(reg, storage, ttl_seconds=1) == []
