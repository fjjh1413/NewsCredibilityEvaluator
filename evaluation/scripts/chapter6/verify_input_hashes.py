from __future__ import annotations

import argparse
import csv
import json
from pathlib import Path

from evaluation.scripts.chapter6.audit_evaluation import sha256_file


def compare_hash_manifest(
    project_root: Path, before: dict[str, str]
) -> tuple[dict[str, str | None], list[dict[str, str]]]:
    after: dict[str, str | None] = {}
    rows: list[dict[str, str]] = []
    for relative_path, before_hash in before.items():
        path = project_root / Path(relative_path)
        after_hash = sha256_file(path) if path.is_file() else None
        status = "missing" if after_hash is None else "unchanged" if after_hash == before_hash else "changed"
        after[relative_path] = after_hash
        rows.append(
            {
                "path": relative_path,
                "before_sha256": before_hash,
                "after_sha256": after_hash or "",
                "status": status,
            }
        )
    return after, rows


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("--project-root", type=Path, required=True)
    parser.add_argument("--before", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    args = parser.parse_args()

    before = json.loads(args.before.read_text(encoding="utf-8-sig"))
    after, rows = compare_hash_manifest(args.project_root.resolve(), before)
    args.output_dir.mkdir(parents=True, exist_ok=True)
    after_path = args.output_dir / "input_hashes_after.json"
    after_path.write_text(json.dumps(after, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    comparison_path = args.output_dir / "input_hash_comparison.csv"
    with comparison_path.open("w", encoding="utf-8-sig", newline="") as handle:
        writer = csv.DictWriter(
            handle,
            fieldnames=["path", "before_sha256", "after_sha256", "status"],
        )
        writer.writeheader()
        writer.writerows(rows)

    changed = [row for row in rows if row["status"] != "unchanged"]
    print(f"checked={len(rows)}")
    print(f"unchanged={len(rows) - len(changed)}")
    print(f"changed_or_missing={len(changed)}")
    return 1 if changed else 0


if __name__ == "__main__":
    raise SystemExit(main())
