"""Event request/response schemas."""

from __future__ import annotations

from datetime import datetime
from decimal import Decimal

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.constants import Visibility


class ReminderIn(BaseModel):
    # Minutes before the event start to fire the reminder (0 .. ~1 year).
    minutes_before: int = Field(default=60, ge=0, le=525600)
    message: str | None = Field(default=None, max_length=500)


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
    title: str = Field(max_length=300)
    description: str | None = None
    starts_at: datetime
    ends_at: datetime | None = None
    all_day: bool = False
    rrule: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    cost_amount: Decimal | None = Field(default=None, ge=0, le=10**10)
    cost_currency: str | None = Field(default=None, max_length=3)
    visibility: Visibility = Visibility.PRIVATE
    group_id: int | None = None


class EventCreate(EventBase):
    attendee_contact_ids: list[int] = Field(default_factory=list)
    reminders: list[ReminderIn] = Field(default_factory=list)

    # Validate time order on input only — never on EventOut serialization, so a
    # pre-existing row with odd times can still be read back.
    @model_validator(mode="after")
    def _check_times(self):
        if self.ends_at and self.ends_at < self.starts_at:
            raise ValueError("ends_at must not be before starts_at")
        return self


class EventUpdate(BaseModel):
    title: str | None = Field(default=None, max_length=300)
    description: str | None = None
    starts_at: datetime | None = None
    ends_at: datetime | None = None
    all_day: bool | None = None
    rrule: str | None = Field(default=None, max_length=500)
    location: str | None = Field(default=None, max_length=500)
    cost_amount: Decimal | None = Field(default=None, ge=0, le=10**10)
    cost_currency: str | None = Field(default=None, max_length=3)
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
