"""merge heads — a1b2c3d4e5f6 + a2b3c4d5e6f7

Revision ID: b3c4d5e6f7a8
Revises: a1b2c3d4e5f6, a2b3c4d5e6f7
Create Date: 2026-06-30 00:00:00.000000

"""
from collections.abc import Sequence

revision: str = "b3c4d5e6f7a8"
down_revision: str | None = ("a1b2c3d4e5f6", "a2b3c4d5e6f7")
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
