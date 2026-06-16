"""Event request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Visibility


class ReminderIn(BaseModel):
    # Minutes before the event start to fire the reminder.
    minutes_before: int = 60
    message: str | None = None


class ReminderOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    message: str
    remind_at: datetime
    channel: str
    done: bool


class AttendeeOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    contact_id: int | None = None
    user_id: int | None = None
    status: str


class EventBase(BaseModel):
    title: str
    description: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    rrule: str | None = None
    location: str | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    visibility: Visibility = Visibility.PRIVATE
    group_id: int | None = None


class EventCreate(EventBase):
    attendee_contact_ids: list[int] = Field(default_factory=list)
    reminders: list[ReminderIn] = Field(default_factory=list)


class EventUpdate(BaseModel):
    title: str | None = None
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    rrule: str | None = None
    location: str | None = None
    cost_amount: Decimal | None = None
    cost_currency: str | None = None
    visibility: Visibility | None = None
    group_id: int | None = None
    attendee_contact_ids: list[int] | None = None
    reminders: list[ReminderIn] | None = None


class EventOut(EventBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int
    attendees: list[AttendeeOut] = Field(default_factory=list)
    reminders: list[ReminderOut] = Field(default_factory=list)
    nextcloud_uid: str | None = None
    last_synced_at: datetime | None = None
    weather: dict | None = None
