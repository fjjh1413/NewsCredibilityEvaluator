from collections import deque
import hashlib
import logging
from threading import Lock
from time import monotonic
from typing import Callable

from app.core.config import Settings, get_settings
from app.core.redis_client import RedisUnavailableError, redis_manager


logger = logging.getLogger(__name__)

REDIS_RATE_LIMIT_SCRIPT = """
local current = redis.call('INCR', KEYS[1])
if current == 1 then
  redis.call('EXPIRE', KEYS[1], tonumber(ARGV[1]))
end
if current > tonumber(ARGV[2]) then
  return 0
end
return 1
"""


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


class RedisBackedRateLimiter:
    """Redis-first fixed-window limiter with in-memory fallback."""

    def __init__(
        self,
        namespace: str,
        clock: Callable[[], float] | None = None,
    ) -> None:
        self._namespace = namespace
        self._fallback = InMemoryRateLimiter(clock=clock)

    async def allow_request(
        self,
        key: str,
        limit: int,
        window_seconds: int,
        settings: Settings | None = None,
    ) -> bool:
        if limit <= 0 or window_seconds <= 0:
            return True

        settings = settings or get_settings()
        redis_enabled = getattr(settings, "redis_enabled", False)
        redis_required = getattr(settings, "redis_required", False)
        if not redis_enabled:
            return self._fallback.allow_request(key, limit, window_seconds)

        client = redis_manager.client
        if client is None:
            if redis_required:
                raise RedisUnavailableError("Redis rate limiter is unavailable")
            return self._fallback.allow_request(key, limit, window_seconds)

        redis_key = self._redis_key(getattr(settings, "cache_key_prefix", "newscred"), key)
        try:
            result = await client.eval(
                REDIS_RATE_LIMIT_SCRIPT,
                1,
                redis_key,
                int(window_seconds),
                int(limit),
            )
            return bool(int(result))
        except Exception as exc:
            logger.exception("Redis rate limiter failed namespace=%s", self._namespace)
            if redis_required:
                raise RedisUnavailableError("Redis rate limiter failed") from exc
            return self._fallback.allow_request(key, limit, window_seconds)

    def clear(self, key: str | None = None) -> None:
        self._fallback.clear(key)

    def _redis_key(self, prefix: str, key: str) -> str:
        digest = hashlib.sha256(key.encode("utf-8")).hexdigest()
        return f"{prefix}:rate-limit:v1:{self._namespace}:{digest}"
