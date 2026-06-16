"""Journal / feeling-tracker schemas."""

from __future__ import annotations

from datetime import date, datetime, time

from pydantic import BaseModel, ConfigDict, Field

from app.constants import Cadence, Visibility


class Prompt(BaseModel):
    """A single customizable question in a journal template.

    type: "scale" (min..max), "text", "number", or "boolean".
    """

    id: str
    type: str = "text"
    label: str
    min: int | None = None
    max: int | None = None


class JournalTemplateBase(BaseModel):
    name: str = Field(max_length=200)
    cadence: Cadence = Cadence.DAILY
    prompts: list[Prompt] = Field(default_factory=list)
    reminder_time: time | None = None
    visibility: Visibility = Visibility.PRIVATE
    active: bool = True


class JournalTemplateCreate(JournalTemplateBase):
    pass


class JournalTemplateUpdate(BaseModel):
    name: str | None = Field(default=None, max_length=200)
    cadence: Cadence | None = None
    prompts: list[Prompt] | None = None
    reminder_time: time | None = None
    visibility: Visibility | None = None
    active: bool | None = None


class JournalTemplateOut(JournalTemplateBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    owner_id: int


class JournalEntryIn(BaseModel):
    # Answers keyed by prompt id. entry_date defaults to today on the server.
    data: dict = Field(default_factory=dict)
    entry_date: date | None = None
    contact_id: int | None = None


class JournalEntryOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    template_id: int
    owner_id: int
    contact_id: int | None = None
    entry_date: date
    period_key: str
    data: dict
    mood: int | None = None
    created_at: datetime
