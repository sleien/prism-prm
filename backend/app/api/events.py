"""Event CRUD with attendees, reminders, and push to the Nextcloud calendar."""

from __future__ import annotations

import uuid
from datetime import timedelta

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession
from sqlalchemy.orm import selectinload

from app.auth.deps import get_current_user
from app.config import settings
from app.constants import ReminderChannel, Visibility
from app.db import get_session
from app.integrations.nextcloud import DavError
from app.models import Contact, Event, EventAttendee, EventNote, Reminder, User
from app.schemas.contact import ContactOut
from app.schemas.event import (
    AttendeeDetailOut,
    EventCreate,
    EventNoteIn,
    EventNoteOut,
    EventOut,
    EventUpdate,
    ReminderIn,
)
from app.services.calendar_sync import delete_event_remote, push_event
from app.services.geocode import geocode_contact
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
    """Attach contacts as attendees. If a contact is explicitly linked to a Prism
    user, that user is recorded so they can see the event (cross-user sharing)."""
    for cid in contact_ids:
        contact = await session.get(Contact, cid)
        session.add(
            EventAttendee(
                event_id=event_id,
                contact_id=cid,
                user_id=(contact.linked_user_id if contact else None),
            )
        )


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


async def _sync_to_calendar(
    session: AsyncSession, owner: User, event: Event, contact_ids: list[int]
) -> None:
    if settings.weather_enabled:
        await enrich_event_weather(event)
    emails = await _attendee_emails(session, contact_ids)
    await push_event(owner, event, list(event.reminders), emails)
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
    await _sync_to_calendar(session, user, event, contact_ids)
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
    await _sync_to_calendar(session, user, event, contact_ids)
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
        await delete_event_remote(user, event)
    except DavError as exc:
        raise HTTPException(
            status.HTTP_502_BAD_GATEWAY, f"Could not delete from Nextcloud: {exc}"
        ) from exc
    await session.delete(event)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


# --- per-user private notes -------------------------------------------------


async def _ensure_event_visible(session: AsyncSession, user: User, event_id: int) -> None:
    filt = await event_visibility_filter(session, user)
    if await session.scalar(select(Event.id).where(Event.id == event_id, filt)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Event not found")


@router.get("/{event_id}/note", response_model=EventNoteOut)
async def get_note(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventNoteOut:
    await _ensure_event_visible(session, user, event_id)
    note = await session.scalar(
        select(EventNote).where(EventNote.event_id == event_id, EventNote.user_id == user.id)
    )
    return EventNoteOut(content=note.content if note else "")


@router.put("/{event_id}/note", response_model=EventNoteOut)
async def put_note(
    event_id: int,
    payload: EventNoteIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventNoteOut:
    await _ensure_event_visible(session, user, event_id)
    note = await session.scalar(
        select(EventNote).where(EventNote.event_id == event_id, EventNote.user_id == user.id)
    )
    if note is None:
        note = EventNote(event_id=event_id, user_id=user.id, content=payload.content)
        session.add(note)
    else:
        note.content = payload.content
    await session.commit()
    return EventNoteOut(content=payload.content)


# --- attendees with detail + cross-user import ------------------------------


async def _viewer_owns_similar(session: AsyncSession, user: User, src: Contact) -> bool:
    """Does the viewer already have this contact (same UID or a shared email)?"""
    if src.nextcloud_uid:
        hit = await session.scalar(
            select(Contact.id).where(
                Contact.owner_id == user.id, Contact.nextcloud_uid == src.nextcloud_uid
            )
        )
        if hit:
            return True
    emails = {e.get("value", "").lower() for e in (src.emails or []) if e.get("value")}
    if not emails:
        return False
    mine = await session.scalars(select(Contact).where(Contact.owner_id == user.id))
    for c in mine.all():
        for e in c.emails or []:
            if e.get("value", "").lower() in emails:
                return True
    return False


@router.get("/{event_id}/attendees", response_model=list[AttendeeDetailOut])
async def event_attendees(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[AttendeeDetailOut]:
    await _ensure_event_visible(session, user, event_id)
    attendees = (
        await session.scalars(select(EventAttendee).where(EventAttendee.event_id == event_id))
    ).all()
    out: list[AttendeeDetailOut] = []
    for att in attendees:
        contact = await session.get(Contact, att.contact_id) if att.contact_id else None
        mine = bool(contact) and (
            contact.owner_id == user.id or await _viewer_owns_similar(session, user, contact)
        )
        out.append(
            AttendeeDetailOut(
                attendee_id=att.id,
                contact_id=att.contact_id,
                name=(contact.display_name if contact else "Someone"),
                emails=(contact.emails if contact else []),
                phones=(contact.phones if contact else []),
                status=att.status,
                mine=mine,
            )
        )
    return out


@router.post("/{event_id}/attendees/{attendee_id}/import", response_model=ContactOut)
async def import_attendee_contact(
    event_id: int,
    attendee_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    """Copy an event attendee's contact into the current user's own contacts."""
    await _ensure_event_visible(session, user, event_id)
    att = await session.get(EventAttendee, attendee_id)
    if att is None or att.event_id != event_id or att.contact_id is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Attendee not found")
    src = await session.get(Contact, att.contact_id)
    if src is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    contact = Contact(
        owner_id=user.id,
        visibility=Visibility.PRIVATE,
        dirty=True,
        nextcloud_uid=str(uuid.uuid4()),
        display_name=src.display_name,
        first_name=src.first_name,
        last_name=src.last_name,
        organization=src.organization,
        job_title=src.job_title,
        birthday=src.birthday,
        notes=src.notes,
        emails=list(src.emails or []),
        phones=list(src.phones or []),
        addresses=list(src.addresses or []),
    )
    session.add(contact)
    await geocode_contact(contact)
    await session.commit()
    await session.refresh(contact)
    return contact
