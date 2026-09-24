import tempfile
import unittest
from pathlib import Path
from types import SimpleNamespace

from fastapi.responses import FileResponse, JSONResponse

from app.api.report_download import build_report_pdf_download_response
from app.services.report_service import (
    ReportAccessDeniedError,
    ReportFileMissingError,
    ReportNotFoundError,
)


class ReportDownloadResponseTests(unittest.TestCase):
    def test_builds_a_consistent_pdf_response(self) -> None:
        with tempfile.TemporaryDirectory() as temp_dir:
            pdf_file = Path(temp_dir) / "report.pdf"
            pdf_file.write_bytes(b"%PDF-1.4\nreport")

            response = build_report_pdf_download_response(
                db=object(),
                report_id=7,
                current_user=object(),
                load_report_pdf=lambda *_: (SimpleNamespace(id=7), pdf_file),
            )

        self.assertIsInstance(response, FileResponse)
        self.assertEqual(response.media_type, "application/pdf")
        self.assertIn("news-credibility-report-7.pdf", response.headers["content-disposition"])

    def test_maps_download_service_errors_consistently(self) -> None:
        for error, status_code in (
            (ReportNotFoundError("报告不存在"), 404),
            (ReportAccessDeniedError("无权下载"), 403),
            (ReportFileMissingError("PDF 文件不存在"), 404),
        ):
            with self.subTest(error=type(error).__name__):
                def raise_error(*_):
                    raise error

                response = build_report_pdf_download_response(
                    db=object(),
                    report_id=7,
                    current_user=object(),
                    load_report_pdf=raise_error,
                )

                self.assertIsInstance(response, JSONResponse)
                self.assertEqual(response.status_code, status_code)


if __name__ == "__main__":
    unittest.main()
