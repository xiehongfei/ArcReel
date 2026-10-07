"""add retry_after to tasks

Revision ID: d8f1c4a0b276
Revises: c2e8a91b4f03
Create Date: 2026-09-21 00:30:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from lib.db.migration_helpers import preserve_sqlite_indexes

revision: str = "d8f1c4a0b276"
down_revision: str | Sequence[str] | None = "c2e8a91b4f03"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("retry_after", sa.DateTime(timezone=True), nullable=True))


def downgrade() -> None:
    """Downgrade schema."""
    with preserve_sqlite_indexes("tasks"), op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("retry_after")
