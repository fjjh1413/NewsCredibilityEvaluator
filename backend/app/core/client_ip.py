import ipaddress
from collections.abc import Iterable

from fastapi import Request

from app.core.config import get_settings


def get_client_ip(request: Request) -> str:
    """Return the best client IP without trusting spoofable proxy headers by default."""
    direct_host = _direct_client_host(request)
    trusted_proxy_networks = getattr(get_settings(), "trusted_proxy_networks", [])

    if _is_trusted_proxy(direct_host, trusted_proxy_networks):
        forwarded_ip = _first_forwarded_ip(request.headers.get("x-forwarded-for", ""))
        if forwarded_ip:
            return forwarded_ip

        real_ip = _parse_ip_header(request.headers.get("x-real-ip", ""))
        if real_ip:
            return real_ip

    return direct_host or "unknown"


def _direct_client_host(request: Request) -> str | None:
    if request.client and request.client.host:
        return request.client.host
    return None


def _is_trusted_proxy(
    host: str | None,
    trusted_proxy_networks: Iterable[ipaddress.IPv4Network | ipaddress.IPv6Network],
) -> bool:
    if not host:
        return False

    try:
        host_ip = ipaddress.ip_address(host)
    except ValueError:
        return False

    return any(host_ip in network for network in trusted_proxy_networks)


def _first_forwarded_ip(header_value: str) -> str | None:
    for candidate in header_value.split(","):
        parsed_ip = _parse_ip_header(candidate)
        if parsed_ip:
            return parsed_ip
    return None


def _parse_ip_header(header_value: str | None) -> str | None:
    if not header_value:
        return None

    candidate = header_value.strip()
    if not candidate:
        return None

    try:
        return str(ipaddress.ip_address(candidate))
    except ValueError:
        return None
