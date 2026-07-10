from __future__ import annotations

import argparse
import csv
import sys
import tempfile
import time
from pathlib import Path
from types import SimpleNamespace
from typing import Any, Callable

from evaluation.scripts.chapter6.compile_results import summarize_latencies


FIELDS = ["path", "sample_count", "mean_ms", "p50_ms", "p95_ms", "min_ms", "max_ms", "success_rate", "external_api_ms", "total_time_ms", "source"]


def _benchmark(function: Callable[[], Any], count: int) -> tuple[list[float], int]:
    latencies: list[float] = []
    successes = 0
    for _ in range(count):
        started = time.perf_counter()
        try:
            function()
            successes += 1
        finally:
            latencies.append((time.perf_counter() - started) * 1000)
    return latencies, successes


def _row(name: str, latencies: list[float], successes: int, source: str, external: str = "不适用/未分阶段") -> dict[str, Any]:
    summary = summarize_latencies(latencies)
    return {
        "path": name,
        **summary,
        "success_rate": round(successes / len(latencies), 4) if latencies else 0,
        "external_api_ms": external,
        "total_time_ms": round(sum(latencies), 2),
        "source": source,
    }


def run(project_root: Path, results_path: Path) -> list[dict[str, Any]]:
    backend = project_root / "backend"
    sys.path.insert(0, str(backend))

    from app.crud.detection_crud import get_detection_history
    from app.crud.user import get_user_by_id
    from app.db.session import SessionLocal
    from app.models.detection_record import DetectionRecord
    from app.services.report_service import _build_report_context, _convert_html_to_pdf, _render_report_html
    from app.services.statistics_service import get_statistics_overview
    from app.services.web.web_content_fetcher import WebContentFetcher

    generated: list[dict[str, Any]] = []
    with SessionLocal() as db:
        admin = SimpleNamespace(id=0, role="admin")
        history_times, history_successes = _benchmark(
            lambda: get_detection_history(db, current_user=admin, page=1, page_size=20),
            20,
        )
        generated.append(_row("历史记录分页（MySQL只读）", history_times, history_successes, "当前MySQL；page=1,page_size=20"))

        stats_times, stats_successes = _benchmark(lambda: get_statistics_overview(db), 20)
        generated.append(_row("管理员统计概览（MySQL只读）", stats_times, stats_successes, "当前MySQL；get_statistics_overview"))

        record = db.query(DetectionRecord).order_by(DetectionRecord.id.asc()).first()
        if record is not None:
            _ = list(record.evidence_matches)
            owner = get_user_by_id(db, record.user_id) if record.user_id is not None else None
            context = _build_report_context(record, owner)
            with tempfile.TemporaryDirectory() as directory:
                counter = {"value": 0}

                def generate_pdf() -> None:
                    counter["value"] += 1
                    html = _render_report_html(context)
                    _convert_html_to_pdf(html, Path(directory) / f"report_{counter['value']}.pdf")

                pdf_times, pdf_successes = _benchmark(generate_pdf, 5)
            generated.append(_row("PDF生成（既有检测记录内容）", pdf_times, pdf_successes, f"detection_id={record.id}; 临时文件已清理"))

    with (project_root / "evaluation" / "datasets" / "news_eval.csv").open("r", encoding="utf-8-sig", newline="") as handle:
        sample = next(csv.DictReader(handle))
    fetcher = WebContentFetcher(timeout=10)
    url_times, url_successes = _benchmark(lambda: fetcher.fetch_article(sample["url"]), 3)
    generated.append(_row("URL提取（既有评测样本URL）", url_times, url_successes, f"sample_id={sample['sample_id']}", external="包含网页网络耗时"))

    existing: list[dict[str, Any]] = []
    if results_path.exists():
        with results_path.open("r", encoding="utf-8-sig", newline="") as handle:
            existing = [dict(row) for row in csv.DictReader(handle)]
    names = {row["path"] for row in generated}
    combined = [row for row in existing if row.get("path") not in names] + generated
    with results_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=FIELDS, extrasaction="ignore")
        writer.writeheader()
        writer.writerows(combined)
    return generated


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--run-dir", type=Path, required=True)
    args = parser.parse_args()
    output = args.run_dir.resolve() / "results" / "performance_results.csv"
    rows = run(args.project_root.resolve(), output)
    print(f"additional_performance_paths={len(rows)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
