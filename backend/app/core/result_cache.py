from __future__ import annotations

import hashlib
import json
import logging
import random
from collections.abc import Callable
from datetime import date, datetime
from threading import Lock
from typing import Any

from app.core.config import Settings, get_settings
from app.core.observability import record_cache_event


logger = logging.getLogger(__name__)


class SyncJsonCache:
    """Small Redis JSON cache-aside helper for synchronous service code."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._client_url: str | None = None
        self._lock = Lock()

    def get_or_set(
        self,
        *,
        namespace: str,
        key: str,
        ttl_seconds: int,
        producer: Callable[[], Any],
        settings: Settings | None = None,
    ) -> Any:
        settings = settings or get_settings()
        if not getattr(settings, "redis_enabled", False):
            record_cache_event(namespace, "disabled")
            return producer()

        client = self._client_for(settings)
        if client is None:
            record_cache_event(namespace, "unavailable")
            return producer()

        cache_key = build_result_cache_key(namespace, key, settings=settings)
        try:
            cached = client.get(cache_key)
            if cached is not None:
                record_cache_event(namespace, "hit")
                return json.loads(cached)
            record_cache_event(namespace, "miss")
        except Exception:
            logger.exception("Redis cache read failed key=%s", cache_key)
            record_cache_event(namespace, "error")
            return producer()

        value = producer()
        try:
            client.set(
                cache_key,
                json.dumps(value, ensure_ascii=False, default=_json_default),
                ex=_ttl_with_jitter(ttl_seconds, settings),
            )
            record_cache_event(namespace, "set")
        except Exception:
            logger.exception("Redis cache write failed key=%s", cache_key)
            record_cache_event(namespace, "error")
        return value

    def get_json(
        self,
        *,
        namespace: str,
        key: str,
        settings: Settings | None = None,
    ) -> Any | None:
        settings = settings or get_settings()
        if not getattr(settings, "redis_enabled", False):
            record_cache_event(namespace, "disabled")
            return None

        client = self._client_for(settings)
        if client is None:
            record_cache_event(namespace, "unavailable")
            return None

        cache_key = build_result_cache_key(namespace, key, settings=settings)
        try:
            cached = client.get(cache_key)
            if cached is None:
                record_cache_event(namespace, "miss")
                return None
            record_cache_event(namespace, "hit")
            return json.loads(cached)
        except Exception:
            logger.exception("Redis cache read failed key=%s", cache_key)
            record_cache_event(namespace, "error")
            return None

    def set_json(
        self,
        *,
        namespace: str,
        key: str,
        value: Any,
        ttl_seconds: int,
        settings: Settings | None = None,
    ) -> None:
        settings = settings or get_settings()
        if not getattr(settings, "redis_enabled", False):
            return

        client = self._client_for(settings)
        if client is None:
            record_cache_event(namespace, "unavailable")
            return

        cache_key = build_result_cache_key(namespace, key, settings=settings)
        try:
            client.set(
                cache_key,
                json.dumps(value, ensure_ascii=False, default=_json_default),
                ex=_ttl_with_jitter(ttl_seconds, settings),
            )
            record_cache_event(namespace, "set")
        except Exception:
            logger.exception("Redis cache write failed key=%s", cache_key)
            record_cache_event(namespace, "error")

    def _client_for(self, settings: Settings) -> Any | None:
        redis_url = settings.redis_url
        with self._lock:
            if self._client is not None and self._client_url == redis_url:
                return self._client

            try:
                import redis

                self._client = redis.Redis.from_url(
                    redis_url,
                    decode_responses=True,
                    socket_timeout=settings.redis_socket_timeout_seconds,
                    socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
                )
                self._client_url = redis_url
            except Exception:
                logger.exception("Redis sync client initialization failed")
                self._client = None
                self._client_url = None
            return self._client


def cache_key_from_payload(
    namespace: str,
    version: str,
    payload: Any,
) -> str:
    serialized = json.dumps(
        payload,
        ensure_ascii=False,
        sort_keys=True,
        separators=(",", ":"),
        default=_json_default,
    )
    digest = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    return f"v{version}:{digest}"


def build_result_cache_key(
    namespace: str,
    key: str,
    *,
    settings: Settings | None = None,
) -> str:
    settings = settings or get_settings()
    prefix = getattr(settings, "cache_key_prefix", "newscred").strip() or "newscred"
    return f"{prefix}:result-cache:{namespace}:{key}"


def _ttl_with_jitter(ttl_seconds: int, settings: Settings) -> int:
    jitter = getattr(settings, "cache_ttl_jitter_seconds", 0)
    if jitter <= 0:
        return ttl_seconds
    return ttl_seconds + random.randint(0, jitter)


def _json_default(value: Any) -> str:
    if isinstance(value, (date, datetime)):
        return value.isoformat()
    return str(value)


sync_json_cache = SyncJsonCache()
