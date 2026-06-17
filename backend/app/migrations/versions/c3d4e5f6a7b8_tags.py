"""tags

Revision ID: c3d4e5f6a7b8
Revises: b2c3d4e5f6a7
Create Date: 2026-06-17 01:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'c3d4e5f6a7b8'
down_revision: str | None = 'b2c3d4e5f6a7'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None


def upgrade() -> None:
    op.create_table(
        'tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('owner_id', sa.Integer(), nullable=False),
        sa.Column('name', sa.String(length=80), nullable=False),
        sa.Column('color', sa.String(length=20), nullable=True),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['owner_id'], ['user.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('owner_id', 'name', name='uq_tag_owner_name'),
    )
    op.create_index(op.f('ix_tag_owner_id'), 'tag', ['owner_id'], unique=False)
    op.create_table(
        'contact_tag',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('contact_id', sa.Integer(), nullable=False),
        sa.Column('tag_id', sa.Integer(), nullable=False),
        sa.Column('created_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.Column('updated_at', sa.DateTime(timezone=True), server_default=sa.text('now()'), nullable=False),
        sa.ForeignKeyConstraint(['contact_id'], ['contact.id'], ondelete='CASCADE'),
        sa.ForeignKeyConstraint(['tag_id'], ['tag.id'], ondelete='CASCADE'),
        sa.PrimaryKeyConstraint('id'),
        sa.UniqueConstraint('contact_id', 'tag_id', name='uq_contact_tag'),
    )
    op.create_index(op.f('ix_contact_tag_contact_id'), 'contact_tag', ['contact_id'], unique=False)
    op.create_index(op.f('ix_contact_tag_tag_id'), 'contact_tag', ['tag_id'], unique=False)


def downgrade() -> None:
    op.drop_index(op.f('ix_contact_tag_tag_id'), table_name='contact_tag')
    op.drop_index(op.f('ix_contact_tag_contact_id'), table_name='contact_tag')
    op.drop_table('contact_tag')
    op.drop_index(op.f('ix_tag_owner_id'), table_name='tag')
    op.drop_table('tag')
