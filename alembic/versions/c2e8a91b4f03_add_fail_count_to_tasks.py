"""add fail_count to tasks

Revision ID: c2e8a91b4f03
Revises: 7c1e5b93a204
Create Date: 2026-09-20 21:50:00.000000

"""

from collections.abc import Sequence

import sqlalchemy as sa

from alembic import op
from lib.db.migration_helpers import preserve_sqlite_indexes

revision: str = "c2e8a91b4f03"
down_revision: str | Sequence[str] | None = "7c1e5b93a204"
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.add_column(sa.Column("fail_count", sa.Integer(), server_default="0", nullable=False))


def downgrade() -> None:
    """Downgrade schema."""
    with preserve_sqlite_indexes("tasks"), op.batch_alter_table("tasks", schema=None) as batch_op:
        batch_op.drop_column("fail_count")
