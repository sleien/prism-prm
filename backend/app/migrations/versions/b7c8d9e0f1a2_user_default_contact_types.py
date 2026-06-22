"""user_default_contact_types

Revision ID: b7c8d9e0f1a2
Revises: a7b8c9d0e1f2
Create Date: 2026-06-22 08:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'b7c8d9e0f1a2'
down_revision: str | None = 'a7b8c9d0e1f2'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.add_column(
        'user',
        sa.Column('default_phone_type', sa.String(length=20), nullable=False, server_default='mobile'),
    )
    op.add_column(
        'user',
        sa.Column('default_email_type', sa.String(length=20), nullable=False, server_default='home'),
    )
    op.add_column(
        'user',
        sa.Column('default_address_type', sa.String(length=20), nullable=False, server_default='home'),
    )


def downgrade() -> None:
    op.drop_column('user', 'default_address_type')
    op.drop_column('user', 'default_email_type')
    op.drop_column('user', 'default_phone_type')
