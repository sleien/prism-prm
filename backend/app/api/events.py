"""Event CRUD with attendees, reminders, and push to the Nextcloud calendar."""

from __future__ import annotations

from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.config import settings
from app.constants import ReminderChannel
from app.db import get_session
from app.integrations.nextcloud import DavError
from app.models import Contact, Event, EventAttendee, Reminder, User
from app.schemas.event import EventCreate, EventOut, EventUpdate, ReminderIn
from app.services.calendar_sync import delete_event_remote, push_event
from app.services.weather import enrich_event_weather
from app.visibility import event_visibility_filter, validate_group_choice, visibility_filter

router = APIRouter(prefix="/events", tags=["events"])

_WITH_RELATIONS = (selectinload(Event.attendees), selectinload(Event.reminders))


async def _load(session: AsyncSession, event_id: int) -> Event | None:
    return await session.scalar(
        select(Event).options(*_WITH_RELATIONS).where(Event.id == event_id)
    )


async def _visible_contact_ids(session: AsyncSession, user: User, ids: list[int]) -> list[int]:
    """Keep only the contact ids the user may actually see."""
    if not ids:
        return []
    filt = await visibility_filter(session, user, Contact)
    rows = await session.scalars(select(Contact.id).where(Contact.id.in_(ids), filt))
    return list(rows.all())


async def _attendee_emails(session: AsyncSession, contact_ids: list[int]) -> list[str]:
    emails: list[str] = []
    for cid in contact_ids:
        contact = await session.get(Contact, cid)
        if contact and contact.emails:
            emails.append(contact.emails[0]["value"])
    return emails


async def _add_attendees(session: AsyncSession, event_id: int, contact_ids: list[int]) -> None:
    """Attach contacts as attendees, linking to a Prism user when a contact's
    email matches one (so they can see "group = attended" events)."""
    for cid in contact_ids:
        contact = await session.get(Contact, cid)
        user_id: int | None = None
        for item in contact.emails if contact else []:
            email = item.get("value")
            if not email:
                continue
            match = await session.scalar(select(User).where(User.email == email.lower()))
            if match:
                user_id = match.id
                break
        session.add(EventAttendee(event_id=event_id, contact_id=cid, user_id=user_id))


def _build_reminders(owner_id: int, event: Event, reminders_in: list[ReminderIn]) -> list[Reminder]:
    out: list[Reminder] = []
    for r in reminders_in:
        out.append(
            Reminder(
                owner_id=owner_id,
                message=r.message or f"Reminder: {event.title}",
                remind_at=event.starts_at - timedelta(minutes=r.minutes_before),
                channel=ReminderChannel.CALDAV,
            )
        )
    return out


async def _sync_to_calendar(session: AsyncSession, event: Event, contact_ids: list[int]) -> None:
    if settings.weather_enabled:
        await enrich_event_weather(event)
    emails = await _attendee_emails(session, contact_ids)
    await push_event(event, list(event.reminders), emails)
    await session.commit()


@router.get("", response_model=list[EventOut])
async def list_events(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[Event]:
    filt = await event_visibility_filter(session, user)
    rows = await session.scalars(
        select(Event).options(*_WITH_RELATIONS).where(filt).order_by(Event.starts_at)
    )
    return list(rows.all())


@router.get("/{event_id}", response_model=EventOut)
async def get_event(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Event:
    filt = await event_visibility_filter(session, user)
    event = await session.scalar(
        select(Event).options(*_WITH_RELATIONS).where(Event.id == event_id, filt)
    )
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    return event


@router.post("", response_model=EventOut, status_code=status.HTTP_201_CREATED)
async def create_event(
    payload: EventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Event:
    await validate_group_choice(
        session, user, payload.visibility, payload.group_id, require_group=False
    )
    data = payload.model_dump(exclude={"attendee_contact_ids", "reminders"})
    event = Event(owner_id=user.id, **data)
    session.add(event)
    await session.flush()

    contact_ids = await _visible_contact_ids(session, user, payload.attendee_contact_ids)
    await _add_attendees(session, event.id, contact_ids)
    for reminder in _build_reminders(user.id, event, payload.reminders):
        reminder.event_id = event.id
        session.add(reminder)

    await session.commit()
    event = await _load(session, event.id)  # type: ignore[assignment]
    await _sync_to_calendar(session, event, contact_ids)
    return await _load(session, event.id)  # type: ignore[return-value]


@router.patch("/{event_id}", response_model=EventOut)
async def update_event(
    event_id: int,
    payload: EventUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Event:
    event = await _load(session, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    if event.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your event")

    updates = payload.model_dump(exclude_unset=True, exclude={"attendee_contact_ids", "reminders"})
    for key, value in updates.items():
        setattr(event, key, value)
    await validate_group_choice(
        session, user, event.visibility, event.group_id, require_group=False
    )

    contact_ids: list[int] | None = None
    if payload.attendee_contact_ids is not None:
        contact_ids = await _visible_contact_ids(session, user, payload.attendee_contact_ids)
        for a in list(event.attendees):
            await session.delete(a)
        await session.flush()
        await _add_attendees(session, event.id, contact_ids)
    if payload.reminders is not None:
        for r in list(event.reminders):
            await session.delete(r)
        await session.flush()
        for reminder in _build_reminders(user.id, event, payload.reminders):
            reminder.event_id = event.id
            session.add(reminder)

    await session.commit()
    event = await _load(session, event_id)  # type: ignore[assignment]
    if contact_ids is None:
        contact_ids = [a.contact_id for a in event.attendees if a.contact_id]
    await _sync_to_calendar(session, event, contact_ids)
    return await _load(session, event_id)  # type: ignore[return-value]


@router.delete("/{event_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_event(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    event = await session.get(Event, event_id)
    if event is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")
    if event.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your event")
    try:
        await delete_event_remote(event)
    except DavError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Could not delete from Nextcloud: {exc}"
        ) from exc
    await session.delete(event)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)
