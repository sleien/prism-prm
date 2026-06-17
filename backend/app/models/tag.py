"""Per-user contact tags and their contact associations.

Tags are an owner's organizational labels (like Monica's tags). A tag belongs to
a user; the contact_tag table links a contact to one of that user's tags.
"""

from __future__ import annotations

from sqlalchemy import ForeignKey, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class Tag(Base, TimestampMixin):
    __tablename__ = "tag"
    __table_args__ = (UniqueConstraint("owner_id", "name", name="uq_tag_owner_name"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Optional display color (hex like "#22c55e"); UI falls back to a default.
    color: Mapped[str | None] = mapped_column(String(20), nullable=True)


class ContactTag(Base, TimestampMixin):
    __tablename__ = "contact_tag"
    __table_args__ = (UniqueConstraint("contact_id", "tag_id", name="uq_contact_tag"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    tag_id: Mapped[int] = mapped_column(ForeignKey("tag.id", ondelete="CASCADE"), index=True)
