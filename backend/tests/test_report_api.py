import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import Mock, patch

from fastapi.testclient import TestClient

from app.core.deps import get_current_user
from app.db.session import get_db
from app.main import app
from app.services.report_service import (
    ReportAccessDeniedError,
    ReportFileMissingError,
    ReportGenerationError,
    ReportNotFoundError,
)


def _db_override():
    return Mock()


def _user_override():
    return SimpleNamespace(id=1, username="user", role="user", status="active")


def _report(report_id: int = 1):
    return SimpleNamespace(
        id=report_id,
        detection_id=10,
        user_id=1,
        report_title="新闻可信度检测报告",
        created_at=datetime(2026, 1, 2, 8, 0, 0),
    )


class ReportApiTestCase(unittest.TestCase):
    def setUp(self) -> None:
        app.dependency_overrides[get_db] = _db_override
        app.dependency_overrides[get_current_user] = _user_override
        self.client = TestClient(app)

    def tearDown(self) -> None:
        app.dependency_overrides.clear()

    @patch("app.api.v1.report.get_report_download_url")
    @patch("app.api.v1.report.generate_detection_report")
    def test_user_can_generate_owned_report(self, mocked_generate, mocked_url) -> None:
        mocked_generate.return_value = _report()
        mocked_url.return_value = "/api/report/download/1"

        response = self.client.post("/api/report/generate/10")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["data"]["download_url"], "/api/report/download/1")
        self.assertEqual(mocked_generate.call_args.args[2].id, 1)

    @patch("app.api.v1.report.generate_detection_report")
    def test_generate_maps_service_errors(self, mocked_generate) -> None:
        for error, status_code in (
            (ReportNotFoundError("检测记录不存在"), 404),
            (ReportAccessDeniedError("无权生成"), 403),
            (ReportGenerationError("PDF 生成失败"), 500),
        ):
            with self.subTest(status_code=status_code):
                mocked_generate.side_effect = error
                response = self.client.post("/api/report/generate/10")
                self.assertEqual(response.status_code, status_code)
                self.assertIn(str(error), response.json()["message"])

    @patch("app.api.v1.report.get_report_pdf_for_download")
    def test_user_can_download_owned_report(self, mocked_download) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_file = Path(temp_dir) / "report.pdf"
            pdf_file.write_bytes(b"%PDF-1.4\nreport")
            mocked_download.return_value = (_report(), pdf_file)

            response = self.client.get("/api/report/download/1")

        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.headers["content-type"], "application/pdf")
        self.assertTrue(response.content.startswith(b"%PDF"))

    @patch("app.api.v1.report.get_report_pdf_for_download")
    def test_download_maps_service_errors(self, mocked_download) -> None:
        for error, status_code in (
            (ReportNotFoundError("报告不存在"), 404),
            (ReportAccessDeniedError("无权下载"), 403),
            (ReportFileMissingError("PDF 文件不存在"), 404),
        ):
            with self.subTest(status_code=status_code, error=type(error).__name__):
                mocked_download.side_effect = error
                response = self.client.get("/api/report/download/1")
                self.assertEqual(response.status_code, status_code)
                self.assertIn(str(error), response.json()["message"])

    def test_unauthenticated_user_cannot_generate_or_download(self) -> None:
        app.dependency_overrides.pop(get_current_user, None)

        generate_response = self.client.post("/api/report/generate/10")
        download_response = self.client.get("/api/report/download/1")

        self.assertEqual(generate_response.status_code, 401)
        self.assertEqual(download_response.status_code, 401)


if __name__ == "__main__":
    unittest.main()
