import asyncio
import inspect
import json
import logging
import random
from collections.abc import Awaitable, Callable
from threading import Lock
from typing import Any

from app.core.config import Settings, get_settings
from app.core.redis_client import redis_manager


logger = logging.getLogger(__name__)


class CacheService:
    """JSON cache-aside helper backed by Redis with safe fallback."""

    def __init__(self) -> None:
        self._locks: dict[tuple[int, str], asyncio.Lock] = {}
        self._locks_guard = Lock()

    async def get_or_set(
        self,
        key: str,
        producer: Callable[[], Any | Awaitable[Any]],
        *,
        ttl_seconds: int | None = None,
        settings: Settings | None = None,
    ) -> Any:
        settings = settings or get_settings()
        if not getattr(settings, "redis_enabled", False):
            return await _resolve(producer())

        client = redis_manager.client
        if client is None:
            return await _resolve(producer())

        cache_key = build_cache_key(key, settings=settings)
        try:
            cached = await client.get(cache_key)
            if cached is not None:
                return json.loads(cached)
        except Exception:
            logger.exception("Redis cache read failed key=%s", cache_key)
            return await _resolve(producer())

        async with self._lock_for(cache_key):
            try:
                cached = await client.get(cache_key)
                if cached is not None:
                    return json.loads(cached)
            except Exception:
                logger.exception("Redis cache read failed key=%s", cache_key)
                return await _resolve(producer())

            value = await _resolve(producer())
            try:
                await client.set(
                    cache_key,
                    json.dumps(value, ensure_ascii=False, default=str),
                    ex=_ttl_with_jitter(
                        ttl_seconds or settings.cache_default_ttl_seconds,
                        settings,
                    ),
                )
            except Exception:
                logger.exception("Redis cache write failed key=%s", cache_key)
            return value

    def _lock_for(self, cache_key: str) -> asyncio.Lock:
        loop_key = (id(asyncio.get_running_loop()), cache_key)
        with self._locks_guard:
            lock = self._locks.get(loop_key)
            if lock is None:
                lock = asyncio.Lock()
                self._locks[loop_key] = lock
            return lock

    async def delete(self, key: str, *, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        client = redis_manager.client
        if not getattr(settings, "redis_enabled", False) or client is None:
            return
        await client.delete(build_cache_key(key, settings=settings))


def build_cache_key(key: str, *, settings: Settings | None = None) -> str:
    settings = settings or get_settings()
    prefix = getattr(settings, "cache_key_prefix", "newscred").strip() or "newscred"
    return f"{prefix}:cache:{key}"


async def _resolve(value: Any | Awaitable[Any]) -> Any:
    if inspect.isawaitable(value):
        return await value
    return value


def _ttl_with_jitter(ttl_seconds: int, settings: Settings) -> int:
    jitter = getattr(settings, "cache_ttl_jitter_seconds", 0)
    if jitter <= 0:
        return ttl_seconds
    return ttl_seconds + random.randint(0, jitter)


cache_service = CacheService()
