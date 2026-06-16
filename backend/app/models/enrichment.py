"""Contact enrichment: relationships and life events, with per-user customizable
type catalogs.

Type catalogs (RelationshipType, LifeEventType) are owned per user and seeded
with sensible defaults on first use, so each user can tailor their own
vocabulary. The actual relationship/event rows denormalize their labels so they
survive edits or deletion of a type.
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import Date, ForeignKey, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from app.db import Base, TimestampMixin


class RelationshipType(Base, TimestampMixin):
    """A user-defined kind of relationship, e.g. Parent (reverse: Child)."""

    __tablename__ = "relationship_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    # Label seen from the other side. Null/equal => symmetric (e.g. Sibling).
    reverse_name: Mapped[str | None] = mapped_column(String(80), nullable=True)


class ContactRelationship(Base, TimestampMixin):
    """A directed link `from_contact -[name]-> to_contact` (labels denormalized)."""

    __tablename__ = "contact_relationship"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    from_contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    to_contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    reverse_name: Mapped[str | None] = mapped_column(String(80), nullable=True)


class LifeEventType(Base, TimestampMixin):
    """A user-defined kind of milestone, e.g. "Got married" 💍."""

    __tablename__ = "life_event_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(120), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)


class EventType(Base, TimestampMixin):
    """A user-defined kind of event, e.g. "Birthday" 🎂 or "Dinner" 🍽️."""

    __tablename__ = "event_type"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    name: Mapped[str] = mapped_column(String(80), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)


class ContactLifeEvent(Base, TimestampMixin):
    """A dated milestone on a contact's timeline (label denormalized)."""

    __tablename__ = "contact_life_event"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    contact_id: Mapped[int] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), index=True
    )
    title: Mapped[str] = mapped_column(String(120), nullable=False)
    emoji: Mapped[str | None] = mapped_column(String(16), nullable=True)
    happened_on: Mapped[date | None] = mapped_column(Date, nullable=True)
    note: Mapped[str | None] = mapped_column(Text, nullable=True)
