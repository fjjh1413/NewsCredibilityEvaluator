"""Build a deterministic, unmapped CFEVER subset from the pinned official file.

No model, fabricated news paragraph or generated reference judgment is involved.
The corpus contains *page titles only*, not Wikipedia article bodies.
"""
from __future__ import annotations

import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1] / "datasets"
COMMIT = "01395ed4a7ab125c3e131c97d33d188159d9a1da"
UPSTREAM = f"https://raw.githubusercontent.com/IKMLab/CFEVER-data/{COMMIT}/data/dev.jsonl"
UPSTREAM_SHA256 = "05f310633b2f1365444a9ef59a423b03d96bddb7591d4a1ccb054759fc2db98e"


def sha(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def pages(row: dict) -> list[str]:
    values: set[str] = set()
    def visit(value):
        if isinstance(value, list):
            if len(value) == 4 and isinstance(value[2], str) and isinstance(value[3], int):
                values.add(value[2])
            else:
                for child in value:
                    visit(child)
    visit(row.get("evidence", []))
    return sorted(values)


def build() -> dict:
    source = ROOT / "sources/cfever/dev.jsonl"
    if hashlib.sha256(source.read_bytes()).hexdigest() != UPSTREAM_SHA256:
        raise ValueError("Pinned upstream file differs from the downloaded official commit; do not silently re-freeze it.")
    original = [json.loads(line) for line in source.read_text(encoding="utf-8").splitlines() if line.strip()]
    # Connected components across EVERY upstream development claim prevent
    # evidence-page overlap across selected train/dev/test groups.
    parents: dict[str, str] = {}
    def find(value):
        parents.setdefault(value, value)
        if parents[value] != value:
            parents[value] = find(parents[value])
        return parents[value]
    def union(left, right):
        a, b = sorted((find(left), find(right)))
        parents[b] = a
    for row in original:
        links = ["page:" + p for p in pages(row)]
        # Identical claims (including upstream duplicate IDs) share a split.
        links.append("claim:" + sha("".join(row["claim"].split())))
        if not pages(row):
            # No topic/entity annotations for NEI: conservative domain block.
            links.append("nei-domain:" + str(row.get("domain", "unknown")))
        for link in links[1:]:
            union(links[0], link)
    selected = []
    seen = set()
    for label in ("supports", "refutes", "NOT ENOUGH INFO"):
        candidates = sorted((r for r in original if r["label"] == label and len(r["claim"]) >= 20),
                            key=lambda r: sha(str(r["id"])))
        count = 0
        for row in candidates:
            normalized = "".join(row["claim"].split())
            if normalized in seen:
                continue
            seen.add(normalized)
            group = find("claim:" + sha(normalized))
            bucket = int(sha(group)[:8], 16) % 10
            split = "train" if bucket < 6 else "dev" if bucket < 8 else "test"
            selected.append({"sample_id": f"CFEVER-DEV-{row['id']}", "topic_id": sha(group)[:16],
                             "split": split, "title": "待核验原始主张", "content": row["claim"], "url": "",
                             "gold_label": "", "upstream_label": row["label"],
                             "gold_label_source": "upstream three-class only; no four-level mapping",
                             "source_dataset": "CFEVER dev", "source_record_ids": str(row["id"]),
                             "source_url": UPSTREAM, "domain": row.get("domain", ""),
                             "upstream_evidence_json": json.dumps(row["evidence"], ensure_ascii=False),
                             "relevant_page_ids": json.dumps(pages(row), ensure_ascii=False),
                             "relevant_knowledge_ids": "", "relevant_chunk_ids": "",
                             "allow_web_search": "false", "reviewer_1_label": "", "reviewer_2_label": "",
                             "reviewer_1_id": "", "reviewer_2_id": "", "reviewer_1_type": "", "reviewer_2_type": "",
                             "human_review_status": "pending_independent_review", "adjudication_reason": ""})
            count += 1
            if count == 40:
                break
        if count < 40:
            raise ValueError(f"Insufficient eligible claims for {label}")
    selected.sort(key=lambda row: row["sample_id"])
    target = ROOT / "news_eval.csv"
    # Keep the former synthetic/leaky input as a quarantined regression fixture.
    if target.exists() and b"NEWS-EVAL-001" in target.read_bytes():
        quarantine = ROOT / "quarantine"
        quarantine.mkdir(exist_ok=True)
        (quarantine / "news_eval_synthetic_leaky.csv").write_bytes(target.read_bytes())
    with target.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(selected[0]))
        writer.writeheader()
        writer.writerows(selected)
    corpus = sorted({p for row in original for p in pages(row)})
    (ROOT / "cfever_page_titles.jsonl").write_text("".join(json.dumps({"page_id": p, "title": p}, ensure_ascii=False) + "\n" for p in corpus), encoding="utf-8")
    fields = ["sample_id", "topic_id", "split", "title", "content", "source_record_ids",
              "reviewer_1_id", "reviewer_1_type", "reviewer_1_label", "reviewer_1_reason", "reviewer_1_sources",
              "reviewer_2_id", "reviewer_2_type", "reviewer_2_label", "reviewer_2_reason", "reviewer_2_sources",
              "gold_label", "adjudication_reason", "human_review_status"]
    with (ROOT / "human_review_pending.csv").open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=fields)
        writer.writeheader()
        writer.writerows({field: row.get(field, "") for field in fields} for row in selected)
    files = ("news_eval.csv", "cfever_page_titles.jsonl", "sources/cfever/dev.jsonl", "sources/cfever/LICENSE")
    manifest = {"schema_version": 1, "dataset_version": "cfever-claims-v1", "upstream_commit": COMMIT,
                "upstream_url": UPSTREAM, "upstream_license": "Apache-2.0 (see bundled LICENSE)",
                "purpose": "Official 3-class claim labels and page-title retrieval smoke baseline; NOT four-level news accuracy",
                "sample_count": len(selected), "upstream_row_count": len(original), "title_corpus_count": len(corpus),
                "label_counts": dict(Counter(r["upstream_label"] for r in selected)),
                "selection_rule": "For each upstream label, take first 40 distinct claims of >=20 characters sorted by SHA-256(source id); preserve exact text and evidence",
                "split_counts": dict(Counter(r["split"] for r in selected)),
                "split_rule": "60/20/20 hash buckets of connected evidence-page/exact-claim groups; NEI grouped by domain; counts are not forced",
                "limitations": ["Upstream claims are human-created Wikipedia fact-verification statements, not a real-world news distribution.",
                                "All sources are Wikipedia; no claim of source-domain generalization.",
                                "Title-only corpus uses all annotated dev pages; this is a closed corpus baseline, not full Wikipedia retrieval.",
                                "Original upstream test split is not used and no official leaderboard comparison is valid.",
                                "Four-level labels, app knowledge/chunk relevance and two local human reviews remain absent."],
                "files": {name: hashlib.sha256((ROOT / name).read_bytes()).hexdigest() for name in files}}
    (ROOT / "frozen_manifest.json").write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return manifest


if __name__ == "__main__":
    print(json.dumps(build(), ensure_ascii=False, indent=2))
