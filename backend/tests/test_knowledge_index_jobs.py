from __future__ import annotations

import unittest
from datetime import UTC, datetime, timedelta
from types import SimpleNamespace
from unittest.mock import Mock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base_class import Base
from app.models.knowledge_item import KnowledgeItem
from app.models.knowledge_index_job import KnowledgeIndexJob
from app.services.chroma_service import ChromaServiceError
from app.services.knowledge_index_jobs import (
    KNOWLEDGE_INDEX_JOB_STATUS_DEAD,
    KNOWLEDGE_INDEX_JOB_STATUS_FAILED,
    KNOWLEDGE_INDEX_JOB_STATUS_QUEUED,
    KNOWLEDGE_INDEX_JOB_STATUS_SUCCEEDED,
    enqueue_knowledge_index_job,
    process_knowledge_index_jobs,
)
from app.services.web.news_crawler import CrawlJobConfig, _create_knowledge_from_crawl


class KnowledgeIndexJobTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        Base.metadata.create_all(bind=self.engine)
        self.session_factory = sessionmaker(bind=self.engine)
        self.db = self.session_factory()

    def tearDown(self) -> None:
        self.db.close()
        self.engine.dispose()

    def _add_item(self, *, item_id: int = 1) -> KnowledgeItem:
        item = KnowledgeItem(
            id=item_id,
            title=f"Knowledge {item_id}",
            content=f"Content {item_id}",
            truth_label="credible",
            vector_sync_status="pending",
        )
        self.db.add(item)
        self.db.commit()
        return item

    def test_enqueue_creates_pending_job_and_coalesces_duplicates(self) -> None:
        item = self._add_item()

        first = enqueue_knowledge_index_job(
            self.db,
            item,
            source="unit-test",
        )
        second = enqueue_knowledge_index_job(
            self.db,
            item,
            source="unit-test-repeat",
        )

        jobs = self.db.query(KnowledgeIndexJob).all()
        self.assertEqual(len(jobs), 1)
        self.assertEqual(first.id, second.id)
        self.assertEqual(jobs[0].status, KNOWLEDGE_INDEX_JOB_STATUS_QUEUED)
        self.assertEqual(jobs[0].knowledge_id, item.id)

    def test_enqueue_resets_retry_state_for_existing_failed_job(self) -> None:
        item = self._add_item()
        job = enqueue_knowledge_index_job(
            self.db,
            item,
            source="unit-test",
        )
        job.status = KNOWLEDGE_INDEX_JOB_STATUS_FAILED
        job.attempts = 2
        job.error_message = "old failure"
        self.db.add(job)
        self.db.commit()

        reused = enqueue_knowledge_index_job(
            self.db,
            item,
            source="unit-test-update",
        )

        self.assertEqual(reused.id, job.id)
        self.assertEqual(reused.status, KNOWLEDGE_INDEX_JOB_STATUS_QUEUED)
        self.assertEqual(reused.attempts, 0)
        self.assertIsNone(reused.error_message)

    @patch("app.services.knowledge_index_jobs.sync_knowledge_vector")
    def test_worker_marks_job_succeeded_after_vector_sync(self, mocked_sync) -> None:
        item = self._add_item()
        job = enqueue_knowledge_index_job(self.db, item, source="unit-test")

        def mark_synced(db, item_arg, auto_commit=False, raise_on_failure=True):
            item_arg.vector_sync_status = "synced"
            item_arg.vector_id = f"knowledge:{item_arg.id}:v2"
            db.add(item_arg)
            db.flush()
            return item_arg

        mocked_sync.side_effect = mark_synced

        summary = process_knowledge_index_jobs(self.db, batch_size=10)

        self.assertEqual(summary["processed"], 1)
        self.assertEqual(summary["succeeded"], 1)
        self.db.refresh(job)
        self.db.refresh(item)
        self.assertEqual(job.status, KNOWLEDGE_INDEX_JOB_STATUS_SUCCEEDED)
        self.assertEqual(item.vector_sync_status, "synced")
        self.assertEqual(item.vector_id, "knowledge:1:v2")

    @patch("app.services.knowledge_index_jobs.sync_knowledge_vector")
    def test_worker_keeps_failed_job_retryable_until_max_attempts(
        self,
        mocked_sync,
    ) -> None:
        item = self._add_item()
        job = enqueue_knowledge_index_job(
            self.db,
            item,
            source="unit-test",
            max_attempts=2,
        )
        mocked_sync.side_effect = ChromaServiceError("temporary vector outage")

        first = process_knowledge_index_jobs(self.db, batch_size=10)

        self.assertEqual(first["failed"], 1)
        self.db.refresh(job)
        self.assertEqual(job.status, KNOWLEDGE_INDEX_JOB_STATUS_FAILED)
        self.assertEqual(job.attempts, 1)
        self.assertIn("temporary vector outage", job.error_message)
        self.assertIsNotNone(job.next_attempt_at)

        job.next_attempt_at = datetime.now(UTC).replace(tzinfo=None) - timedelta(
            seconds=1,
        )
        self.db.add(job)
        self.db.commit()

        second = process_knowledge_index_jobs(self.db, batch_size=10)

        self.assertEqual(second["dead"], 1)
        self.db.refresh(job)
        self.assertEqual(job.status, KNOWLEDGE_INDEX_JOB_STATUS_DEAD)
        self.assertEqual(job.attempts, 2)

    @patch("app.services.web.news_crawler.upsert_knowledge_item_vector", create=True)
    def test_crawler_enqueues_index_job_instead_of_writing_chroma_directly(
        self,
        mocked_direct_upsert,
    ) -> None:
        crawl_item = {
            "title": "Crawler title",
            "full_content": "Crawler content",
            "summary": "Crawler summary",
            "url": "https://example.com/news",
            "site_name": "Example",
        }
        job = CrawlJobConfig(name="crawler-test", query="query", freshness="oneDay")

        created = _create_knowledge_from_crawl(
            db=self.db,
            item=crawl_item,
            job=job,
            auto_sync_vector=True,
        )
        self.db.commit()

        jobs = self.db.query(KnowledgeIndexJob).all()
        self.assertEqual(created.vector_sync_status, "pending")
        self.assertEqual(len(jobs), 1)
        self.assertEqual(jobs[0].knowledge_id, created.id)
        mocked_direct_upsert.assert_not_called()


if __name__ == "__main__":
    unittest.main()
