import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.rate_limit import RedisBackedRateLimiter
from app.core.redis_client import RedisUnavailableError


class _FakeRedisClient:
    def __init__(self) -> None:
        self.counts: dict[str, int] = {}
        self.calls: list[tuple] = []

    async def eval(self, script, numkeys, key, window_seconds, limit):
        self.calls.append((script, numkeys, key, window_seconds, limit))
        self.counts[key] = self.counts.get(key, 0) + 1
        return 1 if self.counts[key] <= int(limit) else 0


def _settings(**overrides):
    defaults = {
        "redis_enabled": True,
        "redis_required": False,
        "cache_key_prefix": "testapp",
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class RedisBackedRateLimiterTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_uses_redis_eval_when_redis_is_available(self) -> None:
        client = _FakeRedisClient()
        limiter = RedisBackedRateLimiter("auth:login")

        with patch("app.core.rate_limit.redis_manager", SimpleNamespace(client=client)):
            first = await limiter.allow_request("203.0.113.1", 1, 60, _settings())
            second = await limiter.allow_request("203.0.113.1", 1, 60, _settings())

        self.assertTrue(first)
        self.assertFalse(second)
        self.assertEqual(len(client.calls), 2)
        self.assertIn("testapp:rate-limit:v1:auth:login:", client.calls[0][2])

    async def test_falls_back_to_memory_when_redis_is_disabled(self) -> None:
        limiter = RedisBackedRateLimiter("detect:news")
        settings = _settings(redis_enabled=False)

        first = await limiter.allow_request("203.0.113.2", 1, 60, settings)
        second = await limiter.allow_request("203.0.113.2", 1, 60, settings)

        self.assertTrue(first)
        self.assertFalse(second)

    async def test_raises_when_required_redis_client_is_missing(self) -> None:
        limiter = RedisBackedRateLimiter("auth:register")

        with patch("app.core.rate_limit.redis_manager", SimpleNamespace(client=None)):
            with self.assertRaises(RedisUnavailableError):
                await limiter.allow_request(
                    "203.0.113.3",
                    1,
                    60,
                    _settings(redis_required=True),
                )


if __name__ == "__main__":
    unittest.main()
