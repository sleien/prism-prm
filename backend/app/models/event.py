"""Events, attendees, and reminders.

Events are owned in Prism and pushed to the Nextcloud calendar as VEVENTs;
their reminders ride along as VALARM components so Nextcloud fires them natively.
An attendee may be a Contact (non-user) and/or a Prism User; for GROUP-visibility
events, the attendee users are exactly who may see the event.
"""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from sqlalchemy import Boolean, DateTime, ForeignKey, Numeric, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.constants import ReminderChannel, Visibility
from app.db import Base, JSONType, TimestampMixin


class Event(Base, TimestampMixin):
    __tablename__ = "event"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)

    title: Mapped[str] = mapped_column(String(300), nullable=False)
    description: Mapped[str | None] = mapped_column(Text, nullable=True)
    starts_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    ends_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    all_day: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    # iCalendar RRULE string for recurring events (e.g. "FREQ=WEEKLY;BYDAY=MO").
    rrule: Mapped[str | None] = mapped_column(String(500), nullable=True)

    # Location + geocode (for weather enrichment).
    location: Mapped[str | None] = mapped_column(String(500), nullable=True)
    latitude: Mapped[float | None] = mapped_column(nullable=True)
    longitude: Mapped[float | None] = mapped_column(nullable=True)
    # Cached Open-Meteo forecast at event time.
    weather: Mapped[dict | None] = mapped_column(JSONType, nullable=True)

    # Optional cost.
    cost_amount: Mapped[Decimal | None] = mapped_column(Numeric(12, 2), nullable=True)
    cost_currency: Mapped[str | None] = mapped_column(String(3), nullable=True)

    # Visibility.
    visibility: Mapped[str] = mapped_column(String(20), default=Visibility.PRIVATE, nullable=False)
    group_id: Mapped[int | None] = mapped_column(
        ForeignKey("group.id", ondelete="SET NULL"), nullable=True, index=True
    )

    # --- Nextcloud / CalDAV correlation ---
    nextcloud_uid: Mapped[str | None] = mapped_column(String(255), index=True, nullable=True)
    nextcloud_href: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    etag: Mapped[str | None] = mapped_column(String(255), nullable=True)
    last_synced_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    attendees: Mapped[list[EventAttendee]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )
    reminders: Mapped[list[Reminder]] = relationship(
        back_populates="event", cascade="all, delete-orphan"
    )


class EventAttendee(Base, TimestampMixin):
    __tablename__ = "event_attendee"

    id: Mapped[int] = mapped_column(primary_key=True)
    event_id: Mapped[int] = mapped_column(ForeignKey("event.id", ondelete="CASCADE"), index=True)
    # An attendee is a contact, a user, or both (a contact who is also a user).
    contact_id: Mapped[int | None] = mapped_column(
        ForeignKey("contact.id", ondelete="CASCADE"), nullable=True, index=True
    )
    user_id: Mapped[int | None] = mapped_column(
        ForeignKey("user.id", ondelete="CASCADE"), nullable=True, index=True
    )
    # "accepted" | "declined" | "tentative" | "invited"
    status: Mapped[str] = mapped_column(String(20), default="invited", nullable=False)

    event: Mapped[Event] = relationship(back_populates="attendees")


class Reminder(Base, TimestampMixin):
    """A point-in-time reminder. May be attached to an event, to a journal
    template (recurring cadence), or stand alone. CALDAV reminders are written
    into Nextcloud as VALARMs; others are dispatched by the in-app scheduler."""

    __tablename__ = "reminder"

    id: Mapped[int] = mapped_column(primary_key=True)
    owner_id: Mapped[int] = mapped_column(ForeignKey("user.id", ondelete="CASCADE"), index=True)
    event_id: Mapped[int | None] = mapped_column(
        ForeignKey("event.id", ondelete="CASCADE"), nullable=True, index=True
    )
    journal_template_id: Mapped[int | None] = mapped_column(
        ForeignKey("journal_template.id", ondelete="CASCADE"), nullable=True, index=True
    )

    message: Mapped[str] = mapped_column(String(500), nullable=False)
    remind_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)
    channel: Mapped[str] = mapped_column(String(20), default=ReminderChannel.CALDAV, nullable=False)

    # Dispatch / push bookkeeping.
    dispatched_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    done: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    event: Mapped[Event | None] = relationship(back_populates="reminders")
