"""Contact relationships and life events, plus their per-user type catalogs.

Type catalogs are seeded with defaults the first time a user reads them, then
fully editable. Everything is owner-scoped: relationships and life events are
each user's own annotations on the contacts they can see.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import (
    Contact,
    ContactLifeEvent,
    ContactRelationship,
    LifeEventType,
    RelationshipType,
    User,
)
from app.schemas.enrichment import (
    LifeEventCreate,
    LifeEventOut,
    LifeEventTypeIn,
    LifeEventTypeOut,
    RelatedContactOut,
    RelationshipCreate,
    RelationshipTypeIn,
    RelationshipTypeOut,
)
from app.visibility import visibility_filter

router = APIRouter(tags=["enrichment"])

_DEFAULT_RELATIONSHIP_TYPES = [
    ("Partner", None),
    ("Parent", "Child"),
    ("Sibling", None),
    ("Grandparent", "Grandchild"),
    ("Friend", None),
    ("Colleague", None),
    ("Relative", None),
]
_DEFAULT_LIFE_EVENT_TYPES = [
    ("Got married", "💍"),
    ("Moved house", "🏠"),
    ("New job", "💼"),
    ("New child", "👶"),
    ("Graduated", "🎓"),
    ("Anniversary", "🎉"),
    ("Met", "🤝"),
]


async def _ensure_visible_contact(session: AsyncSession, user: User, contact_id: int) -> None:
    filt = await visibility_filter(session, user, Contact)
    if await session.scalar(select(Contact.id).where(Contact.id == contact_id, filt)) is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")


# --- relationship types -----------------------------------------------------


@router.get("/relationship-types", response_model=list[RelationshipTypeOut])
async def list_relationship_types(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[RelationshipType]:
    rows = list(
        (
            await session.scalars(
                select(RelationshipType).where(RelationshipType.owner_id == user.id)
            )
        ).all()
    )
    if not rows:
        rows = [
            RelationshipType(owner_id=user.id, name=name, reverse_name=rev)
            for name, rev in _DEFAULT_RELATIONSHIP_TYPES
        ]
        session.add_all(rows)
        await session.commit()
        for r in rows:
            await session.refresh(r)
    return sorted(rows, key=lambda r: r.name)


@router.post("/relationship-types", response_model=RelationshipTypeOut, status_code=201)
async def create_relationship_type(
    payload: RelationshipTypeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RelationshipType:
    rt = RelationshipType(owner_id=user.id, name=payload.name, reverse_name=payload.reverse_name)
    session.add(rt)
    await session.commit()
    await session.refresh(rt)
    return rt


@router.delete("/relationship-types/{type_id}", status_code=204)
async def delete_relationship_type(
    type_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    rt = await session.get(RelationshipType, type_id)
    if rt is not None and rt.owner_id == user.id:
        await session.delete(rt)
        await session.commit()
    return Response(status_code=204)


# --- relationships ----------------------------------------------------------


@router.get("/contacts/{contact_id}/relationships", response_model=list[RelatedContactOut])
async def list_relationships(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[RelatedContactOut]:
    await _ensure_visible_contact(session, user, contact_id)
    rows = (
        await session.scalars(
            select(ContactRelationship).where(
                ContactRelationship.owner_id == user.id,
                or_(
                    ContactRelationship.from_contact_id == contact_id,
                    ContactRelationship.to_contact_id == contact_id,
                ),
            )
        )
    ).all()
    out: list[RelatedContactOut] = []
    for rel in rows:
        if rel.from_contact_id == contact_id:
            other_id, label = rel.to_contact_id, rel.name
        else:
            other_id, label = rel.from_contact_id, (rel.reverse_name or rel.name)
        other = await session.get(Contact, other_id)
        out.append(
            RelatedContactOut(
                relationship_id=rel.id,
                contact_id=other_id,
                contact_name=(other.display_name if other else "Unknown"),
                label=label,
            )
        )
    return out


@router.post("/relationships", status_code=201)
async def create_relationship(
    payload: RelationshipCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> dict:
    if payload.from_contact_id == payload.to_contact_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "A contact cannot relate to itself")
    await _ensure_visible_contact(session, user, payload.from_contact_id)
    await _ensure_visible_contact(session, user, payload.to_contact_id)
    rtype = await session.get(RelationshipType, payload.type_id)
    if rtype is None or rtype.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship type not found")
    rel = ContactRelationship(
        owner_id=user.id,
        from_contact_id=payload.from_contact_id,
        to_contact_id=payload.to_contact_id,
        name=rtype.name,
        reverse_name=rtype.reverse_name,
    )
    session.add(rel)
    await session.commit()
    return {"id": rel.id}


@router.delete("/relationships/{relationship_id}", status_code=204)
async def delete_relationship(
    relationship_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    rel = await session.get(ContactRelationship, relationship_id)
    if rel is not None and rel.owner_id == user.id:
        await session.delete(rel)
        await session.commit()
    return Response(status_code=204)


# --- life-event types -------------------------------------------------------


@router.get("/life-event-types", response_model=list[LifeEventTypeOut])
async def list_life_event_types(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[LifeEventType]:
    rows = list(
        (
            await session.scalars(select(LifeEventType).where(LifeEventType.owner_id == user.id))
        ).all()
    )
    if not rows:
        rows = [
            LifeEventType(owner_id=user.id, name=name, emoji=emoji)
            for name, emoji in _DEFAULT_LIFE_EVENT_TYPES
        ]
        session.add_all(rows)
        await session.commit()
        for r in rows:
            await session.refresh(r)
    return sorted(rows, key=lambda r: r.id)


@router.post("/life-event-types", response_model=LifeEventTypeOut, status_code=201)
async def create_life_event_type(
    payload: LifeEventTypeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> LifeEventType:
    let = LifeEventType(owner_id=user.id, name=payload.name, emoji=payload.emoji)
    session.add(let)
    await session.commit()
    await session.refresh(let)
    return let


@router.delete("/life-event-types/{type_id}", status_code=204)
async def delete_life_event_type(
    type_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    let = await session.get(LifeEventType, type_id)
    if let is not None and let.owner_id == user.id:
        await session.delete(let)
        await session.commit()
    return Response(status_code=204)


# --- life events ------------------------------------------------------------


@router.get("/contacts/{contact_id}/life-events", response_model=list[LifeEventOut])
async def list_life_events(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> list[ContactLifeEvent]:
    await _ensure_visible_contact(session, user, contact_id)
    rows = await session.scalars(
        select(ContactLifeEvent)
        .where(ContactLifeEvent.owner_id == user.id, ContactLifeEvent.contact_id == contact_id)
        .order_by(ContactLifeEvent.happened_on.desc().nulls_last())
    )
    return list(rows.all())


@router.post("/life-events", response_model=LifeEventOut, status_code=201)
async def create_life_event(
    payload: LifeEventCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> ContactLifeEvent:
    await _ensure_visible_contact(session, user, payload.contact_id)
    event = ContactLifeEvent(
        owner_id=user.id,
        contact_id=payload.contact_id,
        title=payload.title,
        emoji=payload.emoji,
        happened_on=payload.happened_on,
        note=payload.note,
    )
    session.add(event)
    await session.commit()
    await session.refresh(event)
    return event


@router.delete("/life-events/{event_id}", status_code=204)
async def delete_life_event(
    event_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    event = await session.get(ContactLifeEvent, event_id)
    if event is not None and event.owner_id == user.id:
        await session.delete(event)
        await session.commit()
    return Response(status_code=204)
