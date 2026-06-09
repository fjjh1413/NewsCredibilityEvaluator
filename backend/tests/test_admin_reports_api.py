import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi import HTTPException
from fastapi.testclient import TestClient

from app.core.deps import get_current_admin
from app.db.session import get_db
from app.main import app
from app.services.report_service import ReportFileMissingError, ReportNotFoundError


def _db_override():
    return Mock()


def _admin_override():
    return SimpleNamespace(id=1, username="admin", role="admin", status="active")


def _report_item():
    return {
        "report_id": 1,
        "detection_id": 10,
        "user_id": 2,
        "username": "report_user",
        "news_title": "测试新闻标题",
        "risk_level": "存疑信息",
        "final_score": 68.5,
        "file_name": "report.pdf",
        "file_size": 120,
        "status": "generated",
        "download_url": "/api/admin/reports/1/download",
        "created_at": datetime(2026, 1, 2, 8, 0, 0),
        "updated_at": datetime(2026, 1, 2, 8, 0, 0),
    }


def _report_detail():
    data = _report_item()
    data.update(
        {
            "report_title": "测试报告",
            "news_summary": "测试新闻正文摘要",
            "report_path": "detection_10/report.pdf",
        }
    )
    return data


class AdminReportsApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_admin] = _admin_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.admin_reports.list_admin_reports")
    def test_admin_can_list_reports(self, mocked_list) -> None:
        mocked_list.return_value = {
            "total": 1,
            "page": 1,
            "page_size": 20,
            "items": [_report_item()],
        }

        response = self.client.get("/api/admin/reports?keyword=测试&status=generated")

        self.assertEqual(response.status_code, 200)
        body = response.json()
        self.assertEqual(body["data"]["total"], 1)
        self.assertEqual(body["data"]["items"][0]["status"], "generated")
        self.assertEqual(mocked_list.call_args.kwargs["keyword"], "测试")
        self.assertEqual(mocked_list.call_args.kwargs["status"], "generated")

    @patch("app.api.v1.admin_reports.get_admin_report_detail")
    def test_admin_can_read_report_detail(self, mocked_detail) -> None:
        mocked_detail.return_value = _report_detail()

        response = self.client.get("/api/admin/reports/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["news_summary"], "测试新闻正文摘要")

    @patch("app.api.v1.admin_reports.get_report_pdf_for_download")
    def test_admin_can_download_report(self, mocked_download) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_file = Path(temp_dir) / "report.pdf"
            pdf_file.write_bytes(b"%PDF-1.4\nadmin report")
            mocked_download.return_value = (SimpleNamespace(id=1), pdf_file)

            response = self.client.get("/api/admin/reports/1/download")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @patch("app.api.v1.admin_reports.get_report_pdf_for_download")
    def test_admin_download_missing_file_returns_clear_error(self, mocked_download) -> None:
        mocked_download.side_effect = ReportFileMissingError("PDF 报告文件不存在")

        response = self.client.get("/api/admin/reports/1/download")

        self.assertEqual(response.status_code, 404)
        body = response.json()
        self.assertEqual(body["code"], 404)
        self.assertIn("PDF 报告文件不存在", body["message"])

    @patch("app.api.v1.admin_reports.get_admin_report_detail")
    def test_missing_report_detail_returns_404(self, mocked_detail) -> None:
        mocked_detail.side_effect = ReportNotFoundError("报告不存在")

        response = self.client.get("/api/admin/reports/999")

        self.assertEqual(response.status_code, 404)
        self.assertIn("报告不存在", response.json()["message"])

    def test_normal_user_cannot_access_admin_reports(self) -> None:
        def forbidden_admin():
            raise HTTPException(status_code=403, detail="Admin permission required")

        app.dependency_overrides[get_current_admin] = forbidden_admin

        response = self.client.get("/api/admin/reports")

        self.assertEqual(response.status_code, 403)
        self.assertEqual(response.json()["code"], 403)

    def test_unauthenticated_user_cannot_access_admin_reports(self) -> None:
        app.dependency_overrides.pop(get_current_admin, None)

        response = self.client.get("/api/admin/reports")

        self.assertEqual(response.status_code, 401)
        body = response.json()
        self.assertEqual(body["code"], 401)
        self.assertIsNone(body["data"])

    def test_validation_error_uses_unified_response(self) -> None:
        response = self.client.get("/api/admin/reports?page=0")

        self.assertEqual(response.status_code, 422)
        body = response.json()
        self.assertEqual(body["code"], 422)
        self.assertIn("page", body["message"])
        self.assertIsNone(body["data"])


if __name__ == "__main__":
    unittest.main()
