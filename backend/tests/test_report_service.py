import os
import tempfile
import unittest
from datetime import datetime
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.core.config import BASE_DIR, get_settings
from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.evidence_match import EvidenceMatch
from app.models.report import Report
from app.models.user import User
from app.services.report_service import (
    ReportAccessDeniedError,
    ReportFileMissingError,
    _convert_html_to_pdf,
    _resolve_stored_path,
    build_news_summary,
    delete_admin_report_record,
    generate_detection_report,
    get_admin_report_detail,
    get_report_pdf_for_download,
    list_admin_reports,
)


class ReportServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.previous_report_dir = os.environ.get("REPORT_DIR")
        self.temp_dir = tempfile.TemporaryDirectory()
        os.environ["REPORT_DIR"] = self.temp_dir.name
        get_settings.cache_clear()

        self.engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()

        self.user = self._add_user(1, "report_user")
        self.other_user = self._add_user(2, "other_user")
        self.admin = self._add_user(99, "report_admin", role="admin")
        self.detection = self._add_detection(self.user.id)

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()
        self.temp_dir.cleanup()
        if self.previous_report_dir is None:
            os.environ.pop("REPORT_DIR", None)
        else:
            os.environ["REPORT_DIR"] = self.previous_report_dir
        get_settings.cache_clear()

    def test_generate_report_saves_html_pdf_and_download_url(self) -> None:
        def fake_converter(html_content: str, pdf_file: Path) -> None:
            self.assertIn("测试新闻标题", html_content)
            self.assertIn("测试新闻正文", html_content)
            self.assertIn("新闻摘要", html_content)
            self.assertNotIn("完整正文末尾不应进入 PDF", html_content)
            self.assertIn("官方证据", html_content)
            pdf_file.write_bytes(b"%PDF-1.4\nfake report")

        with patch(
            "app.services.report_service._convert_html_to_pdf",
            side_effect=fake_converter,
        ):
            report = generate_detection_report(self.db, self.detection.id, self.user)

        self.assertIsNotNone(report.id)
        self.assertEqual(report.user_id, self.user.id)
        self.assertFalse(Path(report.html_path).is_absolute())
        self.assertFalse(Path(report.pdf_path).is_absolute())
        report_root = Path(get_settings().report_path)
        html_content = (report_root / report.html_path).read_text(encoding="utf-8")
        self.assertIn("AI 分析理由", html_content)
        self.assertIn("免责声明", html_content)
        self.assertTrue((report_root / report.pdf_path).is_file())

        self.db.refresh(self.detection)
        self.assertEqual(
            self.detection.report_url,
            f"/api/report/download/{report.id}",
        )

    def test_regenerate_reuses_cached_report_files(self) -> None:
        def fake_converter(html_content: str, pdf_file: Path) -> None:
            pdf_file.write_bytes(b"%PDF-1.4\nfake report")

        with patch(
            "app.services.report_service._convert_html_to_pdf",
            side_effect=fake_converter,
        ) as mocked_converter:
            first_report = generate_detection_report(
                self.db,
                self.detection.id,
                self.user,
            )
            first_id = first_report.id
            old_html = Path(get_settings().report_path) / first_report.html_path
            old_pdf = Path(get_settings().report_path) / first_report.pdf_path
            second_report = generate_detection_report(
                self.db,
                self.detection.id,
                self.user,
            )

        self.assertEqual(second_report.id, first_id)
        self.assertEqual(self.db.query(Report).count(), 1)
        self.assertEqual(second_report.html_path, first_report.html_path)
        self.assertEqual(second_report.pdf_path, first_report.pdf_path)
        self.assertTrue(old_html.exists())
        self.assertTrue(old_pdf.exists())
        self.assertEqual(mocked_converter.call_count, 1)

    def test_regenerate_when_cached_files_are_missing(self) -> None:
        def fake_converter(html_content: str, pdf_file: Path) -> None:
            pdf_file.write_bytes(b"%PDF-1.4\nfake report")

        with patch(
            "app.services.report_service._convert_html_to_pdf",
            side_effect=fake_converter,
        ) as mocked_converter:
            first_report = generate_detection_report(
                self.db,
                self.detection.id,
                self.user,
            )
            first_html_path = first_report.html_path
            first_pdf_path = first_report.pdf_path
            report_root = Path(get_settings().report_path)
            (report_root / first_html_path).unlink()
            (report_root / first_pdf_path).unlink()

            second_report = generate_detection_report(
                self.db,
                self.detection.id,
                self.user,
            )

        self.assertEqual(second_report.id, first_report.id)
        self.assertNotEqual(second_report.html_path, first_html_path)
        self.assertNotEqual(second_report.pdf_path, first_pdf_path)
        self.assertTrue(
            (Path(get_settings().report_path) / second_report.pdf_path).is_file()
        )
        self.assertEqual(mocked_converter.call_count, 2)

    def test_regular_user_cannot_generate_or_download_another_users_report(self) -> None:
        with self.assertRaises(ReportAccessDeniedError):
            generate_detection_report(self.db, self.detection.id, self.other_user)

        report = self._add_report(self.detection)
        with self.assertRaises(ReportAccessDeniedError):
            get_report_pdf_for_download(self.db, report.id, self.other_user)

    def test_admin_can_generate_and_download_any_report(self) -> None:
        def fake_converter(html_content: str, pdf_file: Path) -> None:
            pdf_file.write_bytes(b"%PDF-1.4\nfake report")

        with patch(
            "app.services.report_service._convert_html_to_pdf",
            side_effect=fake_converter,
        ):
            report = generate_detection_report(self.db, self.detection.id, self.admin)

        downloaded_report, pdf_file = get_report_pdf_for_download(
            self.db,
            report.id,
            self.admin,
        )
        self.assertEqual(downloaded_report.id, report.id)
        self.assertTrue(pdf_file.is_file())

    def test_download_rejects_path_outside_report_directory(self) -> None:
        report = self._add_report(self.detection, pdf_path="../../etc/passwd")

        with self.assertRaises(ReportFileMissingError):
            get_report_pdf_for_download(self.db, report.id, self.user)

    def test_download_rejects_non_report_prefixed_pdf_filename(self) -> None:
        report_root = Path(get_settings().report_path)
        pdf_file = report_root / "detection_1" / "manual.pdf"
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(b"%PDF-1.4\nmanual report")
        report = self._add_report(self.detection, pdf_path="detection_1/manual.pdf")

        with self.assertRaisesRegex(ReportFileMissingError, "report_"):
            get_report_pdf_for_download(self.db, report.id, self.user)

    def test_download_rejects_non_pdf_or_html_filename(self) -> None:
        report_root = Path(get_settings().report_path)
        text_file = report_root / "detection_1" / "abc.txt"
        text_file.parent.mkdir(parents=True, exist_ok=True)
        text_file.write_text("not a report", encoding="utf-8")
        report = self._add_report(self.detection, pdf_path="detection_1/abc.txt")

        with self.assertRaisesRegex(ReportFileMissingError, "report_"):
            get_report_pdf_for_download(self.db, report.id, self.user)

    def test_download_rejects_report_prefixed_pdf_without_generated_uuid(self) -> None:
        report_root = Path(get_settings().report_path)
        pdf_file = report_root / "detection_1" / "report_manual.pdf"
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(b"%PDF-1.4\nmanual report")
        report = self._add_report(self.detection, pdf_path="detection_1/report_manual.pdf")

        with self.assertRaisesRegex(ReportFileMissingError, "report_"):
            get_report_pdf_for_download(self.db, report.id, self.user)

    def test_resolve_stored_path_accepts_report_prefixed_html_filename(self) -> None:
        report_root = Path(get_settings().report_path)
        html_name = "report_0123456789abcdef0123456789abcdef.html"
        html_file = report_root / "detection_1" / html_name
        html_file.parent.mkdir(parents=True, exist_ok=True)
        html_file.write_text("<html></html>", encoding="utf-8")

        resolved = _resolve_stored_path(report_root, f"detection_1/{html_name}")

        self.assertEqual(resolved, html_file.resolve())

    def test_report_path_creates_missing_report_directory(self) -> None:
        missing_report_dir = Path(self.temp_dir.name) / "nested" / "reports"
        self.assertFalse(missing_report_dir.exists())
        os.environ["REPORT_DIR"] = str(missing_report_dir)
        get_settings.cache_clear()

        report_path = Path(get_settings().report_path)

        self.assertEqual(report_path, missing_report_dir.resolve())
        self.assertTrue(report_path.is_dir())

    def test_report_path_raises_clear_error_when_directory_cannot_be_created(self) -> None:
        missing_report_dir = Path(self.temp_dir.name) / "blocked" / "reports"
        os.environ["REPORT_DIR"] = str(missing_report_dir)
        get_settings.cache_clear()

        with patch("pathlib.Path.mkdir", side_effect=OSError("permission denied")):
            with self.assertRaisesRegex(RuntimeError, "Unable to create REPORT_DIR"):
                get_settings().report_path

    def test_real_html_to_pdf_converter_creates_pdf(self) -> None:
        pdf_file = Path(self.temp_dir.name) / "converter-test.pdf"

        _convert_html_to_pdf(
            "<html><body><h1>智闻辨真报告</h1><p>PDF converter test</p></body></html>",
            pdf_file,
        )

        self.assertTrue(pdf_file.is_file())
        self.assertTrue(pdf_file.read_bytes().startswith(b"%PDF"))

    def test_report_directory_cannot_be_inside_backend_source(self) -> None:
        os.environ["REPORT_DIR"] = str(BASE_DIR / "reports")
        get_settings.cache_clear()

        with self.assertRaisesRegex(RuntimeError, "outside the backend source"):
            get_settings().report_path

        os.environ["REPORT_DIR"] = self.temp_dir.name
        get_settings.cache_clear()

    def test_admin_report_list_and_detail_use_computed_status(self) -> None:
        report_root = Path(get_settings().report_path)
        pdf_name = "report_0123456789abcdef0123456789abcdef.pdf"
        pdf_file = report_root / "detection_1" / pdf_name
        pdf_file.parent.mkdir(parents=True, exist_ok=True)
        pdf_file.write_bytes(b"%PDF-1.4\nadmin report")
        self._add_report(self.detection, pdf_path=f"detection_1/{pdf_name}")
        missing_detection = self._add_detection(self.other_user.id)
        self._add_report(missing_detection, pdf_path="missing.pdf")

        generated = list_admin_reports(self.db, status="generated")
        missing = list_admin_reports(self.db, status="missing")
        detail = get_admin_report_detail(self.db, generated["items"][0]["report_id"])

        self.assertEqual(generated["total"], 1)
        self.assertEqual(generated["items"][0]["status"], "generated")
        self.assertGreater(generated["items"][0]["file_size"], 0)
        self.assertTrue(generated["items"][0]["download_url"].endswith("/admin/reports/1/download"))
        self.assertEqual(missing["total"], 1)
        self.assertEqual(detail["report_path"], f"detection_1/{pdf_name}")
        self.assertLessEqual(len(detail["news_summary"]), 243)
        self.assertNotIn("完整正文末尾不应进入 PDF", detail["news_summary"])

    def test_admin_report_item_uses_report_updated_at(self) -> None:
        report = self._add_report(self.detection)
        created_at = datetime(2026, 1, 1, 8, 0, 0)
        updated_at = datetime(2026, 1, 3, 9, 30, 0)
        report.created_at = created_at
        report.updated_at = updated_at
        self.db.add(report)
        self.db.commit()

        result = list_admin_reports(self.db)

        self.assertEqual(result["items"][0]["created_at"], created_at)
        self.assertEqual(result["items"][0]["updated_at"], updated_at)

    def test_admin_report_list_uses_database_page_before_building_items(self) -> None:
        self._add_report(self.detection)
        self._add_report(self._add_detection(self.user.id))
        self._add_report(self._add_detection(self.user.id))

        with patch("app.services.report_service._build_admin_report_item") as mocked_build:
            mocked_build.side_effect = lambda db, report, **kwargs: {
                "report_id": int(report.id)
            }

            result = list_admin_reports(self.db, page=2, page_size=1)

        self.assertEqual(result["total"], 3)
        self.assertEqual(result["page"], 2)
        self.assertEqual(result["page_size"], 1)
        self.assertEqual(len(result["items"]), 1)
        self.assertEqual(mocked_build.call_count, 1)

    def test_report_summary_is_generated_without_llm(self) -> None:
        def fake_converter(html_content: str, pdf_file: Path) -> None:
            pdf_file.write_bytes(b"%PDF-1.4\nfake report")

        with (
            patch("app.services.llm_service.analyze_news_credibility") as mocked_llm,
            patch(
                "app.services.report_service._convert_html_to_pdf",
                side_effect=fake_converter,
            ),
        ):
            generate_detection_report(self.db, self.detection.id, self.user)

        mocked_llm.assert_not_called()

    def test_build_news_summary_cleans_whitespace_and_limits_length(self) -> None:
        self.detection.input_content = "  第一段\n\n第二段  " * 80
        summary = build_news_summary(self.detection)

        self.assertNotIn("\n", summary)
        self.assertLessEqual(len(summary), 243)

    def test_delete_admin_report_removes_record_files_and_clears_report_url(self) -> None:
        report_root = Path(get_settings().report_path)
        report_dir = report_root / f"detection_{self.detection.id}"
        report_dir.mkdir(parents=True, exist_ok=True)
        html_path = f"detection_{self.detection.id}/report_{'a' * 32}.html"
        pdf_path = f"detection_{self.detection.id}/report_{'b' * 32}.pdf"
        (report_root / html_path).write_text("<html>report</html>", encoding="utf-8")
        (report_root / pdf_path).write_bytes(b"%PDF-1.4\nreport")
        report = self._add_report(self.detection, pdf_path=pdf_path)
        report.html_path = html_path
        self.detection.report_url = f"/api/report/download/{report.id}"
        self.db.add(report)
        self.db.add(self.detection)
        self.db.commit()

        deleted_id = delete_admin_report_record(self.db, report.id)

        self.assertEqual(deleted_id, report.id)
        self.assertIsNone(self.db.query(Report).filter(Report.id == report.id).first())
        self.db.refresh(self.detection)
        self.assertIsNone(self.detection.report_url)
        self.assertFalse((report_root / html_path).exists())
        self.assertFalse((report_root / pdf_path).exists())

    def _add_user(self, user_id: int, username: str, role: str = "user") -> User:
        now = datetime(2026, 1, 1, 8, 0, 0)
        user = User(
            id=user_id,
            username=username,
            email=f"{username}@example.com",
            password_hash="secret-hash",
            role=role,
            status="active",
            created_at=now,
            updated_at=now,
        )
        self.db.add(user)
        self.db.commit()
        self.db.refresh(user)
        return user

    def _add_detection(self, user_id: int) -> DetectionRecord:
        detection = DetectionRecord(
            user_id=user_id,
            input_title="测试新闻标题",
            input_content=("测试新闻正文 " * 80) + "完整正文末尾不应进入 PDF",
            category="社会",
            keywords="关键词一,关键词二",
            final_score=68.5,
            evidence_score=70,
            llm_score=65,
            rule_score=72,
            risk_level="存疑信息",
            judgement_result="需要进一步核查",
            reason="证据不足，需要结合权威来源。",
            risk_points='["来源不明确", "缺少权威证据"]',
            suggestion="建议查看官方通报。",
            is_high_risk=False,
            created_at=datetime(2026, 1, 2, 8, 0, 0),
        )
        detection.evidence_matches.append(
            EvidenceMatch(
                knowledge_id=1,
                title="官方证据",
                summary="证据摘要",
                source_name="官方媒体",
                similarity_score=0.8321,
                rank_order=1,
            )
        )
        self.db.add(detection)
        self.db.commit()
        self.db.refresh(detection)
        return detection

    def _add_report(
        self,
        detection: DetectionRecord,
        pdf_path: str = "missing.pdf",
    ) -> Report:
        report = Report(
            detection_id=detection.id,
            user_id=detection.user_id,
            report_title="测试报告",
            html_path="missing.html",
            pdf_path=pdf_path,
        )
        self.db.add(report)
        self.db.commit()
        self.db.refresh(report)
        return report


if __name__ == "__main__":
    unittest.main()
