from __future__ import annotations

from pathlib import Path

from alembic.config import Config
from alembic.runtime.migration import MigrationContext
from alembic.script import ScriptDirectory

from app.core.config import BASE_DIR
from app.db.session import engine


def build_alembic_config() -> Config:
    config = Config(str(Path(BASE_DIR) / "alembic.ini"))
    config.set_main_option("script_location", str(Path(BASE_DIR) / "alembic"))
    return config


def get_head_revisions() -> set[str]:
    script = ScriptDirectory.from_config(build_alembic_config())
    return set(script.get_heads())


def get_current_revisions() -> set[str]:
    with engine.connect() as connection:
        context = MigrationContext.configure(connection)
        return set(context.get_current_heads())


def assert_database_at_head() -> None:
    head_revisions = get_head_revisions()
    current_revisions = get_current_revisions()
    if current_revisions == head_revisions:
        return

    expected = ", ".join(sorted(head_revisions)) or "<none>"
    current = ", ".join(sorted(current_revisions)) or "<none>"
    if not current_revisions:
        raise RuntimeError(
            "Database schema is not managed by Alembic. Run `alembic upgrade head` "
            "before initializing data. For an existing manually migrated database, "
            "verify the schema first and stamp the matching revision."
        )

    raise RuntimeError(
        "Database schema is not up to date. "
        f"Current revision(s): {current}; expected head revision(s): {expected}. "
        "Run `alembic upgrade head` before initializing data."
    )
