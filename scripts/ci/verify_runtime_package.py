"""Offline smoke check for the actual backend/worker deployment layout.

Run from backend/ (locally or inside the image). No provider, database or Redis
connection is made. Docker executes this during the build, so a missing shared
contract or an unimportable API/worker prevents publishing a broken image.
"""

from __future__ import annotations

import hashlib
import json
import sys
from pathlib import Path


def main() -> None:
    backend = Path.cwd().resolve()
    sys.path.insert(0, str(backend))
    contract_path = backend.parent / "contracts" / "prompt_output_contract.json"
    raw_contract = contract_path.read_bytes()
    contract = json.loads(raw_contract)

    from app.services.prompt_output_contract import (
        ANALYSIS_CONTRACT_VERSION,
        REQUIRED_RESULT_FIELDS,
        _CONTRACT_PATH,
    )
    from app.main import app
    from app.worker import celery_app

    assert _CONTRACT_PATH.resolve() == contract_path.resolve(), (
        "The runtime must use the shared repository contract"
    )
    assert ANALYSIS_CONTRACT_VERSION == contract["version"]
    assert tuple(contract["required_fields"]) == REQUIRED_RESULT_FIELDS
    # FastAPI may retain included routers internally rather than flattening
    # app.routes; OpenAPI exposes the actual mounted public paths.
    assert "/api/health" in app.openapi()["paths"]
    assert celery_app is not None
    print(json.dumps({
        "check": "runtime-package",
        "status": "passed",
        "contract_version": ANALYSIS_CONTRACT_VERSION,
        "contract_sha256": hashlib.sha256(raw_contract).hexdigest(),
        "api_import": "passed",
        "worker_import": "passed",
    }, ensure_ascii=False))


if __name__ == "__main__":
    main()
