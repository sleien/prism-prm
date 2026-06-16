"""Journal / feeling-tracker templates and entries.

A template defines a customizable set of prompts and a cadence (daily or weekly).
The prompt schema is stored as JSON so users can add mood scales, free-text
prompts, sliders, etc. without a migration. Entries store the answers as JSON
keyed by prompt id, plus a denormalized `mood` for fast trend charts.
"""

from __future__ import annotations

from datetime import date, time

from sqlalchemy import Boolean, Date, ForeignKey, String, Time
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import Cadence, Visibility
from app.db import Base, JSONType, TimestampMixin


class JournalTemplate(Base, TimestampMixin):
    __tablename__ = "journal_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    name: Mapped[str] = mapped_column(String(200), nullable=False)
    cadence: Mapped[str] = mapped_column(String(10), default=Cadence.DAILY, nullable=False)
    active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)

    # List of prompt definitions, e.g.
    #   [{"id": "mood", "type": "scale", "label": "Mood", "min": 1, "max": 10},
    #    {"id": "win", "type": "text", "label": "What went well?"}]
    prompts: Mapped[list] = mapped_column(JSONType, default=list, nullable=False)

    # Optional reminder cadence: local time of day to nudge the user.
    reminder_time: Mapped[time | None] = mapped_column(Time, nullable=True)

    visibility: Mapped[str] = mapped_column(String(20), default=Visibility.PRIVATE, nullable=False)

    entries: Mapped[list[JournalEntry]] = relationship(
        back_populates="template", cascade="all, delete-orphan"
    )


class JournalEntry(Base, TimestampMixin):
    __tablename__ = "journal_entry"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_id: Mapped[int] = mapped_column(
        ForeignKey("journal_template.id", ondelete="CASCADE"), index=True
    )
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    # Optionally about a specific contact (e.g. "how is my relationship with X").
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # The period this entry covers. For daily this is the date; for weekly it is
    # the Monday of the ISO week. `period_key` is the human label (e.g. 2026-W24).
    entry_date: Mapped[date] = mapped_column(Date, nullable=False, index=True)
    period_key: Mapped[str] = mapped_column(String(20), nullable=False, index=True)

    # Answers keyed by prompt id, matching the template's prompt schema.
    data: Mapped[dict] = mapped_column(JSONType, default=dict, nullable=False)
    # Denormalized mood (1..10) for fast trend charts, if the template has one.
    mood: Mapped[int | None] = mapped_column(nullable=True)

    template: Mapped[JournalTemplate] = relationship(back_populates="entries")
