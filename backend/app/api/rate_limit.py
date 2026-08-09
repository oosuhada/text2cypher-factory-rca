"""Small in-process rate limiter for the public demo query surface."""

from __future__ import annotations

from collections import OrderedDict, deque
from dataclasses import dataclass
from math import ceil
from threading import Lock
from time import monotonic
from typing import Callable


@dataclass(frozen=True)
class RateLimitDecision:
    allowed: bool
    retry_after_seconds: int = 0


class SlidingWindowRateLimiter:
    """Thread-safe bounded sliding-window limiter for one application process."""

    def __init__(
        self,
        *,
        limit: int,
        window_seconds: int,
        max_keys: int = 2048,
        clock: Callable[[], float] = monotonic,
    ):
        if limit < 1:
            raise ValueError("limit must be at least 1")
        if window_seconds < 1:
            raise ValueError("window_seconds must be at least 1")
        if max_keys < 1:
            raise ValueError("max_keys must be at least 1")
        self.limit = limit
        self.window_seconds = window_seconds
        self.max_keys = max_keys
        self.clock = clock
        self._events: OrderedDict[str, deque[float]] = OrderedDict()
        self._lock = Lock()

    def check(self, key: str) -> RateLimitDecision:
        now = self.clock()
        cutoff = now - self.window_seconds
        normalized_key = key.strip() or "unknown"
        with self._lock:
            bucket = self._events.get(normalized_key)
            if bucket is None:
                bucket = deque()
                self._events[normalized_key] = bucket
            else:
                self._events.move_to_end(normalized_key)

            while bucket and bucket[0] <= cutoff:
                bucket.popleft()

            if len(bucket) >= self.limit:
                retry_after = max(
                    1,
                    ceil(bucket[0] + self.window_seconds - now),
                )
                return RateLimitDecision(
                    allowed=False,
                    retry_after_seconds=retry_after,
                )

            bucket.append(now)
            while len(self._events) > self.max_keys:
                self._events.popitem(last=False)
            return RateLimitDecision(allowed=True)
