#!/usr/bin/env python3
"""Reproducible offline evaluation for the News Credibility Evaluator.

Usage (from project root)::

    python -m evaluation.run_evaluation \\
        --dataset evaluation/datasets/news_eval_demo.csv \\
        --output-dir evaluation/output \\
        --sample-limit 3 \\
        --allow-web-search false \\
        --retries 1 \\
        --interval 0.5 \\
        --seed 42

Or from the backend directory::

    cd backend
    python -m evaluation.run_evaluation \\
        --dataset ../evaluation/datasets/news_eval_demo.csv \\
        --output-dir ../evaluation/output \\
        --sample-limit 3

The script calls ``detect_news_credibility`` directly (service layer) and
records per‑sample timing, evidence, and outcome data.  It is designed to
be **non‑invasive**: it does not modify any scoring formula, prompt, retrieval
threshold, risk‑classification rule, or web‑search trigger threshold.
"""

from __future__ import annotations

import argparse
import csv
import hashlib
import json
import logging
import os
import random
import sys
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any


# ---------------------------------------------------------------------------
# path setup — ensure backend and evaluation packages are importable
# ---------------------------------------------------------------------------
_HERE = Path(__file__).resolve().parent          # evaluation/
_PROJECT_ROOT = _HERE.parent                     # project root
_BACKEND = _PROJECT_ROOT / "backend"             # backend/
for _p in (str(_PROJECT_ROOT), str(_BACKEND)):
    if _p not in sys.path:
        sys.path.insert(0, _p)

# Confirm the evaluation package itself is importable
try:
    import evaluation  # noqa: F401
except ImportError:
    # Running from a directory where evaluation/ is not on path
    if str(_PROJECT_ROOT) not in sys.path:
        sys.path.insert(0, str(_PROJECT_ROOT))

# ---------------------------------------------------------------------------
# imports from the evaluation package
# ---------------------------------------------------------------------------
from evaluation.metrics import compute_all_metrics
from evaluation.dataset_quality import audit_dataset, gold_issues, verify_manifest
from evaluation.report import (
    compute_file_hash,
    generate_evaluation_report_md,
    generate_metrics_json,
    generate_run_metadata,
)

logger = logging.getLogger(__name__)


# ═══════════════════════════════════════════════════════════════════════════
# CLI
# ═══════════════════════════════════════════════════════════════════════════

def parse_args(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="News Credibility Evaluator — reproducible offline evaluation",
    )
    parser.add_argument(
        "--dataset", required=True,
        help="Path to CSV or JSONL evaluation dataset.",
    )
    parser.add_argument(
        "--output-dir", default="./evaluation/output",
        help="Directory for per-case results, metrics, and reports.",
    )
    parser.add_argument(
        "--sample-limit", type=int, default=0,
        help="Max samples to evaluate (0 = unlimited).",
    )
    parser.add_argument(
        "--allow-web-search", default=None,
        help="Force web search on/off for ALL samples (true/false). "
             "When omitted, per-sample allow_web_search column is respected.",
    )
    parser.add_argument(
        "--retries", type=int, default=1,
        help="Max retries per sample on failure (default: 1, i.e. 2 total attempts).",
    )
    parser.add_argument(
        "--interval", type=float, default=0.5,
        help="Minimum seconds between samples to avoid rate limiting (default: 0.5).",
    )
    parser.add_argument(
        "--seed", type=int, default=42,
        help="Fixed random seed for reproducibility (default: 42).",
    )
    parser.add_argument(
        "--resume", action="store_true",
        help="Resume from last checkpoint — skip already-completed samples.",
    )
    parser.add_argument(
        "--log-level", default="INFO",
        choices=["DEBUG", "INFO", "WARNING", "ERROR"],
        help="Logging level (default: INFO).",
    )
    parser.add_argument("--research-only", action="store_true",
                        help="Permit non-gold diagnostic data; do not publish classification effectiveness.")
    parser.add_argument("--manifest", default=None,
                        help="Frozen manifest to verify (auto-detect sibling frozen_manifest.json).")
    return parser.parse_args(argv)


# ═══════════════════════════════════════════════════════════════════════════
# dataset loading
# ═══════════════════════════════════════════════════════════════════════════

