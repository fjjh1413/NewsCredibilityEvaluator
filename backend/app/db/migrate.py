from __future__ import annotations

from alembic import command

from app.db.migration_guard import build_alembic_config


def upgrade_database(revision: str = "head") -> None:
    command.upgrade(build_alembic_config(), revision)


def main() -> None:
    upgrade_database()
    print("[ok] Database schema upgraded to Alembic head.")


if __name__ == "__main__":
    main()
