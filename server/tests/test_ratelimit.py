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


def test_solo_limit_keys_on_forwarded_ip_when_proxy_trusted(client, monkeypatch):
    import dataclasses

    import server.main as main

    monkeypatch.setattr(main, "settings", dataclasses.replace(main.settings, trust_proxy=1))
    monkeypatch.setattr(main, "create_limiter", RateLimiter(1, 60))
    a = {"X-Forwarded-For": "203.0.113.1"}
    b = {"X-Forwarded-For": "203.0.113.2"}
    assert client.post("/api/solo", headers=a).status_code == 200
    assert client.post("/api/solo", headers=a).status_code == 429
    # same TCP peer, different forwarded client -> its own bucket
    assert client.post("/api/solo", headers=b).status_code == 200
    # a spoofed left-most entry doesn't buy a fresh bucket
    spoof = {"X-Forwarded-For": "198.51.100.9, 203.0.113.1"}
    assert client.post("/api/solo", headers=spoof).status_code == 429


def test_solo_limit_ignores_forwarded_header_by_default(client, monkeypatch):
    monkeypatch.setattr("server.main.create_limiter", RateLimiter(1, 60))
    assert client.post("/api/solo", headers={"X-Forwarded-For": "203.0.113.1"}).status_code == 200
    assert client.post("/api/solo", headers={"X-Forwarded-For": "203.0.113.2"}).status_code == 429


def test_ws_create_limit_keys_on_forwarded_ip_when_proxy_trusted(client, monkeypatch):
    monkeypatch.setattr(hub, "_create_limiter", RateLimiter(1, 60))
    monkeypatch.setattr(hub, "_trust_proxy", 1)
    for ip in ("203.0.113.1", "203.0.113.2"):
        with client.websocket_connect("/ws", headers={"X-Forwarded-For": ip}) as ws:
            ws.send_json({"type": "create", "name": "A", "mode": "solo"})
            assert ws.receive_json()["type"] == "joined"
    with client.websocket_connect("/ws", headers={"X-Forwarded-For": "203.0.113.1"}) as ws:
        ws.send_json({"type": "create", "name": "A", "mode": "solo"})
        assert ws.receive_json()["code"] == "rate_limited"


def test_ipv6_clients_share_a_bucket_per_64():
    rl = RateLimiter(1, 60)
    assert rl.allow("2001:db8:1:2::1") is True
    assert rl.allow("2001:db8:1:2::abcd") is False
    assert rl.allow("2001:db8:1:3::1") is True


def test_many_keys_stay_bounded_and_fast(monkeypatch):
    import time as _time

    from server import ratelimit

    monkeypatch.setattr(ratelimit, "_GC_THRESHOLD", 64)
    monkeypatch.setattr(ratelimit, "_MAX_BUCKETS", 256)
    rl = RateLimiter(5, 900)  # login-style: slow refill, so GC frees nothing
    rl._next_gc = 64
    start = _time.perf_counter()
    for i in range(20_000):
        rl.allow(f"198.51.{i // 256}.{i % 256}")
    assert len(rl._buckets) <= 256
    assert _time.perf_counter() - start < 2.0


def test_lru_eviction_keeps_recently_used_buckets(monkeypatch):
    from server import ratelimit

    monkeypatch.setattr(ratelimit, "_MAX_BUCKETS", 3)
    rl = RateLimiter(1, 60)
    for k in ("a", "b", "c"):
        rl.allow(k)
    rl.allow("a")          # touch a -> b is now oldest
    rl.allow("d")          # evicts b
    assert "b" not in rl._buckets and "a" in rl._buckets