def load_dataset(path: str | Path) -> list[dict[str, Any]]:
    """Load evaluation samples from a CSV or JSONL file.

    - Lines starting with ``#`` in CSV are treated as comments and skipped.
    - Duplicate ``sample_id`` values are reported and skipped.
    - Returns a list of row dicts.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(f"Dataset not found: {path}")

    suffix = path.suffix.lower()
    if suffix == ".csv":
        return _load_csv(path)
    if suffix in (".jsonl", ".json"):
        return _load_jsonl(path)

    raise ValueError(f"Unsupported dataset format: {suffix}. Use .csv or .jsonl.")


def _load_csv(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with open(path, "r", encoding="utf-8-sig") as f:
        # Skip BOM and comment lines, then parse header
        reader = csv.reader(f)
        header: list[str] = []
        for raw_line in reader:
            line = raw_line
            if not line or (len(line) == 1 and not line[0].strip()):
                continue
            if line[0].strip().startswith("#"):
                continue
            header = [h.strip() for h in line]
            break

        if not header:
            raise ValueError(f"CSV file {path} has no header row after skipping comments.")

        for raw_line in reader:
            line = [cell.strip() for cell in raw_line]
            if not line or all(not cell for cell in line):
                continue
            if line[0].startswith("#"):
                continue

            row = dict(zip(header, line))
            sid = row.get("sample_id", "").strip()
            if not sid:
                logger.warning("Skipping row with empty sample_id")
                continue
            if sid in seen_ids:
                logger.warning("Duplicate sample_id %r — skipping", sid)
                continue
            seen_ids.add(sid)
            rows.append(row)

    logger.info("Loaded %d samples from %s", len(rows), path)
    return rows


def _load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows: list[dict[str, Any]] = []
    seen_ids: set[str] = set()

    with open(path, "r", encoding="utf-8") as f:
        for line_num, line in enumerate(f, start=1):
            line = line.strip()
            if not line or line.startswith("#"):
                continue
            try:
                obj = json.loads(line)
            except json.JSONDecodeError as exc:
                logger.warning("Skipping invalid JSONL line %d: %s", line_num, exc)
                continue
            sid = str(obj.get("sample_id", "")).strip()
            if not sid:
                logger.warning("Skipping JSONL line %d with empty sample_id", line_num)
                continue
            if sid in seen_ids:
                logger.warning("Duplicate sample_id %r at line %d — skipping", sid, line_num)
                continue
            seen_ids.add(sid)
            rows.append(obj)

    logger.info("Loaded %d samples from %s", len(rows), path)
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# checkpoint / resume
# ═══════════════════════════════════════════════════════════════════════════

CHECKPOINT_FILENAME = "_checkpoint.json"


def load_checkpoint(output_dir: Path) -> set[str]:
    """Return the set of sample_ids that have already been processed."""
    checkpoint_path = output_dir / CHECKPOINT_FILENAME
    if not checkpoint_path.exists():
        return set()
    try:
        with open(checkpoint_path, "r", encoding="utf-8") as f:
            data = json.load(f)
        return set(data.get("completed_ids", []))
    except (json.JSONDecodeError, KeyError) as exc:
        logger.warning("Corrupt checkpoint file, starting fresh: %s", exc)
        return set()


def save_checkpoint(output_dir: Path, completed_ids: set[str]) -> None:
    """Persist the set of completed sample_ids."""
    output_dir.mkdir(parents=True, exist_ok=True)
    checkpoint_path = output_dir / CHECKPOINT_FILENAME
    with open(checkpoint_path, "w", encoding="utf-8") as f:
        json.dump({"completed_ids": sorted(completed_ids)}, f, ensure_ascii=False)


def bind_run_context(output_dir: Path, context: dict[str, Any], *, resume: bool) -> None:
    """Prevent joining old outputs across dataset/config changes or repeated runs."""
    path = output_dir / "_run_context.json"
    serialized = json.dumps(context, ensure_ascii=False, sort_keys=True)
    fingerprint = hashlib.sha256(serialized.encode("utf-8")).hexdigest()
    has_results = per_case_file_path(output_dir).exists() or (output_dir / CHECKPOINT_FILENAME).exists()
    if has_results:
        if not resume:
            raise ValueError("Output already contains results; choose a new directory or --resume.")
        if not path.exists() or json.loads(path.read_text(encoding="utf-8")).get("fingerprint") != fingerprint:
            raise ValueError("Resume dataset/config fingerprint does not match; choose a new output directory.")
    path.write_text(json.dumps({"fingerprint": fingerprint, "context": context}, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


# ═══════════════════════════════════════════════════════════════════════════
# per-case results
# ═══════════════════════════════════════════════════════════════════════════

PER_CASE_HEADER = [
    "sample_id",
    "gold_label",
    "predicted_label",
    "final_score",
    "success",
    "assessment_status",
    "assessment_reason",
    "arbitration_status",
    "quality_status",
    "gold_eligible",
    "human_review_status",
    "error_type",
    "total_latency_ms",
    "parse_latency_ms",
    "local_retrieval_latency_ms",
    "web_search_latency_ms",
    "llm_latency_ms",
    "report_latency_ms",
    "db_save_latency_ms",
    "web_search_allowed",
    "web_search_triggered",
    "web_trigger_reason",
    "local_candidate_count",
    "top_similarity",
    "retrieved_knowledge_ids",
    "retrieved_chunk_ids",
    "retrieval_version",
    "index_version",
    "candidate_parent_count",
    "candidate_chunk_count",
    "evidence_count",
    "effective_evidence_ids",
    "valid_evidence_count",
    "citation_fields_complete",
    "llm_parse_fallback_used",
    "created_at",
    # ── extras from dataset for traceability ──
    "is_demo",
    "relevant_knowledge_ids",
    "relevant_chunk_ids",
    "reviewer_1_label",
    "reviewer_2_label",
    # ── additional stability fields ──
    "is_timeout",
    "embedding_failed",
    "chroma_failed",
    "web_search_failed",
    "save_failed",
    "evidence_has_valid_url",
    "has_evidence_insufficient_hint",
    # ── error detail (sanitized) ──
    "error_message",
]


def _sanitize_error(exc: Exception) -> str:
    """Return a sanitized error message — never include API keys or tokens."""
    msg = str(exc)[:500]
    # Redact anything that looks like an API key pattern
    import re
    msg = re.sub(r'sk-[A-Za-z0-9_-]{20,}', '[REDACTED]', msg)
    msg = re.sub(r'Bearer\s+[A-Za-z0-9_\-\.]{20,}', 'Bearer [REDACTED]', msg)
    msg = re.sub(r'api_key[=:]\s*[^\s&]{10,}', 'api_key=[REDACTED]', msg, flags=re.IGNORECASE)
    return msg


def per_case_file_path(output_dir: Path) -> Path:
    return output_dir / "per_case_results.csv"


def _init_per_case_csv(path: Path) -> None:
    """Write the CSV header if the file doesn't exist."""
    if path.exists():
        return
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow(PER_CASE_HEADER)


