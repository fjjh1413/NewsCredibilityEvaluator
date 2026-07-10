from __future__ import annotations

import csv
from pathlib import Path

from evaluation.scripts.chapter6.prepare_human_review import prepare_review_sheet


def test_prepare_review_sheet_keeps_human_fields_blank(tmp_path: Path) -> None:
    source = tmp_path / "news.csv"
    output = tmp_path / "review.csv"
    with source.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["sample_id", "topic_id", "title", "content", "url", "gold_label"],
        )
        writer.writeheader()
        writer.writerow(
            {
                "sample_id": "S1",
                "topic_id": "T1",
                "title": "测试新闻",
                "content": "测试正文",
                "url": "https://example.com",
                "gold_label": "可信",
            }
        )

    count = prepare_review_sheet(source, output)

    with output.open("r", encoding="utf-8-sig", newline="") as handle:
        rows = list(csv.DictReader(handle))
    assert count == 1
    assert rows[0]["current_mapped_label"] == "可信新闻"
    assert rows[0]["reviewer_a_label"] == ""
    assert rows[0]["reviewer_b_label"] == ""
    assert rows[0]["adjudicated_label"] == ""
