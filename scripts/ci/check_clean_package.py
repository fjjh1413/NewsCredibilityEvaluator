"""Reproduce packaging checks without reading developer .env or node_modules.

This supplements (and never substitutes for) the Docker build in CI. A new
output directory is retained for inspection. Requires the backend test/runtime
dependencies in the invoking Python environment and a Node/npm installation.
"""

from __future__ import annotations

import argparse
import json
import os
import shutil
import socket
import subprocess
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path


def verify_http_startup(output: Path, env: dict[str, str]) -> None:
    """Start only the copied API with local dummy configuration and probe HTTP."""
    with socket.socket() as reserved:
        reserved.bind(("127.0.0.1", 0))
        port = reserved.getsockname()[1]
    with (output / "api-startup.log").open("w", encoding="utf-8") as log:
        server = subprocess.Popen(
            [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "127.0.0.1", "--port", str(port)],
            cwd=output / "backend", env=env, stdout=log, stderr=subprocess.STDOUT,
            creationflags=getattr(subprocess, "CREATE_NO_WINDOW", 0),
        )
        try:
            deadline = time.monotonic() + 45
            while time.monotonic() < deadline:
                if server.poll() is not None:
                    raise RuntimeError("Copied API exited during startup; see api-startup.log")
                try:
                    with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/health", timeout=2) as response:
                        assert response.status == 200
                    break
                except (urllib.error.URLError, TimeoutError):
                    time.sleep(0.25)
            else:
                raise RuntimeError("Copied API did not become healthy within 45 seconds")
            with urllib.request.urlopen(f"http://127.0.0.1:{port}/api/ready", timeout=2) as response:
                assert response.status == 200
                payload = json.load(response)
            (output / "api-ready.json").write_text(json.dumps(payload, indent=2), encoding="utf-8")
            print("Copied API startup, /api/health and /api/ready passed (Redis disabled).")
        finally:
            server.terminate()
            try:
                server.wait(timeout=10)
            except subprocess.TimeoutExpired:
                server.kill()
                server.wait(timeout=5)


def main() -> None:
    # Vite emits Unicode progress marks even when the host console uses GBK.
    if hasattr(sys.stdout, "reconfigure"):
        sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--node", default="node")
    parser.add_argument("--npm-cli", type=Path, required=True)
    args = parser.parse_args()
    repo = Path(__file__).resolve().parents[2]
    output = args.output_dir.resolve()
    if output.exists():
        parser.error("output-dir must be new; stale packages must not hide missing files")
    output.mkdir(parents=True)
    ignored = shutil.ignore_patterns(
        ".env", ".env.*", "__pycache__", "*.pyc", ".pytest_cache", "node_modules",
        "dist", "chroma_db", "tmp*", "tests", "*.log",
    )
    for name in ("backend", "frontend", "contracts"):
        shutil.copytree(repo / name, output / name, ignore=ignored)
    (output / "evaluation").mkdir()
    shutil.copy2(repo / "evaluation/__init__.py", output / "evaluation/__init__.py")
    shutil.copytree(repo / "evaluation/ai_engineering", output / "evaluation/ai_engineering",
                    ignore=ignored)
    shutil.copy2(repo / "scripts/ci/verify_runtime_package.py", output)
    env = {
        **os.environ,
        "PYTHON_DOTENV_DISABLED": "1",
        "PYTHONPATH": "",
        "PYTHONDONTWRITEBYTECODE": "1",
        "PYTHONUTF8": "1",
        "APP_ENV": "development",
        "API_PREFIX": "/api",
        "BACKEND_CORS_ORIGINS": "*",
        "SECRET_KEY": "package-smoke-secret-0123456789abcdef",
        "DATABASE_URL": "sqlite:///:memory:",
        "EMBEDDING_PROVIDER": "hash",
        "WEB_SEARCH_ENABLED": "false",
        "CRAWL_ENABLED": "false",
        "KNOWLEDGE_INDEX_JOB_ENABLED": "false",
        "REDIS_ENABLED": "false",
        "REDIS_REQUIRED": "false",
        "OTEL_TRACING_ENABLED": "false",
        "PYROSCOPE_ENABLED": "false",
        "VITE_API_BASE_URL": "/api",
    }
    node = str(Path(args.node).resolve()) if Path(args.node).is_file() else args.node
    node_directory = Path(node).parent
    env["PATH"] = str(node_directory) + os.pathsep + env.get("PATH", "")
    commands = [
        ([sys.executable, str(output / "verify_runtime_package.py")], "backend", "backend-package.log"),
        ([node, str(args.npm_cli.resolve()), "ci", "--no-audit", "--no-fund"], "frontend", "npm-ci.log"),
        ([node, str(args.npm_cli.resolve()), "run", "build"], "frontend", "frontend-build.log"),
    ]
    for command, workdir, logfile in commands:
        result = subprocess.run(command, cwd=output / workdir, env=env,
                                text=True, encoding="utf-8", errors="replace",
                                stdout=subprocess.PIPE, stderr=subprocess.STDOUT)
        (output / logfile).write_text(result.stdout, encoding="utf-8")
        print(result.stdout)
        if result.returncode:
            raise SystemExit(result.returncode)
    verify_http_startup(output, env)
    print(f"Clean package imports and frontend build passed: {output}")
    print("Docker image build was NOT exercised by this script; CI performs it separately.")


if __name__ == "__main__":
    main()
