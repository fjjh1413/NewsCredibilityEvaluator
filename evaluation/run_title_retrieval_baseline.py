"""Real, no-provider title retrieval baseline on frozen upstream annotations.

This is an explicit diagnostic baseline, not the production RAG pipeline and
not a semantic/hash embedding benchmark. No threshold is tuned on test results.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import json
import platform
import re
import time
from pathlib import Path

from evaluation.dataset_quality import verify_manifest
from evaluation.metrics import _ranked_retrieval_stats


def normalise(text: str) -> str:
    return re.sub(r"[\W_]+", "", text.casefold())


def bigrams(text: str) -> set[str]:
    return {text[i:i + 2] for i in range(len(text) - 1)} or {text}


def retrieve(query: str, corpus: list[dict], k: int = 10) -> list[dict]:
    query = normalise(query)
    query_grams = bigrams(query)
    scored = []
    for document in corpus:
        title = normalise(document["title"])
        overlap = len(query_grams & bigrams(title))
        # Exact title containment then title bigram coverage. No gold consulted.
        score = float(bool(title) and title in query) + overlap / max(1, len(bigrams(title)))
        if score > 0:
            scored.append({"page_id": document["page_id"], "score": round(score, 6)})
    return sorted(scored, key=lambda item: (-item["score"], item["page_id"]))[:k]


def run(dataset_dir: Path, output: Path) -> dict:
    manifest = verify_manifest(dataset_dir / "frozen_manifest.json")
    with (dataset_dir / "news_eval.csv").open(encoding="utf-8", newline="") as file:
        rows = list(csv.DictReader(file))
    corpus = [json.loads(line) for line in (dataset_dir / "cfever_page_titles.jsonl").read_text(encoding="utf-8").splitlines()]
    results = []
    for row in rows:
        start = time.perf_counter()
        ranked = retrieve(row["content"], corpus)
        expected = json.loads(row["relevant_page_ids"])
        results.append({"sample_id": row["sample_id"], "split": row["split"], "claim": row["content"],
                        "upstream_label": row["upstream_label"], "expected_page_ids": expected,
                        "ranked": ranked, "latency_ms": round((time.perf_counter() - start) * 1000, 3),
                        "relevance_origin": "official CFEVER evidence page annotations",
                        "hit_at_10": bool(set(expected) & {r["page_id"] for r in ranked}) if expected else None})
    grouped = {}
    for split in ("train", "dev", "test", "all_diagnostic"):
        selected = [r for r in results if split == "all_diagnostic" or r["split"] == split]
        eligible = [r for r in selected if r["expected_page_ids"]]
        stats = _ranked_retrieval_stats([(set(r["expected_page_ids"]), [i["page_id"] for i in r["ranked"]]) for r in eligible], [1, 3, 5, 10])
        grouped[split] = {"sample_count": len(selected), "annotated_count": len(eligible),
                          "nei_excluded_count": len(selected) - len(eligible), **stats}
    summary = {"benchmark": "CFEVER title-only lexical closed-corpus baseline", "dataset_version": manifest["dataset_version"],
               "dataset_hashes": manifest["files"], "python_version": platform.python_version(),
               "baseline_code_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
               "algorithm": "exact title containment + character bigram title coverage; fixed before results",
               "pipeline": "evaluation.run_title_retrieval_baseline; not production RAG",
               "corpus_size": len(corpus), "metrics_by_split": grouped,
               "publication_scope": "Only page-title lexical retrieval on this frozen subset. No classification, full-text RAG, semantic embedding or LLM accuracy claim.",
               "limitations": manifest["limitations"] + ["No simplified/traditional conversion: script/alias mismatches are expected failures.", "Relevant sets union all upstream evidence groups; evidence completeness is not verified by this title metric."]}
    output.mkdir(parents=True, exist_ok=True)
    (output / "per_case_results.jsonl").write_text("".join(json.dumps(r, ensure_ascii=False) + "\n" for r in results), encoding="utf-8")
    (output / "summary.json").write_text(json.dumps(summary, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    failures = [r for r in results if r["split"] == "test" and r["hit_at_10"] is False]
    lines = ["# 冻结基准的检索失败样本", "", summary["publication_scope"], "",
             "测试集指标保存在 summary.json；不能写成本项目端到端RAG效果。以下为全部test Top-10未命中的样本，未自动虚构失败原因。", ""]
    for row in failures:
        lines.extend([f"## {row['sample_id']}", f"主张：{row['claim']}",
                      f"官方证据页：{', '.join(row['expected_page_ids'])}",
                      f"实际Top-10：{', '.join(r['page_id'] for r in row['ranked'])}",
                      "待分析：别名/字形差异、主张未显式提及证据标题、词项歧义；需人工逐条确认。", ""])
        for page in row["expected_page_ids"]:
            shared = sorted(bigrams(normalise(row["claim"])) & bigrams(normalise(page)))
            lines.append(f"可直接复核的词项诊断：证据页「{page}」完整标题包含={normalise(page) in normalise(row['claim'])}，共享bigram={shared}。")
        lines.append("")
    (output / "failure_analysis.md").write_text("\n".join(lines) + "\n", encoding="utf-8")
    return summary


if __name__ == "__main__":
    parser = argparse.ArgumentParser()
    parser.add_argument("--dataset-dir", type=Path, default=Path(__file__).parent / "datasets")
    parser.add_argument("--output-dir", type=Path, default=Path(__file__).parent / "baselines/cfever-title-v1")
    args = parser.parse_args()
    print(json.dumps(run(args.dataset_dir, args.output_dir), ensure_ascii=False, indent=2))
