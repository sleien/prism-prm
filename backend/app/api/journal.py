"""Journal / feeling-tracker: templates and per-period entries (owner-scoped)."""

from __future__ import annotations

from datetime import date

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import JournalEntry, JournalTemplate, User
from app.schemas.journal import (
    JournalEntryIn,
    JournalEntryOut,
    JournalTemplateCreate,
    JournalTemplateOut,
    JournalTemplateUpdate,
)
from app.services.journal import (
    delete_journal_reminder,
    extract_mood,
    period_for,
    push_journal_reminder,
)

router = APIRouter(prefix="/journal", tags=["journal"])


async def _own_template(session: AsyncSession, user: User, template_id: int) -> JournalTemplate:
    tpl = await session.get(JournalTemplate, template_id)
    if tpl is None or tpl.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Template not found")
    return tpl


@router.get("/templates", response_model=list[JournalTemplateOut])
async def list_templates(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[JournalTemplate]:
    rows = await session.scalars(
        select(JournalTemplate)
        .where(JournalTemplate.owner_id == user.id)
        .order_by(JournalTemplate.id)
    )
    return list(rows.all())


@router.post("/templates", response_model=JournalTemplateOut, status_code=status.HTTP_201_CREATED)
async def create_template(
    payload: JournalTemplateCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JournalTemplate:
    tpl = JournalTemplate(
        owner_id=user.id,
        name=payload.name,
        cadence=payload.cadence,
        prompts=[p.model_dump() for p in payload.prompts],
        reminder_time=payload.reminder_time,
        visibility=payload.visibility,
        active=payload.active,
    )
    session.add(tpl)
    await session.commit()
    await session.refresh(tpl)
    await push_journal_reminder(tpl)
    return tpl


@router.patch("/templates/{template_id}", response_model=JournalTemplateOut)
async def update_template(
    template_id: int,
    payload: JournalTemplateUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JournalTemplate:
    tpl = await _own_template(session, user, template_id)
    updates = payload.model_dump(exclude_unset=True)
    if "prompts" in updates and payload.prompts is not None:
        updates["prompts"] = [p.model_dump() for p in payload.prompts]
    for key, value in updates.items():
        setattr(tpl, key, value)
    await session.commit()
    await session.refresh(tpl)
    if tpl.active and tpl.reminder_time:
        await push_journal_reminder(tpl)
    else:
        await delete_journal_reminder(tpl.id)
    return tpl


@router.delete("/templates/{template_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_template(
    template_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    tpl = await _own_template(session, user, template_id)
    await delete_journal_reminder(tpl.id)
    await session.delete(tpl)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.get("/templates/{template_id}/entries", response_model=list[JournalEntryOut])
async def list_entries(
    template_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[JournalEntry]:
    await _own_template(session, user, template_id)
    rows = await session.scalars(
        select(JournalEntry)
        .where(JournalEntry.template_id == template_id, JournalEntry.owner_id == user.id)
        .order_by(JournalEntry.entry_date.desc())
    )
    return list(rows.all())


@router.put("/templates/{template_id}/entries", response_model=JournalEntryOut)
async def upsert_entry(
    template_id: int,
    payload: JournalEntryIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> JournalEntry:
    """Create or update the entry for the period containing entry_date (today by default)."""
    tpl = await _own_template(session, user, template_id)
    entry_date, period_key = period_for(payload.entry_date or date.today(), tpl.cadence)
    mood = extract_mood(tpl.prompts, payload.data)

    entry = await session.scalar(
        select(JournalEntry).where(
            JournalEntry.template_id == template_id,
            JournalEntry.owner_id == user.id,
            JournalEntry.period_key == period_key,
        )
    )
    if entry is None:
        entry = JournalEntry(
            template_id=template_id,
            owner_id=user.id,
            entry_date=entry_date,
            period_key=period_key,
        )
        session.add(entry)
    entry.data = payload.data
    entry.mood = mood
    entry.contact_id = payload.contact_id
    await session.commit()
    await session.refresh(entry)
    return entry
