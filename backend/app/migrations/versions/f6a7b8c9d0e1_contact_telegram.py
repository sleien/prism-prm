"""contact_telegram

Revision ID: f6a7b8c9d0e1
Revises: e5f6a7b8c9d0
Create Date: 2026-06-17 04:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'f6a7b8c9d0e1'
down_revision: str | None = 'e5f6a7b8c9d0'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('contact', sa.Column('telegram', sa.String(length=100), nullable=True))


def downgrade() -> None:
    op.drop_column('contact', 'telegram')
