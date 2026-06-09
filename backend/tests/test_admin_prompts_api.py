import unittest
from datetime import datetime
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app
from app.services.prompt_service import (
    PromptTemplateDefaultDeleteError,
    PromptTemplateDisabledError,
)
from app.services.prompt_template_validator import PromptTemplateValidationError


def _db_override():
    return Mock()


def _admin_override():
    return SimpleNamespace(id=99, username="admin", role="admin", status="active")


def _prompt(template_id: int = 1, **overrides):
    data = {
        "id": template_id,
        "name": "Credibility default",
        "type": "news_credibility",
        "content": "Analyze {title} {content} {evidence_list}",
        "is_default": True,
        "status": "enabled",
        "created_by": 99,
        "created_at": datetime(2026, 1, 1, 8, 0, 0),
        "updated_at": datetime(2026, 1, 1, 8, 0, 0),
    }
    data.update(overrides)
    return SimpleNamespace(**data)


class AdminPromptsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.admin_prompts.list_prompt_templates")
    def test_admin_can_list_prompt_templates(self, mocked_list) -> None:
        mocked_list.return_value = ([_prompt()], 1)

        response = self.client.get(
            "/api/admin/prompts?type=news_credibility&status=enabled&keyword=Credibility"
        )

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["items"][0]["type"], "news_credibility")
        kwargs = mocked_list.call_args.kwargs
        self.assertEqual(kwargs["prompt_type"], "news_credibility")
        self.assertEqual(kwargs["status"], "enabled")

    @patch("app.api.v1.admin_prompts.create_prompt_template")
    def test_create_records_current_admin(self, mocked_create) -> None:
        mocked_create.return_value = _prompt()

        response = self.client.post(
            "/api/admin/prompts",
            json={
                "name": "Credibility default",
                "type": "news_credibility",
                "content": "Analyze {title} {content} {evidence_list}",
                "is_default": True,
                "status": "enabled",
            },
        )

        self.assertEqual(response.status_code, 201)
        self.assertEqual(mocked_create.call_args.kwargs["created_by"], 99)

    @patch("app.api.v1.admin_prompts.set_default_prompt_template")
    def test_disabled_template_cannot_be_set_default(self, mocked_set_default) -> None:
        mocked_set_default.side_effect = PromptTemplateDisabledError("disabled")

        response = self.client.post("/api/admin/prompts/1/set-default")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["message"], "disabled")

    @patch("app.api.v1.admin_prompts.set_default_prompt_template")
    def test_invalid_template_cannot_be_set_default(self, mocked_set_default) -> None:
        mocked_set_default.side_effect = PromptTemplateValidationError(
            "新闻检测Prompt必须包含新闻标题占位符：{title}"
        )

        response = self.client.post("/api/admin/prompts/1/set-default")

        self.assertEqual(response.status_code, 422)
        self.assertIn("{title}", response.json()["message"])

    @patch("app.api.v1.admin_prompts.delete_prompt_template")
    def test_default_template_delete_returns_conflict(self, mocked_delete) -> None:
        mocked_delete.side_effect = PromptTemplateDefaultDeleteError("default")

        response = self.client.delete("/api/admin/prompts/1")

        self.assertEqual(response.status_code, 409)
        self.assertEqual(response.json()["message"], "default")

    def test_non_admin_dependency_cannot_access_prompt_management(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/prompts")

        self.assertEqual(response.status_code, 403)


if __name__ == "__main__":
    unittest.main()
