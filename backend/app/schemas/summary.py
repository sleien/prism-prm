"""Dashboard summary schema."""

from __future__ import annotations

from datetime import date

from pydantic import BaseModel

from app.schemas.event import EventOut
from app.schemas.journal import JournalEntryOut


class MoodPoint(BaseModel):
    entry_date: date
    mood: int


class SummaryOut(BaseModel):
    contacts_count: int
    events_count: int
    journal_templates: int
    mood_trend: list[MoodPoint]
    recent_events: list[EventOut]
    recent_entries: list[JournalEntryOut]
