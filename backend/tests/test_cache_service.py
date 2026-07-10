import asyncio
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.cache import CacheService, build_cache_key


class _FakeRedisClient:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.set_calls: list[tuple] = []

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str, ex: int):
        self.values[key] = value
        self.set_calls.append((key, value, ex))
        return True

    async def delete(self, key: str):
        self.values.pop(key, None)
        return 1


def _settings(**overrides):
    defaults = {
        "redis_enabled": True,
        "cache_key_prefix": "testapp",
        "cache_default_ttl_seconds": 300,
        "cache_ttl_jitter_seconds": 0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class CacheServiceTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_get_or_set_returns_producer_value_when_redis_disabled(self) -> None:
        cache = CacheService()
        calls = 0

        async def producer():
            nonlocal calls
            calls += 1
            return {"count": calls}

        value = await cache.get_or_set(
            "admin:statistics:v1:overview",
            producer,
            settings=_settings(redis_enabled=False),
        )

        self.assertEqual(value, {"count": 1})
        self.assertEqual(calls, 1)

    async def test_get_or_set_caches_json_value_in_redis(self) -> None:
        cache = CacheService()
        client = _FakeRedisClient()
        calls = 0

        async def producer():
            nonlocal calls
            calls += 1
            return {"total": calls}

        with patch("app.core.cache.redis_manager", SimpleNamespace(client=client)):
            first = await cache.get_or_set("stats", producer, settings=_settings())
            second = await cache.get_or_set("stats", producer, settings=_settings())

        self.assertEqual(first, {"total": 1})
        self.assertEqual(second, {"total": 1})
        self.assertEqual(calls, 1)
        self.assertEqual(client.set_calls[0][2], 300)

    async def test_get_or_set_collapses_concurrent_cache_misses(self) -> None:
        cache = CacheService()
        client = _FakeRedisClient()
        calls = 0

        async def producer():
            nonlocal calls
            calls += 1
            await asyncio.sleep(0.01)
            return {"total": calls}

        with patch("app.core.cache.redis_manager", SimpleNamespace(client=client)):
            first, second = await asyncio.gather(
                cache.get_or_set("stats", producer, settings=_settings()),
                cache.get_or_set("stats", producer, settings=_settings()),
            )

        self.assertEqual(first, {"total": 1})
        self.assertEqual(second, {"total": 1})
        self.assertEqual(calls, 1)
        self.assertEqual(len(client.set_calls), 1)

    def test_build_cache_key_uses_configured_prefix(self) -> None:
        key = build_cache_key("stats", settings=_settings(cache_key_prefix="prodapp"))

        self.assertEqual(key, "prodapp:cache:stats")


if __name__ == "__main__":
    unittest.main()
