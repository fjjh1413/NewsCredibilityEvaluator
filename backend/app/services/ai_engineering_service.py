"""Read offline AI engineering quality gate summaries for the admin console."""

from __future__ import annotations

import json
import sys
from pathlib import Path
from typing import Any, Iterable


PROJECT_ROOT = Path(__file__).resolve().parents[3]
if str(PROJECT_ROOT) not in sys.path:
    sys.path.append(str(PROJECT_ROOT))

from evaluation.ai_engineering.metrics import evaluate_cases  # noqa: E402
from evaluation.ai_engineering.runner import load_jsonl  # noqa: E402

SUMMARY_PATH_CANDIDATES = (
    PROJECT_ROOT / ".artifacts" / "ai_eval" / "summary.json",
    PROJECT_ROOT / "evaluation" / "output" / "ai_engineering_summary.json",
    PROJECT_ROOT / "evaluation" / "ai_engineering" / "summary.json",
)
SAMPLE_CASES_PATH = PROJECT_ROOT / "evaluation" / "ai_engineering" / "sample_cases.jsonl"
MAX_PER_CASE_ROWS = 100


class AiEngineeringSummaryNotFoundError(FileNotFoundError):
    pass


def get_ai_engineering_summary(
    *,
    summary_paths: Iterable[str | Path] | None = None,
    sample_cases_path: str | Path | None = None,
) -> dict[str, Any]:
    paths = tuple(Path(path) for path in (summary_paths or SUMMARY_PATH_CANDIDATES))
    summary_path = _first_existing_path(paths)
    if summary_path is not None:
        payload = json.loads(summary_path.read_text(encoding="utf-8"))
        return _normalize_summary(
            payload,
            source_type="summary_file",
            source_path=summary_path,
        )

    cases_path = Path(sample_cases_path or SAMPLE_CASES_PATH)
    if cases_path.exists():
        payload = evaluate_cases(load_jsonl(cases_path))
        return _normalize_summary(
            payload,
            source_type="sample_cases",
            source_path=cases_path,
        )

    raise AiEngineeringSummaryNotFoundError("AI engineering summary not found")


def _first_existing_path(paths: Iterable[Path]) -> Path | None:
    for path in paths:
        if path.exists() and path.is_file():
            return path
    return None


def _normalize_summary(
    payload: dict[str, Any],
    *,
    source_type: str,
    source_path: Path,
) -> dict[str, Any]:
    metrics = payload.get("metrics") if isinstance(payload.get("metrics"), dict) else {}
    gate = payload.get("gate") if isinstance(payload.get("gate"), dict) else {}
    per_case = payload.get("per_case") if isinstance(payload.get("per_case"), list) else []

    return {
        "source": {
            "type": source_type,
            "path": _display_path(source_path),
        },
        "schema_version": payload.get("schema_version") or "ai-engineering-eval/v1",
        "generated_at": payload.get("generated_at"),
        "metrics": metrics,
        "gate": {
            "passed": bool(gate.get("passed")),
            "failures": gate.get("failures") if isinstance(gate.get("failures"), list) else [],
            "thresholds": gate.get("thresholds") if isinstance(gate.get("thresholds"), dict) else {},
        },
        "per_case": [row for row in per_case if isinstance(row, dict)][:MAX_PER_CASE_ROWS],
    }


def _display_path(path: Path) -> str:
    try:
        return path.resolve().relative_to(PROJECT_ROOT.resolve()).as_posix()
    except ValueError:
        return str(path)
