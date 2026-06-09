from collections import deque
from threading import Lock
from time import monotonic
from typing import Callable


class InMemoryRateLimiter:
    """Lightweight per-key sliding window rate limiter."""

    def __init__(self, clock: Callable[[], float] | None = None) -> None:
        self._clock = clock or monotonic
        self._requests: dict[str, deque[float]] = {}
        self._lock = Lock()

    def allow_request(self, key: str, limit: int, window_seconds: int) -> bool:
        if limit <= 0 or window_seconds <= 0:
            return True

        now = self._clock()
        window_start = now - window_seconds

        with self._lock:
            timestamps = self._requests.setdefault(key, deque())
            while timestamps and timestamps[0] <= window_start:
                timestamps.popleft()

            if len(timestamps) >= limit:
                return False

            timestamps.append(now)
            return True

    def clear(self, key: str | None = None) -> None:
        with self._lock:
            if key is None:
                self._requests.clear()
            else:
                self._requests.pop(key, None)
