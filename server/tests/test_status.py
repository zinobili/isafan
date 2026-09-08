"""Admin status figures: server/admin/status.collect + the rendered page."""

import time
from types import SimpleNamespace

from server import retention
from server.admin import status
from server.config import settings
from server.game import GameRegistry, Phase
from server.storage import LocalDiskStorage
from server.main import registry


def test_collect_counts_games_clips_and_bytes(tmp_path):
    reg = GameRegistry(LocalDiskStorage(tmp_path), code_length=4, max_players=5)
    store = reg._storage
    g = reg.create(mode="solo")
    g.phase = Phase.REVERSED_PLAYBACK
    g.add_player("Ana")
    store.put_bytes(f"games/{g.code}/original_reversed.wav", b"\x00" * 1000)
    store.put_bytes(f"games/{g.code}/original_source.webm", b"\x00" * 500)
    fake = SimpleNamespace(
        data_dir=tmp_path,
        game_ttl_seconds=settings.game_ttl_seconds,
        purge_interval_seconds=settings.purge_interval_seconds,
    )
    s = status.collect(reg, store, fake, start_time=time.time() - 42)

    assert 42 <= s["uptime_seconds"] < 90
    assert [x["code"] for x in s["active_games"]] == [g.code]
    assert s["active_games"][0]["players"] == 1
    assert s["stored_game_count"] == 1
    assert s["clip_count"] == 2                       # .wav + _source.
    assert s["clip_bytes"] == 1500
    assert s["data_bytes"] >= 1500
    assert s["oldest_game_age_seconds"] is not None


def test_collect_reports_purge_schedule(tmp_path, monkeypatch):
    reg = GameRegistry(LocalDiskStorage(tmp_path), code_length=4, max_players=5)
    monkeypatch.setattr(retention, "last_sweep_at", 1_000.0)
    fake = SimpleNamespace(
        data_dir=tmp_path, game_ttl_seconds=3600, purge_interval_seconds=600
    )
    s = status.collect(reg, reg._storage, fake, start_time=time.time())
    assert s["purge_enabled"] is True
    assert s["next_sweep_at"] == 1_600.0

    off = SimpleNamespace(data_dir=tmp_path, game_ttl_seconds=0, purge_interval_seconds=600)
    assert status.collect(reg, reg._storage, off, start_time=time.time())["purge_enabled"] is False


def test_status_page_shows_a_live_game(client, admin_creds):
    g = registry.create(mode="multi")
    g.add_player("Host", as_host=True)
    client.post("/admin/login", data=admin_creds)

    page = client.get("/admin").text
    assert "Active games" in page and g.code in page and "Uptime" in page
    registry.drop(g.code)
