"""Contact relationships and life events, plus their per-user type catalogs.

Type catalogs are seeded with defaults the first time a user reads them, then
fully editable. Everything is owner-scoped: relationships and life events are
each user's own annotations on the contacts they can see.
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, or_, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.models import (
    Contact,
    ContactLifeEvent,
    ContactRelationship,
    ContactTag,
    EventType,
    LifeEventType,
    RelationshipType,
    Tag,
    User,
)
from app.schemas.enrichment import (
    EventTypeIn,
    EventTypeOut,
    LifeEventCreate,
    LifeEventOut,
    LifeEventTypeIn,
    LifeEventTypeOut,
    RelatedContactOut,
    RelationshipCreate,
    RelationshipTypeIn,
    RelationshipTypeOut,
    RelationshipTypeUpdate,
    TagCatalogOut,
    TagIn,
    TagUpdate,
)
from app.services.tags import auto_color
from app.visibility import visibility_filter

router = APIRouter(tags=["enrichment"])

# Built-in fallback for the gendered form of a label, used when a relationship
# type has no explicit male/female override set. Keyed by lower-cased base
# label -> (male, female).
_GENDERED_LABELS: dict[str, tuple[str, str]] = {
    "parent": ("Father", "Mother"),
    "child": ("Son", "Daughter"),
    "sibling": ("Brother", "Sister"),
    "grandparent": ("Grandfather", "Grandmother"),
    "grandchild": ("Grandson", "Granddaughter"),
}


def _gendered_label(
    base: str, gender: str | None, male: str | None = None, female: str | None = None
) -> str:
    """Render `base` in its gendered form for `gender`, preferring the explicit
    `male`/`female` overrides (from the relationship type), then the built-in
    fallback, then the neutral label."""
    fb = _GENDERED_LABELS.get(base.lower(), (None, None))
    if gender == "male":
        return male or fb[0] or base
    if gender == "female":
        return female or fb[1] or base
    return base

# (name, reverse_name, name_male, name_female, reverse_name_male, reverse_name_female)
_DEFAULT_RELATIONSHIP_TYPES = [
    ("Partner", None, None, None, None, None),
    ("Parent", "Child", "Father", "Mother", "Son", "Daughter"),
    ("Sibling", None, "Brother", "Sister", None, None),
    ("Grandparent", "Grandchild", "Grandfather", "Grandmother", "Grandson", "Granddaughter"),
    ("Friend", None, None, None, None, None),
    ("Colleague", None, None, None, None, None),
    ("Relative", None, None, None, None, None),
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
_DEFAULT_EVENT_TYPES = [
    ("Birthday", "🎂"),
    ("Dinner", "🍽️"),
    ("Meeting", "🤝"),
    ("Trip", "✈️"),
    ("Party", "🎉"),
    ("Call", "📞"),
    ("Appointment", "📅"),
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
            RelationshipType(
                owner_id=user.id,
                name=name,
                reverse_name=rev,
                name_male=nm,
                name_female=nf,
                reverse_name_male=rm,
                reverse_name_female=rf,
            )
            for name, rev, nm, nf, rm, rf in _DEFAULT_RELATIONSHIP_TYPES
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
    rt = RelationshipType(owner_id=user.id, **payload.model_dump())
    session.add(rt)
    await session.commit()
    await session.refresh(rt)
    return rt


@router.patch("/relationship-types/{type_id}", response_model=RelationshipTypeOut)
async def update_relationship_type(
    type_id: int,
    payload: RelationshipTypeUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> RelationshipType:
    rt = await session.get(RelationshipType, type_id)
    if rt is None or rt.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Relationship type not found")
    updates = payload.model_dump(exclude_unset=True)
    if "name" in updates and not (updates["name"] or "").strip():
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Name required")
    for key, value in updates.items():
        # Empty strings clear an optional gendered/reverse label back to null.
        setattr(rt, key, (value or None) if key != "name" else value.strip())
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
    # The owner's type catalog, keyed by neutral name, supplies the editable
    # gendered overrides for each relationship's denormalized labels.
    types = {
        t.name: t
        for t in await session.scalars(
            select(RelationshipType).where(RelationshipType.owner_id == user.id)
        )
    }
    out: list[RelatedContactOut] = []
    for rel in rows:
        rtype = types.get(rel.name)
        if rel.from_contact_id == contact_id:
            other_id, base = rel.to_contact_id, rel.name
            male = rtype.name_male if rtype else None
            female = rtype.name_female if rtype else None
        elif rel.reverse_name:
            other_id, base = rel.from_contact_id, rel.reverse_name
            male = rtype.reverse_name_male if rtype else None
            female = rtype.reverse_name_female if rtype else None
        else:  # symmetric (no reverse label) — gender the neutral name
            other_id, base = rel.from_contact_id, rel.name
            male = rtype.name_male if rtype else None
            female = rtype.name_female if rtype else None
        other = await session.get(Contact, other_id)
        out.append(
            RelatedContactOut(
                relationship_id=rel.id,
                contact_id=other_id,
                contact_name=(other.display_name if other else "Unknown"),
                label=_gendered_label(base, other.gender if other else None, male, female),
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


# --- event types ------------------------------------------------------------


@router.get("/event-types", response_model=list[EventTypeOut])
async def list_event_types(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[EventType]:
    rows = list(
        (await session.scalars(select(EventType).where(EventType.owner_id == user.id))).all()
    )
    if not rows:
        rows = [
            EventType(owner_id=user.id, name=name, emoji=emoji)
            for name, emoji in _DEFAULT_EVENT_TYPES
        ]
        session.add_all(rows)
        await session.commit()
        for r in rows:
            await session.refresh(r)
    return sorted(rows, key=lambda r: r.id)


@router.post("/event-types", response_model=EventTypeOut, status_code=201)
async def create_event_type(
    payload: EventTypeIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> EventType:
    et = EventType(owner_id=user.id, name=payload.name, emoji=payload.emoji)
    session.add(et)
    await session.commit()
    await session.refresh(et)
    return et


@router.delete("/event-types/{type_id}", status_code=204)
async def delete_event_type(
    type_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    et = await session.get(EventType, type_id)
    if et is not None and et.owner_id == user.id:
        await session.delete(et)
        await session.commit()
    return Response(status_code=204)


# --- tags -------------------------------------------------------------------


async def _owned_tag(session: AsyncSession, user: User, tag_id: int) -> Tag:
    tag = await session.get(Tag, tag_id)
    if tag is None or tag.owner_id != user.id:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Tag not found")
    return tag


@router.get("/tags", response_model=list[TagCatalogOut])
async def list_tags(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[TagCatalogOut]:
    counts = dict(
        (
            await session.execute(
                select(ContactTag.tag_id, func.count())
                .join(Tag, Tag.id == ContactTag.tag_id)
                .where(Tag.owner_id == user.id)
                .group_by(ContactTag.tag_id)
            )
        ).all()
    )
    rows = await session.scalars(
        select(Tag).where(Tag.owner_id == user.id).order_by(func.lower(Tag.name))
    )
    return [
        TagCatalogOut(id=t.id, name=t.name, color=t.color, count=counts.get(t.id, 0))
        for t in rows
    ]


@router.post("/tags", response_model=TagCatalogOut, status_code=201)
async def create_tag(
    payload: TagIn,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TagCatalogOut:
    name = payload.name.strip()
    if not name:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Tag name required")
    existing = await session.scalar(
        select(Tag).where(Tag.owner_id == user.id, func.lower(Tag.name) == name.lower())
    )
    if existing is not None:
        raise HTTPException(status.HTTP_409_CONFLICT, "Tag already exists")
    tag = Tag(owner_id=user.id, name=name, color=payload.color or auto_color(name))
    session.add(tag)
    await session.commit()
    await session.refresh(tag)
    return TagCatalogOut(id=tag.id, name=tag.name, color=tag.color, count=0)


@router.patch("/tags/{tag_id}", response_model=TagCatalogOut)
async def update_tag(
    tag_id: int,
    payload: TagUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> TagCatalogOut:
    tag = await _owned_tag(session, user, tag_id)
    if payload.name is not None and payload.name.strip():
        tag.name = payload.name.strip()
    if payload.color is not None:
        tag.color = payload.color or None
    await session.commit()
    await session.refresh(tag)
    count = await session.scalar(
        select(func.count()).select_from(ContactTag).where(ContactTag.tag_id == tag.id)
    )
    return TagCatalogOut(id=tag.id, name=tag.name, color=tag.color, count=count or 0)


@router.delete("/tags/{tag_id}", status_code=204)
async def delete_tag(
    tag_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    tag = await session.get(Tag, tag_id)
    if tag is not None and tag.owner_id == user.id:
        await session.delete(tag)  # contact_tag rows cascade
        await session.commit()
    return Response(status_code=204)
