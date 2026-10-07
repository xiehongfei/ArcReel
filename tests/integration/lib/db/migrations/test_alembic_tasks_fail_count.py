"""Alembic migration for tasks.fail_count."""

from __future__ import annotations

from pathlib import Path

import sqlalchemy as sa

from alembic import command

REVISION = "c2e8a91b4f03"
DOWN_REVISION = "7c1e5b93a204"


def _columns(db_path: Path) -> set[str]:
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        rows = conn.execute(sa.text("PRAGMA table_info(tasks)")).fetchall()
    engine.dispose()
    return {row[1] for row in rows}


def test_upgrade_adds_fail_count_defaulting_to_zero(alembic_cfg) -> None:
    cfg, db_path = alembic_cfg
    command.upgrade(cfg, DOWN_REVISION)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        conn.execute(
            sa.text(
                "INSERT INTO tasks (task_id, project_name, task_type, media_type, resource_id, status, "
                "source, queued_at, updated_at) VALUES ('T-old', 'demo', 'video', 'video', 'E1S01', "
                "'queued', 'webui', '2026-09-20 00:00:00', '2026-09-20 00:00:00')"
            )
        )
    engine.dispose()

    command.upgrade(cfg, REVISION)

    assert "fail_count" in _columns(db_path)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        assert conn.execute(sa.text("SELECT fail_count FROM tasks WHERE task_id='T-old'")).scalar() == 0
    engine.dispose()


def test_downgrade_drops_fail_count_and_preserves_active_dedupe_index(alembic_cfg) -> None:
    cfg, db_path = alembic_cfg
    command.upgrade(cfg, REVISION)
    command.downgrade(cfg, DOWN_REVISION)

    assert "fail_count" not in _columns(db_path)
    engine = sa.create_engine(f"sqlite:///{db_path}")
    with engine.begin() as conn:
        indexes = {row[1] for row in conn.execute(sa.text("PRAGMA index_list('tasks')")).fetchall()}
    engine.dispose()
    assert "idx_tasks_dedupe_active" in indexes
