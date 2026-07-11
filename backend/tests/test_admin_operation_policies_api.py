import unittest
from types import SimpleNamespace

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.main import app


def _admin_override():
    return SimpleNamespace(id=1, username="admin", role="admin", status="active")


class AdminOperationPoliciesApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    def test_admin_can_list_operation_policies(self) -> None:
        response = self.client.get("/api/admin/operation-policies")

        self.assertEqual(response.status_code, 200)
        data = response.json()["data"]
        self.assertGreaterEqual(data["total"], 8)
        first = data["items"][0]
        self.assertIn(first["risk_level"], {"critical", "high", "medium"})
        self.assertIn("operation_key", first)
        self.assertIn("current_enforcement", first)
        self.assertIn("next_controls", first)

    def test_admin_can_filter_operation_policies_by_risk_level(self) -> None:
        response = self.client.get("/api/admin/operation-policies?risk_level=critical")

        self.assertEqual(response.status_code, 200)
        items = response.json()["data"]["items"]
        self.assertTrue(items)
        self.assertTrue(all(item["risk_level"] == "critical" for item in items))

    def test_normal_user_cannot_access_operation_policies(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/operation-policies")

        self.assertEqual(response.status_code, 403)

    def test_unauthenticated_user_cannot_access_operation_policies(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        response = self.client.get("/api/admin/operation-policies")

        self.assertEqual(response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
