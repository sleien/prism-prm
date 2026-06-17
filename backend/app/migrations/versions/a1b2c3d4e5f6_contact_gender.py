"""contact_gender

Revision ID: a1b2c3d4e5f6
Revises: 6e68afab217f
Create Date: 2026-06-17 00:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'a1b2c3d4e5f6'
down_revision: str | None = '6e68afab217f'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column('contact', sa.Column('gender', sa.String(length=20), nullable=True))


def downgrade() -> None:
    op.drop_column('contact', 'gender')
