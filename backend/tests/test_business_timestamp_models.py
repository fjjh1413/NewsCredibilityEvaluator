import unittest
from datetime import datetime

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.detection_record import DetectionRecord
from app.models.evidence_match import EvidenceMatch
from app.models.report import Report


class BusinessTimestampModelTestCase(unittest.TestCase):
    def setUp(self) -> None:
        engine = create_engine("sqlite:///:memory:")
        TestingSessionLocal = sessionmaker(bind=engine)
        Base.metadata.create_all(bind=engine)
        self.db = TestingSessionLocal()

    def tearDown(self) -> None:
        self.db.close()

    def test_new_business_records_receive_updated_at(self) -> None:
        detection, evidence, report = self._add_detection_with_related_rows()

        self.assertIsNotNone(detection.updated_at)
        self.assertIsNotNone(evidence.updated_at)
        self.assertIsNotNone(report.updated_at)

    def test_business_record_updates_refresh_updated_at_only(self) -> None:
        detection, evidence, report = self._add_detection_with_related_rows()
        original_created_at = {
            "detection": detection.created_at,
            "evidence": evidence.created_at,
            "report": report.created_at,
        }
        old_timestamp = datetime(2020, 1, 1, 0, 0, 0)

        detection.updated_at = old_timestamp
        evidence.updated_at = old_timestamp
        report.updated_at = old_timestamp
        self.db.add_all([detection, evidence, report])
        self.db.commit()

        detection.input_title = "Updated timestamp news"
        evidence.summary = "Updated evidence summary"
        report.report_title = "Updated report title"
        self.db.add_all([detection, evidence, report])
        self.db.commit()
        self.db.refresh(detection)
        self.db.refresh(evidence)
        self.db.refresh(report)

        self.assertEqual(detection.created_at, original_created_at["detection"])
        self.assertEqual(evidence.created_at, original_created_at["evidence"])
        self.assertEqual(report.created_at, original_created_at["report"])
        self.assertGreater(detection.updated_at, old_timestamp)
        self.assertGreater(evidence.updated_at, old_timestamp)
        self.assertGreater(report.updated_at, old_timestamp)

    def _add_detection_with_related_rows(
        self,
    ) -> tuple[DetectionRecord, EvidenceMatch, Report]:
        detection = DetectionRecord(
            input_title="Timestamp news",
            input_content="Timestamp content",
            final_score=68.5,
            evidence_score=70,
            llm_score=65,
            rule_score=72,
            risk_level="suspicious",
            judgement_result="needs review",
            is_high_risk=False,
        )
        evidence = EvidenceMatch(
            title="Timestamp evidence",
            summary="Evidence summary",
            source_name="Official source",
            similarity_score=0.8321,
            rank_order=1,
        )
        report = Report(report_title="Timestamp report")
        detection.evidence_matches.append(evidence)
        detection.report = report

        self.db.add(detection)
        self.db.commit()
        self.db.refresh(detection)
        self.db.refresh(evidence)
        self.db.refresh(report)
        return detection, evidence, report


if __name__ == "__main__":
    unittest.main()
