import ipaddress
import unittest
from types import SimpleNamespace
from unittest.mock import patch

from starlette.requests import Request

from app.core.client_ip import get_client_ip


def _request(client_host: str, headers: dict[str, str] | None = None) -> Request:
    raw_headers = [
        (name.lower().encode("latin-1"), value.encode("latin-1"))
        for name, value in (headers or {}).items()
    ]
    return Request(
        {
            "type": "http",
            "method": "GET",
            "path": "/",
            "headers": raw_headers,
            "client": (client_host, 12345),
            "server": ("testserver", 80),
            "scheme": "http",
        }
    )


class ClientIpTestCase(unittest.TestCase):
    @patch("app.core.client_ip.get_settings")
    def test_ignores_forwarded_headers_from_untrusted_direct_client(
        self,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(trusted_proxy_networks=[])

        client_ip = get_client_ip(
            _request(
                "198.51.100.1",
                {
                    "X-Forwarded-For": "203.0.113.10",
                    "X-Real-IP": "203.0.113.11",
                },
            )
        )

        self.assertEqual(client_ip, "198.51.100.1")

    @patch("app.core.client_ip.get_settings")
    def test_uses_forwarded_for_from_trusted_proxy(self, mocked_get_settings) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            trusted_proxy_networks=[ipaddress.ip_network("10.0.0.0/8")]
        )

        client_ip = get_client_ip(
            _request("10.1.2.3", {"X-Forwarded-For": "203.0.113.10, 10.1.2.3"})
        )

        self.assertEqual(client_ip, "203.0.113.10")

    @patch("app.core.client_ip.get_settings")
    def test_uses_real_ip_from_trusted_proxy_when_forwarded_for_missing(
        self,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            trusted_proxy_networks=[ipaddress.ip_network("10.0.0.0/8")]
        )

        client_ip = get_client_ip(_request("10.1.2.3", {"X-Real-IP": "203.0.113.20"}))

        self.assertEqual(client_ip, "203.0.113.20")

    @patch("app.core.client_ip.get_settings")
    def test_invalid_forwarded_headers_fall_back_to_direct_client(
        self,
        mocked_get_settings,
    ) -> None:
        mocked_get_settings.return_value = SimpleNamespace(
            trusted_proxy_networks=[ipaddress.ip_network("10.0.0.0/8")]
        )

        client_ip = get_client_ip(
            _request("10.1.2.3", {"X-Forwarded-For": "unknown"})
        )

        self.assertEqual(client_ip, "10.1.2.3")


if __name__ == "__main__":
    unittest.main()