def append_per_case_row(output_dir: Path, row: dict[str, Any]) -> None:
    """Append a single result row to the per-case CSV."""
    path = per_case_file_path(output_dir)
    _init_per_case_csv(path)
    with open(path, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        writer.writerow([row.get(key, "") for key in PER_CASE_HEADER])


# Columns that store boolean values — must be coerced from CSV strings.
_BOOL_COLUMNS = frozenset({
    "success", "gold_eligible", "web_search_allowed", "web_search_triggered",
    "citation_fields_complete", "llm_parse_fallback_used",
    "is_demo", "is_timeout", "embedding_failed", "chroma_failed",
    "web_search_failed", "save_failed", "evidence_has_valid_url",
    "has_evidence_insufficient_hint",
})

# Columns that store numeric values — coerced to float ("" stays as None).
_NUMERIC_COLUMNS = frozenset({
    "total_latency_ms", "parse_latency_ms", "local_retrieval_latency_ms",
    "web_search_latency_ms", "llm_latency_ms", "report_latency_ms", "db_save_latency_ms",
    "final_score", "top_similarity",
})


def _coerce_bool(value: str) -> bool:
    return value.strip().lower() in ("true", "1", "yes")


def _coerce_numeric(value: str) -> float | None:
    v = value.strip()
    if not v or v == "":
        return None
    try:
        return float(v)
    except ValueError:
        return None


def read_per_case_results(output_dir: Path) -> list[dict[str, Any]]:
    """Read all rows from per_case_results.csv, coercing boolean & numeric columns."""
    path = per_case_file_path(output_dir)
    if not path.exists():
        return []
    rows: list[dict[str, Any]] = []
    with open(path, "r", encoding="utf-8-sig") as f:
        reader = csv.DictReader(f)
        for row in reader:
            # Coerce booleans
            for col in _BOOL_COLUMNS:
                if col in row:
                    row[col] = _coerce_bool(row[col])
            # Coerce numerics (keep None for empty cells)
            for col in _NUMERIC_COLUMNS:
                if col in row:
                    val = _coerce_numeric(row[col])
                    if val is not None:
                        row[col] = val
            # Coerce integer fields from CSV
            for col in (
                "evidence_count",
                "valid_evidence_count",
                "local_candidate_count",
                "candidate_parent_count",
                "candidate_chunk_count",
            ):
                if col in row:
                    try:
                        row[col] = int(row[col])
                    except (ValueError, TypeError):
                        row[col] = 0
            rows.append(row)
    return rows


# ═══════════════════════════════════════════════════════════════════════════
# detection wrapper
# ═══════════════════════════════════════════════════════════════════════════

def _is_demo(sample_id: str) -> bool:
    return str(sample_id).upper().startswith("DEMO")


# ── Label normalization — maps external dataset labels to system-internal ──
# The detection system outputs four standard risk levels. Third-party
# evaluation datasets may use different naming conventions. This mapping
# is applied ONLY to gold_label at read time; predicted_label comes from
# the system directly and always uses the canonical form.
GOLD_LABEL_NORMALIZATION: dict[str, str] = {
    # CFEVER-like labels
    "可信": "可信新闻",
    "存疑": "存疑信息",
    "高风险": "高风险谣言",
    "谣言": "疑似谣言",
    # Already canonical → pass through
    "可信新闻": "可信新闻",
    "存疑信息": "存疑信息",
    "疑似谣言": "疑似谣言",
    "高风险谣言": "高风险谣言",
}

SYSTEM_LABELS = frozenset({"可信新闻", "存疑信息", "疑似谣言", "高风险谣言"})


def _normalize_gold_label(raw: str) -> str:
    """Normalize an external gold_label to the canonical system label.

    Returns the canonical label, or the original stripped string if no
    mapping is known (which will then fail the ``in SYSTEM_LABELS`` check
    in metric functions).
    """
    cleaned = str(raw).strip()
    return GOLD_LABEL_NORMALIZATION.get(cleaned, cleaned)


def _normalize_reviewer_label(raw: str) -> str:
    """Normalize reviewer labels using the same mapping as gold labels."""
    return _normalize_gold_label(raw)


# ── EVAL-KB → MySQL ID mapping ──────────────────────────────────────────
# Resolves evaluation knowledge-base identifiers (EVAL-KB-0001 etc.) to
# actual auto-increment MySQL IDs so that Hit@K / Recall@K can compare
# retrieved_knowledge_ids (integers) against human-annotated relevant items.
_EVAL_KB_ID_MAP: dict[str, str] = {}

def _load_eval_kb_id_map(db: Any) -> None:
    """Populate ``_EVAL_KB_ID_MAP`` from MySQL knowledge_items.admin_note."""
    global _EVAL_KB_ID_MAP
    if _EVAL_KB_ID_MAP:
        return
    try:
        from app.models.knowledge_item import KnowledgeItem
        import re
        items = db.query(KnowledgeItem).filter(
            KnowledgeItem.admin_note.like('%[EVAL-KB-%')
        ).all()
        for item in items:
            note = item.admin_note or ""
            m = re.search(r'\[EVAL-KB-([^\]]+)\]', note)
            if m:
                _EVAL_KB_ID_MAP[m.group(1)] = str(item.id)
    except Exception:
        pass  # DB not available during unit tests


def _resolve_relevant_knowledge_ids(raw: str) -> str:
    """Convert EVAL-KB-XXXX to MySQL integer IDs, keeping integers as-is."""
    if not raw or not raw.strip():
        return ""
    parts = [p.strip() for p in str(raw).split(",") if p.strip()]
    resolved: list[str] = []
    for p in parts:
        upper = p.upper()
        if upper in _EVAL_KB_ID_MAP:
            resolved.append(_EVAL_KB_ID_MAP[upper])
        elif p.isdigit():
            resolved.append(p)
        # Non-integer, non-EVAL-KB values are silently dropped
    return ",".join(resolved)


def _parse_allow_web_search(row: dict[str, Any], global_override: bool | None) -> bool:
    """Determine whether web search is allowed for this sample."""
    if global_override is not None:
        return global_override
    raw = row.get("allow_web_search", "true")
    if isinstance(raw, bool):
        return raw
    return str(raw).strip().lower() in ("true", "1", "yes")


def _parse_relevant_knowledge_ids(row: dict[str, Any]) -> str:
    """Normalize relevant_knowledge_ids — resolves EVAL-KB-XXXX to MySQL IDs."""
    raw = row.get("relevant_knowledge_ids", "")
    if raw is None:
        return ""
    if isinstance(raw, list):
        raw = ",".join(str(x) for x in raw)
    return _resolve_relevant_knowledge_ids(str(raw).strip())


def _parse_relevant_chunk_ids(row: dict[str, Any]) -> str:
    """Normalize relevant_chunk_ids while preserving stable chunk string IDs."""
    raw = row.get("relevant_chunk_ids", "")
    if raw is None:
        return ""
    if isinstance(raw, list):
        return ",".join(str(x).strip() for x in raw if str(x).strip())
    return str(raw).strip()


def _load_detection_runtime() -> tuple[Any, Any, Any, Any]:
    """Lazy dependency boundary; unit tests need no real backend import state."""
    from app.schemas.detection import DetectNewsRequest
    from app.services.detection_service import (
        DetectionServiceError, KnowledgeRetrievalFailedError, detect_news_credibility,
    )
    return DetectNewsRequest, DetectionServiceError, KnowledgeRetrievalFailedError, detect_news_credibility


def run_single_detection(
    db: Any,
    row: dict[str, Any],
    allow_web_search_global: bool | None,
    retries: int,
) -> dict[str, Any]:
    """Run ``detect_news_credibility`` for one sample and return a per-case dict.

    The result dict is **sensitive-information-free** — no API keys, tokens, or
    full user data appear in its values.
    """
    DetectNewsRequest, DetectionServiceError, KnowledgeRetrievalFailedError, detect_news_credibility = _load_detection_runtime()

    sample_id = str(row.get("sample_id", "")).strip()
    title = str(row.get("title", "")).strip()
    content = str(row.get("content", "")).strip()
    source_url = str(row.get("url", "")).strip() or None
    allow_web = _parse_allow_web_search(row, allow_web_search_global)

    base_result: dict[str, Any] = {
        "sample_id": sample_id,
        "gold_label": _normalize_gold_label(row.get("gold_label", "")),
        "is_demo": _is_demo(sample_id),
        "relevant_knowledge_ids": _parse_relevant_knowledge_ids(row),
        "relevant_chunk_ids": _parse_relevant_chunk_ids(row),
        "reviewer_1_label": _normalize_reviewer_label(row.get("reviewer_1_label", "")),
        "reviewer_2_label": _normalize_reviewer_label(row.get("reviewer_2_label", "")),
        "web_search_allowed": allow_web,
        # defaults (will be overwritten on success)
        "predicted_label": "",
        "final_score": "",
        "success": False,
        "assessment_status": "failed",
        "assessment_reason": "",
        "arbitration_status": "unknown",
        "quality_status": "unknown",
        "gold_eligible": not gold_issues(row),
        "human_review_status": row.get("human_review_status", "unverified"),
        "error_type": "",
        "error_message": "",
        "total_latency_ms": "",
        "parse_latency_ms": "",
        "local_retrieval_latency_ms": "",
        "web_search_latency_ms": "",
        "llm_latency_ms": "",
        "report_latency_ms": "",
        "db_save_latency_ms": "",
        "web_search_triggered": False,
        "web_trigger_reason": "",
        "local_candidate_count": "",
        "top_similarity": "",
        "retrieved_knowledge_ids": "",
        "retrieved_chunk_ids": "",
        "retrieval_version": "",
        "index_version": "",
        "candidate_parent_count": "",
        "candidate_chunk_count": "",
        "evidence_count": "",
        "valid_evidence_count": "",
        "citation_fields_complete": False,
        "llm_parse_fallback_used": False,
        "created_at": "",
        "is_timeout": False,
        "embedding_failed": False,
        "chroma_failed": False,
        "web_search_failed": False,
        "save_failed": False,
        "evidence_has_valid_url": False,
        "has_evidence_insufficient_hint": False,
    }

    if not title or not content:
        base_result["error_type"] = "invalid_input"
        base_result["error_message"] = "Missing title or content"
        return base_result

    if len(title) < 4:
        base_result["error_type"] = "title_too_short"
        base_result["error_message"] = f"Title too short: {len(title)} chars (min 4)"
        return base_result
    if len(content) < 20:
        base_result["error_type"] = "content_too_short"
        base_result["error_message"] = f"Content too short: {len(content)} chars (min 20)"
        return base_result
        return base_result

    last_exception: Exception | None = None

    for attempt in range(retries + 1):
        try:
            t_start = time.perf_counter()

            payload = DetectNewsRequest(
                title=title,
                content=content,
                source_url=source_url,
                enable_web_search=allow_web,
            )

            # ── actual detection call ──
            result = detect_news_credibility(
                db=db,
                payload=payload,
                current_user=None,
            )

            t_end = time.perf_counter()
            total_ms = round((t_end - t_start) * 1000, 2)

            # ── populate result fields ──
            base_result["success"] = True
            base_result["assessment_status"] = result.get("assessment_status", "legacy")
            base_result["assessment_reason"] = result.get("assessment_reason", "")
            base_result["total_latency_ms"] = total_ms
            base_result["predicted_label"] = str(result.get("risk_level", ""))
            base_result["final_score"] = result.get("final_score")

            # Per-stage latencies — our current detection_service doesn't
            # expose them individually, so we record what we can.
            # total_latency_ms is the full wall-clock time.
            # Individual stage latencies are set to "" when unavailable;
            # this is explicitly documented in the output and report.
            stage_latency = result.get("stage_latency_ms") or {}
            base_result["parse_latency_ms"] = stage_latency.get("extract_keywords", "")
            base_result["local_retrieval_latency_ms"] = stage_latency.get("rag_search", "")
            base_result["web_search_latency_ms"] = stage_latency.get("web_search", "")
            base_result["llm_latency_ms"] = stage_latency.get("llm_analysis", "")
            base_result["db_save_latency_ms"] = stage_latency.get("db_save", "")
            base_result["report_latency_ms"] = stage_latency.get("report_generation", "")

            # Web search
            base_result["web_search_triggered"] = bool(result.get("web_search_triggered", False))
            base_result["web_trigger_reason"] = ""  # detection_service doesn't expose reason

            # Evidence from candidate list
            candidates = result.get("candidate_evidence_list") or []
            base_result["local_candidate_count"] = sum(
                1 for c in candidates if c.get("source_type") == "knowledge_base"
            )

            # Top similarity
            similarities = [
                (c.get("similarity_score") or 0)
                for c in candidates
            ]
            base_result["top_similarity"] = round(max(similarities), 4) if similarities else ""

            # Retrieved knowledge IDs
            retrieved_ids = [
                str(c["knowledge_id"])
                for c in candidates
                if c.get("knowledge_id") is not None
            ]
            base_result["retrieved_knowledge_ids"] = ",".join(retrieved_ids)

            retrieved_chunk_ids: list[str] = []
            for candidate in candidates:
                for chunk in candidate.get("chunks") or []:
                    chunk_id = chunk.get("chunk_id")
                    if chunk_id:
                        retrieved_chunk_ids.append(str(chunk_id))
            base_result["retrieved_chunk_ids"] = ",".join(retrieved_chunk_ids)
            base_result["retrieval_version"] = result.get("retrieval_version", "")
            base_result["index_version"] = result.get("index_version", "")
            base_result["candidate_parent_count"] = result.get(
                "candidate_parent_count",
                len({rid for rid in retrieved_ids if rid}),
            )
            base_result["candidate_chunk_count"] = result.get(
                "candidate_chunk_count",
                len(retrieved_chunk_ids),
            )

            # Effective evidence (post-arbitration)
            effective = result.get("evidence_list") or []
            base_result["evidence_count"] = len(effective)
            base_result["valid_evidence_count"] = len(effective)
            base_result["effective_evidence_ids"] = ",".join(
                str(e.get("knowledge_id") or e.get("candidate_id") or e.get("source_url") or "")
                for e in effective if e.get("knowledge_id") or e.get("candidate_id") or e.get("source_url")
            )

            # Citation fields complete: check title + summary
            fields_ok = all(
                e.get("title") and e.get("summary")
                for e in effective
            ) if effective else False
            base_result["citation_fields_complete"] = fields_ok

            # Evidence has valid URL
            base_result["evidence_has_valid_url"] = any(
                isinstance(e.get("source_url"), str) and e["source_url"].strip()
                for e in effective
            )

            # Evidence insufficient hint
            reason = str(result.get("reason", ""))
            base_result["has_evidence_insufficient_hint"] = (
                "证据不足" in reason
                or "未检索到相关证据" in reason
                or "没有找到相关" in reason
                or "暂无相关证据" in reason
            )

            # LLM parse fallback
            analysis_payload = result.get("analysis_payload") or {}
            arbitration_status = (
                result.get("arbitration_status")
                or analysis_payload.get("arbitration_status", "")
            )
            base_result["arbitration_status"] = arbitration_status or "unknown"
            quality = result.get("evidence_quality") or analysis_payload.get("evidence_quality") or {}
            base_result["quality_status"] = result.get("quality_status") or quality.get("status", "unknown")
            base_result["llm_parse_fallback_used"] = (
                str(arbitration_status) == "unavailable"
                and not result.get("evidence_quality")
            )

            base_result["created_at"] = datetime.now(timezone.utc).isoformat()

            # Stability flags
            base_result["is_timeout"] = False
            base_result["embedding_failed"] = False
            base_result["chroma_failed"] = False
            base_result["web_search_failed"] = False
            base_result["save_failed"] = False

            return base_result

        except KnowledgeRetrievalFailedError as exc:
            last_exception = exc
            base_result["error_type"] = "knowledge_retrieval_failed"
            base_result["chroma_failed"] = True
            logger.warning("[%s] Knowledge retrieval failed (attempt %d/%d)", sample_id, attempt + 1, retries + 1)

        except DetectionServiceError as exc:
            last_exception = exc
            base_result["error_type"] = "detection_service_error"
            logger.warning("[%s] Detection service error (attempt %d/%d): %s",
                           sample_id, attempt + 1, retries + 1, _sanitize_error(exc))

        except Exception as exc:
            last_exception = exc
            error_msg = str(exc).lower()
            if "timeout" in error_msg or "timed out" in error_msg:
                base_result["error_type"] = "timeout"
                base_result["is_timeout"] = True
            elif "embedding" in error_msg or "vector" in error_msg:
                base_result["error_type"] = "embedding_failed"
                base_result["embedding_failed"] = True
            elif "chroma" in error_msg:
                base_result["error_type"] = "chroma_failed"
                base_result["chroma_failed"] = True
            elif "bocha" in error_msg.lower() or "web search" in error_msg.lower():
                base_result["error_type"] = "web_search_failed"
                base_result["web_search_failed"] = True
            elif "database" in error_msg or "sql" in error_msg:
                base_result["error_type"] = "save_failed"
                base_result["save_failed"] = True
            else:
                base_result["error_type"] = type(exc).__name__
            logger.warning("[%s] %s (attempt %d/%d): %s",
                           sample_id, type(exc).__name__,
                           attempt + 1, retries + 1, _sanitize_error(exc))

        # Wait before retry
        if attempt < retries:
            time.sleep(1.0)

    # All retries exhausted
    base_result["success"] = False
    base_result["error_message"] = _sanitize_error(last_exception) if last_exception else "unknown"
    base_result["created_at"] = datetime.now(timezone.utc).isoformat()
    return base_result


# ═══════════════════════════════════════════════════════════════════════════
# main runner
# ═══════════════════════════════════════════════════════════════════════════

def run_evaluation(args: argparse.Namespace) -> int:
    """Execute the full evaluation pipeline."""
    # Setup
    random.seed(args.seed)
    logging.basicConfig(
        level=getattr(logging, args.log_level),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
        datefmt="%Y-%m-%d %H:%M:%S",
    )

    output_dir = Path(args.output_dir).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)
    dataset_path = Path(args.dataset).resolve()

    logger.info("=" * 60)
    logger.info("News Credibility Evaluator — Offline Evaluation")
    logger.info("  Dataset:   %s", dataset_path)
    logger.info("  Output:    %s", output_dir)
    logger.info("  Seed:      %d", args.seed)
    logger.info("=" * 60)

    # ── Load dataset ──
    rows = load_dataset(dataset_path)
    if not rows:
        logger.error("Dataset is empty — nothing to evaluate.")
        return 1

    manifest_path = Path(args.manifest) if getattr(args, "manifest", None) else dataset_path.parent / "frozen_manifest.json"
    integrity_verified = False
    if manifest_path.exists():
        try:
            manifest = verify_manifest(manifest_path)
            integrity_verified = any((manifest_path.parent / relative).resolve() == dataset_path
                                     for relative in manifest["files"])
            if getattr(args, "manifest", None) and not integrity_verified:
                raise ValueError("Selected dataset is not covered by the supplied manifest")
        except ValueError as exc:
            logger.error("Dataset integrity check failed: %s", exc)
            return 2
    quality_audit = audit_dataset(rows)
    quality_audit["integrity_verified"] = integrity_verified
    quality_audit["publication_eligible"] = quality_audit["publication_eligible"] and integrity_verified
    (output_dir / "dataset_quality.json").write_text(json.dumps(quality_audit, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    # Fail before loading credentials, providers or database connections.
    if not quality_audit["publication_eligible"] and not getattr(args, "research_only", False):
        logger.error("Dataset is not four-level gold. Complete independent adjudication or use --research-only for non-publication diagnostics.")
        return 2
    if quality_audit["leakage_count"]:
        logger.error("Model-visible target leakage detected; even research execution is rejected. Use quarantined data only in leakage-detector tests.")
        return 2

    # Apply sample limit
    if args.sample_limit and args.sample_limit > 0:
        rows = rows[: args.sample_limit]
        logger.info("Sample limit applied: %d samples.", len(rows))

    # ── Resolve web search override ──
    allow_web_global: bool | None = None
    if args.allow_web_search is not None:
        allow_web_global = args.allow_web_search.strip().lower() in ("true", "1", "yes")
        logger.info("Global web search override: %s", allow_web_global)

    # ── Resume support ──
    completed_ids: set[str] = set()
    if args.resume:
        completed_ids = load_checkpoint(output_dir)
        if completed_ids:
            logger.info("Resume mode: %d sample(s) already completed, will skip.", len(completed_ids))

    # ── Gather config for metadata ──
    from app.core.config import get_settings
    from app.services.llm_service import _load_deepseek_config
    from app.services.web.web_search_service import (
        RAG_TOP1_THRESHOLD,
        RAG_TOP1_MODERATE,
        RAG_MIN_MEANINGFUL_RESULTS,
    )

    settings = get_settings()
    llm_config = _load_deepseek_config()

    config_info = {
        "model_name": llm_config.get("model", "unknown"),
        "embedding_provider": settings.embedding_provider,
        "embedding_model": (
            settings.dashscope_embedding_model
            if settings.embedding_provider == "dashscope"
            else settings.deepseek_embedding_model
        ),
        "top_k_rag": 10,
        "rag_top1_threshold": RAG_TOP1_THRESHOLD,
        "rag_top1_moderate": RAG_TOP1_MODERATE,
        "rag_min_meaningful": RAG_MIN_MEANINGFUL_RESULTS,
        "scoring_formula": (
            "completed: llm_score×0.5 + evidence_quality_score×0.3 + rule_score×0.2; "
            "insufficient_evidence/degraded: final_score=null, risk_level=无法判断"
        ),
        "dataset_publication_eligible": quality_audit["publication_eligible"],
        "research_only": bool(getattr(args, "research_only", False)),
    }

    dataset_hash = compute_file_hash(dataset_path)
    try:
        bind_run_context(output_dir, {"dataset_hash": dataset_hash, "config": config_info,
                                     "allow_web_search": allow_web_global, "seed": args.seed,
                                     "sample_limit": args.sample_limit, "commit": _get_commit_hash()}, resume=args.resume)
    except ValueError as exc:
        logger.error("Unsafe result reuse refused: %s", exc)
        return 2

    # ── Initialize DB session ──
    from app.db.session import SessionLocal
    db = SessionLocal()
    _load_eval_kb_id_map(db)

    try:
        # ── Main evaluation loop ──
        total = len(rows)
        processed = 0
        for idx, row in enumerate(rows, start=1):
            sample_id = str(row.get("sample_id", "")).strip()

            # Skip already-completed in resume mode
            if sample_id and sample_id in completed_ids:
                logger.info("[%d/%d] %s — already completed, skipping.", idx, total, sample_id)
                continue

            logger.info("[%d/%d] Evaluating %s ...", idx, total, sample_id)

            # Run detection
            case_result = run_single_detection(
                db=db,
                row=row,
                allow_web_search_global=allow_web_global,
                retries=args.retries,
            )

            # Immediately flush to disk
            append_per_case_row(output_dir, case_result)
            completed_ids.add(sample_id)
            save_checkpoint(output_dir, completed_ids)

            status = "OK" if case_result["success"] else f"FAIL ({case_result.get('error_type', 'unknown')})"
            logger.info("[%d/%d] %s — %s (%.0f ms)", idx, total, sample_id, status,
                        float(case_result.get("total_latency_ms") or 0))
            processed += 1

            # Respect interval
            if idx < total:
                time.sleep(args.interval)

        logger.info("Evaluation complete: %d sample(s) processed.", processed)

        # ── Load all results for metrics ──
        all_results = read_per_case_results(output_dir)
        logger.info("Loaded %d per-case results for metrics computation.", len(all_results))

        # ── Compute metrics ──
        metrics = compute_all_metrics(all_results)
        generate_metrics_json(output_dir, metrics)
        logger.info("Metrics written to %s", output_dir / "metrics.json")

        # ── Generate metadata ──
        run_metadata = generate_run_metadata(
            output_dir=output_dir,
            dataset_path=dataset_path,
            run_args={
                "commit_hash": _get_commit_hash(),
                "dataset_hash": dataset_hash,
                "allow_web_search": allow_web_global,
                "sample_limit": args.sample_limit if args.sample_limit else None,
                "command": " ".join(sys.argv),
            },
            config_info=config_info,
        )
        logger.info("Metadata written to %s", output_dir / "run_metadata.json")

        # ── Generate report ──
        report = generate_evaluation_report_md(output_dir, metrics, run_metadata)
        logger.info("Report written to %s", output_dir / "evaluation_report.md")

        # ── Print summary ──
        sc = metrics.get("sample_counts", {})
        print("\n" + "=" * 60)
        print("Evaluation Summary")
        print("=" * 60)
        print(f"  Total samples:     {sc.get('total_samples', 0)}")
        print(f"  Valid (excl demo): {sc.get('valid_samples', 0)}")
        print(f"  Successful:        {sc.get('success_count', 0)}")
        print(f"  Failed:            {sc.get('failure_count', 0)}")
        clf = metrics.get("classification", {})
        if clf.get("accuracy") is not None:
            print(f"  Accuracy:          {clf['accuracy']}")
            print(f"  Macro F1:          {clf.get('macro_f1', '-')}")
        print(f"  Output:            {output_dir}")
        print("=" * 60)

    finally:
        db.close()

    return 0


def _get_commit_hash() -> str:
    """Try to get the current git commit hash."""
    import subprocess
    try:
        result = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            capture_output=True, text=True, timeout=5,
            cwd=str(_BACKEND.parent),
        )
        if result.returncode == 0:
            return result.stdout.strip()
    except Exception:
        pass
    return "unknown"


# ═══════════════════════════════════════════════════════════════════════════
# entry point
# ═══════════════════════════════════════════════════════════════════════════

if __name__ == "__main__":
    sys.exit(run_evaluation(parse_args()))
