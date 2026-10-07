"""merge upstream and fork migration heads

Revision ID: 9a4c1f7b2e08
Revises: d8f1c4a0b276, e3b81f6c4a27
Create Date: 2026-10-07 00:00:00.000000

"""

from collections.abc import Sequence

revision: str = "9a4c1f7b2e08"
down_revision: str | Sequence[str] | None = ("d8f1c4a0b276", "e3b81f6c4a27")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
