"""Dashboard summary: counts, upcoming events, and mood trend."""

from __future__ import annotations

from datetime import UTC, datetime

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import Contact, Event, JournalEntry, JournalTemplate, User
from app.schemas.summary import MoodPoint, SummaryOut
from app.visibility import visibility_filter

router = APIRouter(prefix="/summary", tags=["summary"])


@router.get("", response_model=SummaryOut)
async def get_summary(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> SummaryOut:
    now = datetime.now(UTC)

    contact_filter = await visibility_filter(session, user, Contact)
    contacts_count = await session.scalar(
        select(func.count(Contact.id)).where(contact_filter)
    )

    event_filter = await visibility_filter(session, user, Event)
    upcoming_events = list(
        (
            await session.scalars(
                select(Event)
                .options(selectinload(Event.attendees), selectinload(Event.reminders))
                .where(event_filter, Event.starts_at >= now)
                .order_by(Event.starts_at)
                .limit(5)
            )
        ).all()
    )
    events_upcoming = await session.scalar(
        select(func.count(Event.id)).where(event_filter, Event.starts_at >= now)
    )

    journal_templates = await session.scalar(
        select(func.count(JournalTemplate.id)).where(JournalTemplate.owner_id == user.id)
    )

    mood_rows = (
        await session.execute(
            select(JournalEntry.entry_date, JournalEntry.mood)
            .where(JournalEntry.owner_id == user.id, JournalEntry.mood.is_not(None))
            .order_by(JournalEntry.entry_date.desc())
            .limit(30)
        )
    ).all()
    mood_trend = [MoodPoint(entry_date=d, mood=m) for d, m in reversed(mood_rows)]

    recent_entries = list(
        (
            await session.scalars(
                select(JournalEntry)
                .where(JournalEntry.owner_id == user.id)
                .order_by(JournalEntry.created_at.desc())
                .limit(5)
            )
        ).all()
    )

    return SummaryOut(
        contacts_count=contacts_count or 0,
        events_upcoming=events_upcoming or 0,
        journal_templates=journal_templates or 0,
        mood_trend=mood_trend,
        upcoming_events=upcoming_events,
        recent_entries=recent_entries,
    )
