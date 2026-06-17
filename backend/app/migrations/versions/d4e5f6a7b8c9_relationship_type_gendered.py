"""relationship_type_gendered

Revision ID: d4e5f6a7b8c9
Revises: c3d4e5f6a7b8
Create Date: 2026-06-17 02:00:00.000000
"""
from collections.abc import Sequence

from alembic import op
import sqlalchemy as sa


revision: str = 'd4e5f6a7b8c9'
down_revision: str | None = 'c3d4e5f6a7b8'
branch_labels: str | Sequence[str] | None = None
depends_on: str | Sequence[str] | None = None

# Backfill gendered labels onto existing default-named types so already-created
# relationships keep rendering Father/Mother/etc. without a manual step.
# (name, name_male, name_female, reverse_name_male, reverse_name_female)
_DEFAULTS = [
    ("Parent", "Father", "Mother", "Son", "Daughter"),
    ("Sibling", "Brother", "Sister", None, None),
    ("Grandparent", "Grandfather", "Grandmother", "Grandson", "Granddaughter"),
]


def upgrade() -> None:
    for col in ("name_male", "name_female", "reverse_name_male", "reverse_name_female"):
        op.add_column("relationship_type", sa.Column(col, sa.String(length=80), nullable=True))

    rt = sa.table(
        "relationship_type",
        sa.column("name", sa.String),
        sa.column("name_male", sa.String),
        sa.column("name_female", sa.String),
        sa.column("reverse_name_male", sa.String),
        sa.column("reverse_name_female", sa.String),
    )
    for name, nm, nf, rm, rf in _DEFAULTS:
        op.execute(
            rt.update()
            .where(rt.c.name == name)
            .values(name_male=nm, name_female=nf, reverse_name_male=rm, reverse_name_female=rf)
        )


def downgrade() -> None:
    for col in ("reverse_name_female", "reverse_name_male", "name_female", "name_male"):
        op.drop_column("relationship_type", col)
