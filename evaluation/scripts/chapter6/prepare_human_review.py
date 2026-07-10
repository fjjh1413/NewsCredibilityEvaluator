from __future__ import annotations

import argparse
import csv
from pathlib import Path


LABEL_ALIASES = {
    "可信": "可信新闻",
    "存疑": "存疑信息",
    "疑似谣言": "疑似谣言",
    "高风险": "高风险谣言",
}

OUTPUT_FIELDS = [
    "sample_id",
    "topic_id",
    "title",
    "content",
    "url",
    "current_mapped_label",
    "reviewer_a_label",
    "reviewer_a_confidence_1_to_5",
    "reviewer_a_reason",
    "reviewer_a_sources",
    "reviewer_b_label",
    "reviewer_b_confidence_1_to_5",
    "reviewer_b_reason",
    "reviewer_b_sources",
    "agreement",
    "adjudicated_label",
    "adjudicator_reason",
    "review_status",
]


def prepare_review_sheet(source: Path, output: Path) -> int:
    with source.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    prepared = []
    for row in rows:
        prepared.append(
            {
                "sample_id": row.get("sample_id", ""),
                "topic_id": row.get("topic_id", ""),
                "title": row.get("title", ""),
                "content": row.get("content", ""),
                "url": row.get("url", ""),
                "current_mapped_label": LABEL_ALIASES.get(
                    row.get("gold_label", ""), row.get("gold_label", "")
                ),
                "reviewer_a_label": "",
                "reviewer_a_confidence_1_to_5": "",
                "reviewer_a_reason": "",
                "reviewer_a_sources": "",
                "reviewer_b_label": "",
                "reviewer_b_confidence_1_to_5": "",
                "reviewer_b_reason": "",
                "reviewer_b_sources": "",
                "agreement": "",
                "adjudicated_label": "",
                "adjudicator_reason": "",
                "review_status": "pending_independent_review",
            }
        )
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(handle, fieldnames=OUTPUT_FIELDS)
        writer.writeheader()
        writer.writerows(prepared)
    return len(prepared)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    count = prepare_review_sheet(args.source.resolve(), args.output.resolve())
    print(f"review_rows={count}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
