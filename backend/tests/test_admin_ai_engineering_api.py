import unittest
from types import SimpleNamespace
from unittest.mock import patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.main import app


def _admin_override():
    return SimpleNamespace(id=1, username="admin", role="admin", status="active")


class AdminAiEngineeringApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.admin_ai_engineering.get_ai_engineering_summary")
    def test_admin_can_read_ai_engineering_summary(self, mocked_summary) -> None:
        mocked_summary.return_value = {
            "source": {"type": "summary_file", "path": ".artifacts/ai_eval/summary.json"},
            "schema_version": "ai-engineering-eval/v1",
            "generated_at": "2026-07-11T00:00:00Z",
            "metrics": {"total_cases": 3, "risk_level_accuracy": 1.0},
            "gate": {"passed": True, "failures": [], "thresholds": {}},
            "per_case": [{"case_id": "AI-SMOKE-001", "contract_valid": True}],
        }

        response = self.client.get("/api/admin/ai-engineering/summary")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertEqual(data["source"]["type"], "summary_file")
        self.assertEqual(data["metrics"]["total_cases"], 3)
        self.assertTrue(data["gate"]["passed"])

    def test_normal_user_cannot_access_ai_engineering_summary(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/ai-engineering/summary")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_ai_engineering_summary(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        response = self.client.get("/api/admin/ai-engineering/summary")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
