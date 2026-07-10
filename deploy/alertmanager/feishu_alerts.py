import json
import os
import sys
import urllib.error
import urllib.parse
import urllib.request
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from typing import Any


MAX_BODY_BYTES = 1024 * 1024
DEFAULT_LISTEN_HOST = "0.0.0.0"
DEFAULT_LISTEN_PORT = 8080
ALLOWED_WEBHOOK_HOSTS = {"open.feishu.cn", "open.larksuite.com"}


def format_feishu_text(payload: dict[str, Any]) -> str:
    status = str(payload.get("status") or "unknown").upper()
    alerts = payload.get("alerts")
    if not isinstance(alerts, list):
        alerts = []

    title = os.getenv("FEISHU_ALERT_TITLE", "NewsCred 告警")
    lines = [f"[{status}] {title}: {len(alerts)} alert(s)"]

    group_labels = payload.get("groupLabels")
    if isinstance(group_labels, dict) and group_labels:
        group = ", ".join(
            f"{key}={value}" for key, value in sorted(group_labels.items())
        )
        lines.append(f"Group: {group}")

    for alert in alerts[:10]:
        if not isinstance(alert, dict):
            continue
        labels = alert.get("labels") if isinstance(alert.get("labels"), dict) else {}
        annotations = (
            alert.get("annotations") if isinstance(alert.get("annotations"), dict) else {}
        )

        alert_name = labels.get("alertname", "unknown")
        severity = labels.get("severity", "unknown")
        service = labels.get("service", "unknown")
        summary = annotations.get("summary") or annotations.get("description") or ""
        runbook = annotations.get("runbook")

        lines.append(f"- {alert_name} [{severity}] service={service}")
        if summary:
            lines.append(f"  {summary}")
        if runbook:
            lines.append(f"  Runbook: {runbook}")

    if len(alerts) > 10:
        lines.append(f"... and {len(alerts) - 10} more alert(s)")

    external_url = payload.get("externalURL")
    if external_url:
        lines.append(f"Alertmanager: {external_url}")

    return "\n".join(lines)


def post_to_feishu(webhook_url: str, text: str) -> None:
    _validate_webhook_url(webhook_url)
    body = json.dumps(
        {
            "msg_type": "text",
            "content": {"text": text},
        },
        ensure_ascii=False,
    ).encode("utf-8")
    request = urllib.request.Request(
        webhook_url,
        data=body,
        headers={"Content-Type": "application/json; charset=utf-8"},
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=5) as response:
        response_body = response.read(4096)
        if response.status >= 400:
            raise RuntimeError(f"Feishu webhook HTTP {response.status}")
        _raise_for_feishu_error(response_body)


def _validate_webhook_url(webhook_url: str) -> None:
    parsed = urllib.parse.urlparse(webhook_url)
    if parsed.scheme != "https":
        raise RuntimeError("FEISHU_WEBHOOK_URL must use https")
    if parsed.hostname not in ALLOWED_WEBHOOK_HOSTS:
        raise RuntimeError("FEISHU_WEBHOOK_URL host is not allowed")
    if not parsed.path.startswith("/open-apis/bot/v2/hook/"):
        raise RuntimeError("FEISHU_WEBHOOK_URL path is not a bot v2 hook")


def _raise_for_feishu_error(response_body: bytes) -> None:
    if not response_body:
        return
    try:
        payload = json.loads(response_body.decode("utf-8"))
    except (UnicodeDecodeError, json.JSONDecodeError):
        return
    code = payload.get("code")
    if code not in (None, 0):
        message = str(payload.get("msg") or payload.get("message") or "unknown")
        raise RuntimeError(f"Feishu webhook returned code={code}: {message}")


class AlertHandler(BaseHTTPRequestHandler):
    server_version = "feishu-alert-bridge/1.0"

    def do_GET(self) -> None:
        if self.path != "/health":
            self._send_text(404, "not found")
            return
        self._send_text(200, "ok")

    def do_POST(self) -> None:
        if self.path != "/alert":
            self._send_text(404, "not found")
            return

        try:
            payload = self._read_json_body()
            webhook_url = os.environ["FEISHU_WEBHOOK_URL"]
            post_to_feishu(webhook_url, format_feishu_text(payload))
        except KeyError:
            self._send_text(500, "FEISHU_WEBHOOK_URL is not configured")
        except ValueError as exc:
            self._send_text(400, str(exc))
        except (RuntimeError, urllib.error.URLError) as exc:
            self._send_text(502, str(exc))
        else:
            self._send_text(200, "ok")

    def log_message(self, format: str, *args: Any) -> None:
        sys.stdout.write(f"{self.address_string()} {format % args}\n")

    def _read_json_body(self) -> dict[str, Any]:
        raw_length = self.headers.get("Content-Length", "")
        try:
            content_length = int(raw_length)
        except ValueError as exc:
            raise ValueError("invalid Content-Length") from exc
        if content_length > MAX_BODY_BYTES:
            raise ValueError("request body too large")
        body = self.rfile.read(content_length)
        try:
            payload = json.loads(body.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError) as exc:
            raise ValueError("request body must be JSON") from exc
        if not isinstance(payload, dict):
            raise ValueError("request body must be a JSON object")
        return payload

    def _send_text(self, status_code: int, body: str) -> None:
        encoded = body.encode("utf-8")
        self.send_response(status_code)
        self.send_header("Content-Type", "text/plain; charset=utf-8")
        self.send_header("Content-Length", str(len(encoded)))
        self.end_headers()
        self.wfile.write(encoded)


def main() -> None:
    webhook_url = os.environ.get("FEISHU_WEBHOOK_URL", "")
    _validate_webhook_url(webhook_url)

    host = os.getenv("LISTEN_HOST", DEFAULT_LISTEN_HOST)
    port = int(os.getenv("LISTEN_PORT", str(DEFAULT_LISTEN_PORT)))
    server = ThreadingHTTPServer((host, port), AlertHandler)
    print(f"Feishu alert bridge listening on {host}:{port}", flush=True)
    server.serve_forever()


if __name__ == "__main__":
    main()
