import unittest
from types import SimpleNamespace
from unittest.mock import patch

from app.core.redis_client import (
    RedisClientManager,
    RedisUnavailableError,
)


class _FakeRedisClient:
    def __init__(self, should_ping: bool = True) -> None:
        self.should_ping = should_ping
        self.closed = False

    async def ping(self) -> bool:
        if not self.should_ping:
            raise ConnectionError("redis down")
        return True

    async def aclose(self) -> None:
        self.closed = True


class _FakeRedisNamespace:
    created_client: _FakeRedisClient | None = None

    class Redis:
        @classmethod
        def from_url(cls, *args, **kwargs):
            client = _FakeRedisClient()
            _FakeRedisNamespace.created_client = client
            return client


def _settings(**overrides):
    defaults = {
        "redis_enabled": True,
        "redis_required": False,
        "redis_url": "redis://127.0.0.1:6379/0",
        "redis_socket_timeout_seconds": 1.0,
        "redis_socket_connect_timeout_seconds": 1.0,
    }
    defaults.update(overrides)
    return SimpleNamespace(**defaults)


class RedisClientManagerTestCase(unittest.IsolatedAsyncioTestCase):
    async def test_startup_is_noop_when_redis_is_disabled(self) -> None:
        manager = RedisClientManager()

        await manager.startup(_settings(redis_enabled=False))

        self.assertIsNone(manager.client)
        health = await manager.health(_settings(redis_enabled=False))
        self.assertEqual(health.status, "disabled")

    async def test_startup_creates_async_client_and_shutdown_closes_it(self) -> None:
        manager = RedisClientManager()
        with patch(
            "app.core.redis_client._import_redis_async",
            return_value=_FakeRedisNamespace,
        ):
            await manager.startup(_settings())

        self.assertIs(manager.client, _FakeRedisNamespace.created_client)
        health = await manager.health(_settings())
        self.assertEqual(health.status, "ok")

        await manager.shutdown()

        self.assertIsNone(manager.client)
        self.assertTrue(_FakeRedisNamespace.created_client.closed)

    async def test_startup_raises_when_required_redis_is_unavailable(self) -> None:
        manager = RedisClientManager()

        class FailingRedisNamespace:
            class Redis:
                @classmethod
                def from_url(cls, *args, **kwargs):
                    return _FakeRedisClient(should_ping=False)

        with patch(
            "app.core.redis_client._import_redis_async",
            return_value=FailingRedisNamespace,
        ):
            with self.assertRaises(RedisUnavailableError):
                await manager.startup(_settings(redis_required=True))

        self.assertIsNone(manager.client)


if __name__ == "__main__":
    unittest.main()
