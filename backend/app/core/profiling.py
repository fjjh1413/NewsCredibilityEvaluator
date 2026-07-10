"""Pyroscope continuous profiling helpers.

Profiling is opt-in so local tests and development never require a running
Pyroscope server. Production can make it mandatory with PYROSCOPE_REQUIRED.
"""

from __future__ import annotations

import logging
from collections.abc import Iterator
from contextlib import contextmanager, nullcontext
from typing import Any


logger = logging.getLogger(__name__)

_PROFILING_CONFIGURED = False
_PROFILING_ENABLED = False


def configure_profiling(settings: Any, *, role: str) -> None:
    """Configure Pyroscope when explicitly enabled."""
    global _PROFILING_CONFIGURED, _PROFILING_ENABLED

    if _PROFILING_CONFIGURED:
        return
    _PROFILING_CONFIGURED = True

    if not getattr(settings, "pyroscope_enabled", False):
        logger.info("pyroscope_profiling_disabled")
        return

    try:
        import pyroscope
    except ImportError as exc:
        message = (
            "PYROSCOPE_ENABLED=true requires pyroscope-io. "
            "Install backend requirements in a non-Windows runtime or disable profiling."
        )
        if getattr(settings, "pyroscope_required", False):
            raise RuntimeError(message) from exc
        logger.warning(message)
        return

    application_name = _application_name(settings, role)
    configure_kwargs: dict[str, Any] = {
        "application_name": application_name,
        "server_address": settings.pyroscope_server_address,
        "sample_rate": settings.pyroscope_sample_rate,
        "oncpu": True,
        "gil_only": True,
        "enable_logging": False,
        "tags": {
            "service": settings.project_name,
            "role": role,
            "env": settings.environment,
            "version": settings.project_version,
        },
    }
    if settings.pyroscope_basic_auth_username:
        configure_kwargs["basic_auth_username"] = settings.pyroscope_basic_auth_username
    if settings.pyroscope_basic_auth_password:
        configure_kwargs["basic_auth_password"] = settings.pyroscope_basic_auth_password
    if settings.pyroscope_tenant_id:
        configure_kwargs["tenant_id"] = settings.pyroscope_tenant_id

    pyroscope.configure(**configure_kwargs)
    _PROFILING_ENABLED = True
    logger.info(
        "pyroscope_profiling_configured",
        extra={
            "event": "pyroscope_profiling_configured",
            "application_name": application_name,
            "server_address": settings.pyroscope_server_address,
            "sample_rate": settings.pyroscope_sample_rate,
            "role": role,
        },
    )


def is_profiling_enabled() -> bool:
    return _PROFILING_ENABLED


@contextmanager
def profile_block(tags: dict[str, str] | None = None) -> Iterator[None]:
    """Attach low-cardinality Pyroscope tags to a profiled block."""
    if not _PROFILING_ENABLED or not tags:
        with nullcontext():
            yield
        return

    try:
        import pyroscope
    except ImportError:
        with nullcontext():
            yield
        return

    with pyroscope.tag_wrapper(_sanitize_tags(tags)):
        yield


def _application_name(settings: Any, role: str) -> str:
    base_name = str(settings.pyroscope_application_name).strip() or settings.project_name
    role_suffix = role.replace(" ", "_").strip(".")
    if base_name.endswith(f".{role_suffix}"):
        return base_name
    return f"{base_name}.{role_suffix}"


def _sanitize_tags(tags: dict[str, str]) -> dict[str, str]:
    return {
        str(key)[:64]: str(value)[:128]
        for key, value in tags.items()
        if key and value
    }

