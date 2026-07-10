import logging
from dataclasses import dataclass
from typing import Any

from app.core.config import Settings, get_settings


logger = logging.getLogger(__name__)


class RedisUnavailableError(RuntimeError):
    """Raised when Redis is required but cannot be used."""


@dataclass(frozen=True)
class RedisHealthStatus:
    enabled: bool
    status: str
    message: str

    def as_dict(self) -> dict[str, str | bool]:
        return {
            "enabled": self.enabled,
            "status": self.status,
            "message": self.message,
        }


class RedisClientManager:
    """Owns the async Redis client for the FastAPI application lifespan."""

    def __init__(self) -> None:
        self._client: Any | None = None
        self._last_error: str | None = None

    @property
    def client(self) -> Any | None:
        return self._client

    async def startup(self, settings: Settings | None = None) -> None:
        settings = settings or get_settings()
        if not settings.redis_enabled:
            self._client = None
            self._last_error = None
            return

        try:
            redis_async = _import_redis_async()
            self._client = redis_async.Redis.from_url(
                settings.redis_url,
                decode_responses=True,
                socket_timeout=settings.redis_socket_timeout_seconds,
                socket_connect_timeout=settings.redis_socket_connect_timeout_seconds,
            )
            await self._client.ping()
            self._last_error = None
            logger.info("Redis connection established")
        except Exception as exc:
            self._last_error = str(exc)
            logger.exception("Redis startup check failed")
            await self.shutdown()
            if settings.redis_required:
                raise RedisUnavailableError("Redis is required but unavailable") from exc

    async def shutdown(self) -> None:
        client = self._client
        self._client = None
        if client is None:
            return

        close = getattr(client, "aclose", None) or getattr(client, "close", None)
        if close is None:
            return
        result = close()
        if hasattr(result, "__await__"):
            await result

    async def health(self, settings: Settings | None = None) -> RedisHealthStatus:
        settings = settings or get_settings()
        if not settings.redis_enabled:
            return RedisHealthStatus(
                enabled=False,
                status="disabled",
                message="Redis is disabled",
            )

        if self._client is None:
            return RedisHealthStatus(
                enabled=True,
                status="unavailable",
                message=self._last_error or "Redis client is not initialized",
            )

        try:
            await self._client.ping()
        except Exception as exc:
            self._last_error = str(exc)
            return RedisHealthStatus(
                enabled=True,
                status="unavailable",
                message=str(exc),
            )

        self._last_error = None
        return RedisHealthStatus(
            enabled=True,
            status="ok",
            message="Redis is reachable",
        )


def _import_redis_async():
    try:
        import redis.asyncio as redis_async
    except ImportError as exc:
        raise RedisUnavailableError(
            "redis package is not installed. Install redis[hiredis]."
        ) from exc
    return redis_async


redis_manager = RedisClientManager()
