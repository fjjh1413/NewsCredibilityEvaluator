"""Command line runner for the AI engineering evaluation gate."""

from __future__ import annotations

import argparse
import copy
import csv
import json
from pathlib import Path
from typing import Any

from evaluation.ai_engineering.metrics import DEFAULT_K, evaluate_cases


def load_jsonl(path: str | Path) -> list[dict[str, Any]]:
    """Load JSON or JSONL rows, skipping blank and comment lines."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    if file_path.suffix.lower() == ".json":
        data = json.loads(file_path.read_text(encoding="utf-8"))
        if isinstance(data, list):
            return [row for row in data if isinstance(row, dict)]
        if isinstance(data, dict):
            rows = data.get("cases") or data.get("predictions")
            if isinstance(rows, list):
                return [row for row in rows if isinstance(row, dict)]
            return [data]
        raise ValueError(f"Unsupported JSON root in {file_path}")

    rows: list[dict[str, Any]] = []
    with file_path.open("r", encoding="utf-8") as f:
        for line_number, raw_line in enumerate(f, start=1):
            line = raw_line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                row = json.loads(line)
            except json.JSONDecodeError as exc:
                raise ValueError(f"Invalid JSONL at {file_path}:{line_number}: {exc}") from exc
            if not isinstance(row, dict):
                raise ValueError(f"Expected object at {file_path}:{line_number}")
            rows.append(row)
    return rows


def load_predictions(path: str | Path) -> dict[str, dict[str, Any]]:
    """Load predictions keyed by case_id/sample_id."""
    rows = load_jsonl(path)
    predictions: dict[str, dict[str, Any]] = {}
    for row in rows:
        case_id = str(row.get("case_id") or row.get("sample_id") or "").strip()
        if not case_id:
            raise ValueError("Prediction row missing case_id/sample_id")
        prediction = row.get("prediction")
        if prediction is None:
            prediction = {
                key: value
                for key, value in row.items()
                if key not in {"case_id", "sample_id", "input", "expected"}
            }
        if not isinstance(prediction, dict):
            raise ValueError(f"Prediction for {case_id} must be an object")
        predictions[case_id] = prediction
    return predictions


def load_results_csv_as_cases(path: str | Path) -> list[dict[str, Any]]:
    """Adapt existing evaluation per_case_results.csv rows to gate cases."""
    file_path = Path(path)
    if not file_path.exists():
        raise FileNotFoundError(f"File not found: {file_path}")

    with file_path.open("r", encoding="utf-8-sig", newline="") as f:
        rows = [row for row in csv.DictReader(f)]
    return [_csv_row_to_case(row, index) for index, row in enumerate(rows, start=1)]


def merge_predictions(
    cases: list[dict[str, Any]],
    predictions: dict[str, dict[str, Any]],
) -> list[dict[str, Any]]:
    """Return a copy of cases with external predictions merged by case_id."""
    merged = copy.deepcopy(cases)
    for case in merged:
        case_id = str(case.get("case_id") or case.get("sample_id") or "").strip()
        if case_id in predictions:
            case["prediction"] = copy.deepcopy(predictions[case_id])
    return merged


def _load_gate_config(path: str | Path | None) -> dict[str, float] | None:
    if not path:
        return None
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    if not isinstance(data, dict):
        raise ValueError("Gate config must be a JSON object")
    return {str(key): float(value) for key, value in data.items()}


def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Offline AI engineering evaluation gate for captured detect outputs.",
    )
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--cases", help="Path to JSONL/JSON eval cases.")
    source.add_argument(
        "--results-csv",
        help="Path to evaluation/output/per_case_results.csv from evaluation.run_evaluation.",
    )
    parser.add_argument(
        "--predictions",
        default=None,
        help="Optional JSONL/JSON predictions keyed by case_id/sample_id.",
    )
    parser.add_argument(
        "--output",
        default=".artifacts/ai_eval/summary.json",
        help="Path for the summary JSON.",
    )
    parser.add_argument(
        "--gate-config",
        default=None,
        help="Optional JSON object overriding default gate thresholds.",
    )
    parser.add_argument("--k", type=int, default=DEFAULT_K, help="Top-k evidence window.")
    return parser.parse_args(argv)


def main(argv: list[str] | None = None) -> int:
    args = parse_args(argv)
    cases = load_results_csv_as_cases(args.results_csv) if args.results_csv else load_jsonl(args.cases)
    if args.predictions:
        predictions = load_predictions(args.predictions)
        cases = merge_predictions(cases, predictions)

    summary = evaluate_cases(
        cases,
        gates=_load_gate_config(args.gate_config),
        k=args.k,
    )
    summary["publication_eligible"] = bool(cases) and all(case.get("gold_eligible") is True for case in cases)
    summary["publication_scope"] = "Regression gate only unless every case carries independently audited gold provenance; a passing fixture gate is not model accuracy."

    output_path = Path(args.output)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(
        json.dumps(summary, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    status = "PASS" if summary["gate"]["passed"] else "FAIL"
    print(
        f"AI engineering gate {status}: "
        f"{summary['metrics']['total_cases']} cases, "
        f"risk_accuracy={summary['metrics']['risk_level_accuracy']}, "
        f"context_recall@{args.k}={summary['metrics']['context_recall_at_k']}"
    )
    return 0 if summary["gate"]["passed"] else 2


def _csv_row_to_case(row: dict[str, Any], index: int) -> dict[str, Any]:
    sample_id = str(row.get("sample_id") or f"csv-{index}").strip()
    retrieved_ids = _split_ids(row.get("retrieved_knowledge_ids"))
    retrieved_ids.extend(_split_ids(row.get("retrieved_chunk_ids")))
    relevant_ids = _split_ids(row.get("relevant_knowledge_ids"))
    relevant_ids.extend(_split_ids(row.get("relevant_chunk_ids")))

    success = _truthy(row.get("success"))
    effective_ids = _split_ids(row.get("effective_evidence_ids"))
    stage_latency = {
        "parse": _float_or_none(row.get("parse_latency_ms")),
        "local_retrieval": _float_or_none(row.get("local_retrieval_latency_ms")),
        "web_search": _float_or_none(row.get("web_search_latency_ms")),
        "llm": _float_or_none(row.get("llm_latency_ms")),
        "report": _float_or_none(row.get("report_latency_ms")),
        "db_save": _float_or_none(row.get("db_save_latency_ms")),
    }
    stage_latency = {
        key: value for key, value in stage_latency.items() if value is not None and value >= 0
    }

    prediction = {
        "risk_level": str(row.get("predicted_label") or "").strip(),
        "final_score": _float_or_none(row.get("final_score")),
        "evidence_list": [
            {"evidence_id": evidence_id, "source": "captured_csv"}
            for evidence_id in effective_ids
        ],
        "candidate_evidence_list": [
            {"evidence_id": evidence_id, "source": "captured_csv"}
            for evidence_id in retrieved_ids
        ],
        "assessment_status": str(row.get("assessment_status") or ("legacy" if success else "failed")),
        "arbitration_status": str(row.get("arbitration_status") or ("unknown" if success else row.get("error_type") or "failed")),
        "quality_status": str(row.get("quality_status") or ("unknown" if success else "failed")),
        "total_latency_ms": _float_or_none(row.get("total_latency_ms")),
        "stage_latency_ms": stage_latency,
    }
    if row.get("error_message"):
        prediction["error_message"] = row["error_message"]

    return {
        "case_id": sample_id,
        "gold_eligible": _truthy(row.get("gold_eligible")),
        "expected": {
            "risk_level": str(row.get("gold_label") or "").strip() if _truthy(row.get("gold_eligible")) else "",
            "relevant_evidence_ids": relevant_ids,
        },
        "prediction": prediction,
    }


def _split_ids(value: Any) -> list[str]:
    if value is None:
        return []
    if isinstance(value, str):
        parts = value.split(",")
    elif isinstance(value, list):
        parts = value
    else:
        parts = [value]
    return [str(part).strip() for part in parts if str(part).strip()]


def _truthy(value: Any) -> bool:
    if isinstance(value, bool):
        return value
    if value is None:
        return False
    return str(value).strip().lower() in {"true", "1", "yes"}


def _float_or_none(value: Any) -> float | None:
    if value is None or value == "":
        return None
    try:
        return float(value)
    except (TypeError, ValueError):
        return None


def _int_or_zero(value: Any) -> int:
    try:
        return max(0, int(float(value)))
    except (TypeError, ValueError):
        return 0


if __name__ == "__main__":
    raise SystemExit(main())
