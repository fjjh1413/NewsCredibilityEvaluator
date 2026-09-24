"""Identify tested working-tree sources without pretending they are committed."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import subprocess


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()
    root = Path(__file__).resolve().parents[2]

    def git(*arguments: str) -> str:
        return subprocess.check_output(
            ["git", "-c", f"safe.directory={root.as_posix()}", *arguments],
            cwd=root, text=True, encoding="utf-8",
        ).strip()

    prefixes = ("backend/app/", "backend/tests/", "backend/alembic/", "frontend/src/",
                "frontend/build/", "contracts/", "evaluation/", "scripts/ci/", ".github/workflows/")
    specific = {"backend/Dockerfile", "backend/requirements.txt", "backend/requirements-test.txt",
                "backend/alembic.ini", "frontend/Dockerfile", "frontend/package.json",
                "frontend/package-lock.json", "frontend/vite.config.js", ".dockerignore",
                "docker-compose.yml", "docker-compose.prod.yml"}
    sources = {}
    for relative in sorted(set(git("ls-files", "-z", "--cached", "--others", "--exclude-standard").split("\0"))):
        path = root / relative
        if not path.is_file() or path.name.startswith(".env"):
            continue
        if relative.startswith(prefixes) or relative in specific:
            sources[relative] = hashlib.sha256(path.read_bytes()).hexdigest()
    manifest = {
        "base_commit": git("rev-parse", "HEAD"),
        "branch": git("branch", "--show-current"),
        "working_tree_dirty": bool(git("status", "--porcelain")),
        "scope": "selected runtime, tests, evaluation and build files; includes untracked sources; excludes environment files",
        "source_tree_sha256": hashlib.sha256(json.dumps(sources, sort_keys=True).encode()).hexdigest(),
        "file_count": len(sources),
        "files": sources,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(manifest, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in manifest.items() if key != "files"}, ensure_ascii=False))


if __name__ == "__main__":
    main()
