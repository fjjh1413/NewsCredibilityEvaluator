from __future__ import annotations

import json
import time
from pathlib import Path
from typing import Any
from urllib.error import HTTPError, URLError
from urllib.parse import urlencode
from urllib.request import Request, urlopen


BASE_URL = "http://127.0.0.1:8000/api"
OUTPUT = Path(
    r"E:\nan\《基于 RAG 与大语言模型的网络新闻真伪鉴别系统设计》\报告\第五章撰写\chapter5_run.json"
)
DEMO_PASSWORD = "Chapter5Demo!2026"


def request_json(
    method: str,
    path: str,
    *,
    token: str | None = None,
    data: dict[str, Any] | None = None,
    timeout: int = 180,
) -> tuple[int, dict[str, Any]]:
    body = None
    headers = {"Accept": "application/json"}
    if data is not None:
        body = json.dumps(data, ensure_ascii=False).encode("utf-8")
        headers["Content-Type"] = "application/json"
    if token:
        headers["Authorization"] = f"Bearer {token}"
    req = Request(f"{BASE_URL}{path}", data=body, headers=headers, method=method)
    try:
        with urlopen(req, timeout=timeout) as resp:
            payload = json.loads(resp.read().decode("utf-8"))
            return resp.status, payload
    except HTTPError as exc:
        raw = exc.read().decode("utf-8", errors="replace")
        try:
            payload = json.loads(raw)
        except json.JSONDecodeError:
            payload = {"message": raw}
        return exc.code, payload
    except URLError as exc:
        return 0, {"message": str(exc)}


def login(username: str) -> str:
    status, payload = request_json(
        "POST",
        "/auth/login",
        data={"username": username, "password": DEMO_PASSWORD},
        timeout=30,
    )
    if status != 200:
        raise RuntimeError(f"login failed for {username}: {status} {payload}")
    return payload["data"]["access_token"]


def first_successful_preview(token: str | None) -> dict[str, Any]:
    urls = [
        "https://www.gov.cn/",
        "https://www.xinhuanet.com/",
        "https://www.example.com/",
    ]
    failures: list[dict[str, Any]] = []
    for url in urls:
        status, payload = request_json(
            "POST",
            "/detect/extract-preview",
            token=token,
            data={"url": url},
            timeout=40,
        )
        if status == 200 and payload.get("data"):
            return {"status": status, "url": url, "payload": payload}
        failures.append({"url": url, "status": status, "payload": payload})
    return {"status": 0, "url": None, "payload": {"failures": failures}}


def detect_news(token: str) -> dict[str, Any]:
    data = {
        "title": "网传喝柠檬水三天清除血管垃圾并替代降脂药",
        "content": (
            "近日有自媒体文章声称，连续三天饮用柠檬水就能清除血管垃圾、"
            "降低血脂并替代医生开具的降脂药。文章没有给出医学指南、"
            "临床研究或监管机构来源，只引用了匿名网友体验，并使用"
            "“百分百有效”“所有人都适用”等绝对化表达。"
        ),
        "category": "健康",
        "source_name": "第五章演示自媒体样例",
        "source_url": "https://example.com/chapter5/lemon-claim-demo",
        "publish_time": "2026-06-22T09:30:00",
        "enable_web_search": True,
    }
    status, payload = request_json("POST", "/detect/news", token=token, data=data, timeout=240)
    if status != 200:
        raise RuntimeError(f"detection failed: {status} {payload}")
    return payload


def generate_report(token: str, detection_id: int) -> dict[str, Any]:
    status, payload = request_json(
        "POST",
        f"/report/generate/{detection_id}",
        token=token,
        data=None,
        timeout=120,
    )
    return {"status": status, "payload": payload}


def get_path(token: str, path: str, query: dict[str, Any] | None = None) -> dict[str, Any]:
    suffix = path
    if query:
        suffix = f"{path}?{urlencode(query)}"
    status, payload = request_json("GET", suffix, token=token, timeout=60)
    return {"status": status, "payload": payload}


def main() -> None:
    user_token = login("chapter5_user")
    admin_token = login("chapter5_admin")
    preview = first_successful_preview(user_token)
    detection = detect_news(user_token)
    detection_id = int(detection["data"]["detection_id"])
    report = generate_report(user_token, detection_id)
    time.sleep(1)
    history = get_path(user_token, "/detect/history", {"page": 1, "page_size": 5})
    admin_knowledge = get_path(
        admin_token,
        "/admin/knowledge",
        {"page": 1, "page_size": 10, "keyword": "第五章演示"},
    )
    admin_logs = get_path(
        admin_token,
        "/admin/logs",
        {"page": 1, "page_size": 10},
    )
    admin_stats = get_path(admin_token, "/admin/statistics/overview")
    high_risk = get_path(admin_token, "/admin/high-risk", {"page": 1, "page_size": 5})
    result = {
        "base_url": BASE_URL,
        "frontend_url": "http://127.0.0.1:5173",
        "demo_user": "chapter5_user",
        "demo_admin": "chapter5_admin",
        "preview": preview,
        "detection": detection,
        "detection_id": detection_id,
        "report": report,
        "history": history,
        "admin_knowledge": admin_knowledge,
        "admin_logs": admin_logs,
        "admin_stats": admin_stats,
        "admin_high_risk": high_risk,
    }
    OUTPUT.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(OUTPUT)
    print(f"detection_id={detection_id}")
    print(f"risk_level={detection['data'].get('risk_level')}")
    print(f"final_score={detection['data'].get('final_score')}")
    print(f"arbitration_status={detection['data'].get('arbitration_status')}")
    print(f"quality_status={detection['data'].get('quality_status')}")
    print(f"web_search_triggered={detection['data'].get('web_search_triggered')}")
    print(f"report_status={report['status']}")


if __name__ == "__main__":
    main()
