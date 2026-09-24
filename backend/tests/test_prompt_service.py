import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker

from app.db.base import Base
from app.models.prompt_template import PromptTemplate
from app.schemas.prompt import PromptTemplateCreate, PromptTemplateUpdate
from app.services.prompt_service import (
    PromptTemplateDefaultDeleteError,
    PromptTemplateDisabledError,
    create_prompt_template,
    delete_prompt_template,
    disable_prompt_template,
    enable_prompt_template,
    get_default_prompt_content,
    set_default_prompt_template,
    update_prompt_template,
)
from app.services.prompt_template_validator import PromptTemplateValidationError


def _payload(
    name: str,
    *,
    prompt_type: str = "news_credibility",
    content: str = "Analyze {title} with {content} and {evidence_list}",
    is_default: bool = False,
    status: str = "enabled",
) -> PromptTemplateCreate:
    return PromptTemplateCreate(
        name=name,
        type=prompt_type,
        content=content,
        is_default=is_default,
        status=status,
    )


class PromptTemplateServiceTestCase(unittest.TestCase):
    def setUp(self) -> None:
        self.engine = create_engine("sqlite:///:memory:")
        self.addCleanup(self.engine.dispose)
        TestingSessionLocal = sessionmaker(bind=self.engine)
        Base.metadata.create_all(bind=self.engine)
        self.db = TestingSessionLocal()
        self.addCleanup(self.db.close)

    def test_same_type_keeps_only_one_default(self) -> None:
        first = create_prompt_template(
            self.db,
            _payload("First", is_default=True),
            created_by=None,
        )
        second = create_prompt_template(
            self.db,
            _payload(
                "Second",
                content="Second {title} {content} {evidence_list}",
                is_default=True,
            ),
            created_by=None,
        )

        self.db.refresh(first)
        self.assertFalse(first.is_default)
        self.assertTrue(second.is_default)
        self.assertEqual(
            get_default_prompt_content(self.db),
            "Second {title} {content} {evidence_list}",
        )

    def test_create_news_prompt_missing_title_placeholder_fails(self) -> None:
        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{title\}"):
            create_prompt_template(
                self.db,
                _payload("Missing title", content="{content} {evidence_list}"),
                created_by=None,
            )

    def test_create_news_prompt_missing_content_placeholder_fails(self) -> None:
        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{content\}"):
            create_prompt_template(
                self.db,
                _payload("Missing content", content="{title} {evidence_list}"),
                created_by=None,
            )

    def test_create_news_prompt_missing_evidence_placeholder_fails(self) -> None:
        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{evidence_list\}"):
            create_prompt_template(
                self.db,
                _payload("Missing evidence", content="{title} {content}"),
                created_by=None,
            )

    def test_create_valid_news_prompt_succeeds(self) -> None:
        template = create_prompt_template(
            self.db,
            _payload("Valid"),
            created_by=None,
        )

        self.assertIsNotNone(template.id)

    def test_edit_default_prompt_missing_placeholder_fails(self) -> None:
        template = create_prompt_template(
            self.db,
            _payload("Default", is_default=True),
            created_by=None,
        )

        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{evidence_list\}"):
            update_prompt_template(
                self.db,
                template.id,
                PromptTemplateUpdate(content="{title} {content}"),
            )

    def test_invalid_legacy_prompt_cannot_be_set_default(self) -> None:
        template = self._insert_legacy_invalid_template()

        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{content\}"):
            set_default_prompt_template(self.db, template.id)

    def test_invalid_legacy_prompt_cannot_be_enabled(self) -> None:
        template = self._insert_legacy_invalid_template(status="disabled")

        with self.assertRaisesRegex(PromptTemplateValidationError, r"\{title\}"):
            enable_prompt_template(self.db, template.id)

    def test_invalid_legacy_default_is_ignored_for_safe_fallback(self) -> None:
        self._insert_legacy_invalid_template(is_default=True)

        with self.assertLogs("app.services.prompt_service", level="ERROR") as captured:
            content = get_default_prompt_content(self.db)

        self.assertEqual(content, "")
        self.assertTrue(
            any(
                "Default prompt template validation failed, fallback to built-in prompt."
                in message
                for message in captured.output
            )
        )

    def test_missing_enabled_default_logs_builtin_fallback(self) -> None:
        with self.assertLogs("app.services.prompt_service", level="WARNING") as captured:
            content = get_default_prompt_content(self.db)

        self.assertEqual(content, "")
        self.assertTrue(
            any(
                "No enabled default prompt template found, fallback to built-in prompt."
                in message
                for message in captured.output
            )
        )

    def test_disabled_template_cannot_be_default(self) -> None:
        disabled = create_prompt_template(
            self.db,
            _payload("Disabled", status="disabled"),
            created_by=None,
        )

        with self.assertRaises(PromptTemplateDisabledError):
            set_default_prompt_template(self.db, disabled.id)

    def test_disabling_default_clears_default_and_uses_fallback_signal(self) -> None:
        default_template = create_prompt_template(
            self.db,
            _payload("Default", is_default=True),
            created_by=None,
        )

        disabled = disable_prompt_template(self.db, default_template.id)

        self.assertEqual(disabled.status, "disabled")
        self.assertFalse(disabled.is_default)
        self.assertEqual(get_default_prompt_content(self.db), "")

    def test_default_template_cannot_be_deleted(self) -> None:
        default_template = create_prompt_template(
            self.db,
            _payload("Default", is_default=True),
            created_by=None,
        )

        with self.assertRaises(PromptTemplateDefaultDeleteError):
            delete_prompt_template(self.db, default_template.id)

    def _insert_legacy_invalid_template(
        self,
        is_default: bool = False,
        status: str = "enabled",
    ) -> PromptTemplate:
        template = PromptTemplate(
            name="Legacy invalid",
            type="news_credibility",
            content="Only analyze the role without news inputs",
            is_default=is_default,
            status=status,
        )
        self.db.add(template)
        self.db.commit()
        self.db.refresh(template)
        return template


if __name__ == "__main__":
    unittest.main()
