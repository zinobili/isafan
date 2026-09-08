"""Token-bucket limiter + the two game-create call sites that use it."""

import pytest

from server.main import app, hub
from server.ratelimit import RateLimiter


def test_burst_then_deny_then_refill():
    rl = RateLimiter(capacity=3, per_seconds=60)
    assert [rl.allow("ip") for _ in range(3)] == [True, True, True]
    assert rl.allow("ip") is False
    # a different client has its own bucket
    assert rl.allow("other") is True
    # simulate 20s passing: 3 tokens / 60s -> +1 token
    rl._buckets["ip"].last -= 20
    assert rl.allow("ip") is True
    assert rl.allow("ip") is False


def test_capacity_zero_is_unlimited():
    rl = RateLimiter(capacity=0, per_seconds=60)
    assert rl.enabled is False
    assert all(rl.allow("ip") for _ in range(100))


def test_gc_drops_only_refilled_buckets():
    rl = RateLimiter(capacity=1, per_seconds=60)
    rl.allow("stale")          # emptied, then backdated so it fully refills
    rl._buckets["stale"].last -= 120
    rl.allow("hot")            # emptied just now
    rl._gc(__import__("time").monotonic())
    assert "stale" not in rl._buckets and "hot" in rl._buckets


def test_solo_endpoint_rate_limited(client, monkeypatch):
    monkeypatch.setattr("server.main.create_limiter", RateLimiter(2, 60))
    assert client.post("/api/solo").status_code == 200
    assert client.post("/api/solo").status_code == 200
    r = client.post("/api/solo")
    assert r.status_code == 429 and "too many" in r.json()["detail"]


def test_ws_create_rate_limited(client, monkeypatch):
    monkeypatch.setattr(hub, "_create_limiter", RateLimiter(1, 60))
    with client.websocket_connect("/ws") as ws:
        ws.send_json({"type": "create", "name": "A", "mode": "solo"})
        assert ws.receive_json()["type"] == "joined"
        ws.send_json({"type": "create", "name": "B", "mode": "solo"})
        assert ws.receive_json() == {
            "type": "error",
            "code": "rate_limited",
            "message": "too many games created — wait a moment and retry",
        }
