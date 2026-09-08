"""A tiny in-memory token-bucket rate limiter, keyed by client IP.

Used to cap how fast one client can create games (`POST /api/solo` and the
WebSocket `create` verb). Not distributed — fine while the app is a single
process; revisit alongside a shared store (see backlog Phase 7).
"""

from __future__ import annotations

import time

# Once distinct-IP buckets pass this, drop the ones that have fully refilled.
_GC_THRESHOLD = 4096


class _Bucket:
    __slots__ = ("tokens", "last")

    def __init__(self, capacity: float) -> None:
        self.tokens = capacity
        self.last = time.monotonic()


class RateLimiter:
    """`capacity` requests are allowed as a burst; the bucket then refills to
    full over `per_seconds`. `capacity <= 0` disables limiting entirely."""

    def __init__(self, capacity: int, per_seconds: float) -> None:
        self.capacity = float(capacity)
        self.refill_per_second = (
            self.capacity / per_seconds if capacity > 0 and per_seconds > 0 else 0.0
        )
        self._buckets: dict[str, _Bucket] = {}

    @property
    def enabled(self) -> bool:
        return self.capacity > 0

    def allow(self, key: str, cost: float = 1.0) -> bool:
        if not self.enabled:
            return True
        now = time.monotonic()
        b = self._buckets.get(key)
        if b is None:
            if len(self._buckets) >= _GC_THRESHOLD:
                self._gc(now)
            b = self._buckets[key] = _Bucket(self.capacity)
        else:
            b.tokens = min(
                self.capacity, b.tokens + (now - b.last) * self.refill_per_second
            )
            b.last = now
        if b.tokens >= cost:
            b.tokens -= cost
            return True
        return False

    def _gc(self, now: float) -> None:
        for key, b in list(self._buckets.items()):
            refilled = b.tokens + (now - b.last) * self.refill_per_second
            if refilled >= self.capacity:
                del self._buckets[key]
