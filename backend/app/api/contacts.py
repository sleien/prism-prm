"""Contact CRUD (visibility-filtered) and the manual sync trigger.

Reads are filtered through the visibility layer. Writes are restricted to the
owner (or an admin) and mark the row `dirty`, so the next sync — or the "Sync
now" action — pushes the change up to Nextcloud. Deletes remove the vCard from
Nextcloud first (the source of truth), then the local mirror.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user
from app.db import get_session
from app.integrations.nextcloud import DavError
from app.models import Contact, ContactTag, Tag, User
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate
from app.services.geocode import geocode_contact
from app.services.nextcloud_accounts import client_for_user
from app.services.phones import format_phones
from app.services.sync import SyncResult, sync_contacts
from app.services.tags import auto_color
from app.visibility import validate_group_choice, visibility_filter

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _to_dicts(items) -> list[dict]:
    return [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in (items or [])]


async def _set_contact_tags(
    session: AsyncSession, user: User, contact: Contact, names: list[str]
) -> None:
    """Get-or-create the owner's tags by name and set the contact's links to them."""
    wanted: list[int] = []
    seen: set[str] = set()
    for raw in names:
        name = (raw or "").strip()
        key = name.lower()
        if not name or key in seen:
            continue
        seen.add(key)
        tag = await session.scalar(
            select(Tag).where(Tag.owner_id == user.id, func.lower(Tag.name) == key)
        )
        if tag is None:
            tag = Tag(owner_id=user.id, name=name, color=auto_color(name))
            session.add(tag)
            await session.flush()
        wanted.append(tag.id)

    existing = list(
        await session.scalars(select(ContactTag).where(ContactTag.contact_id == contact.id))
    )
    have = {ct.tag_id for ct in existing}
    for ct in existing:
        if ct.tag_id not in wanted:
            await session.delete(ct)
    for tid in wanted:
        if tid not in have:
            session.add(ContactTag(contact_id=contact.id, tag_id=tid))


async def _owned(session: AsyncSession, user: User, contact_id: int) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    if contact.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your contact")
    return contact


async def _validate_linked_user(session: AsyncSession, linked_user_id: int | None) -> None:
    if linked_user_id is not None and await session.get(User, linked_user_id) is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "Linked user not found")


@router.get("", response_model=list[ContactOut])
async def list_contacts(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> list[Contact]:
    filt = await visibility_filter(session, user, Contact)
    rows = await session.scalars(select(Contact).where(filt).order_by(Contact.display_name))
    return list(rows.all())


@router.get("/{contact_id}", response_model=ContactOut)
async def get_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    filt = await visibility_filter(session, user, Contact)
    contact = await session.scalar(select(Contact).where(Contact.id == contact_id, filt))
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    return contact


@router.post("", response_model=ContactOut, status_code=status.HTTP_201_CREATED)
async def create_contact(
    payload: ContactCreate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    await validate_group_choice(session, user, payload.visibility, payload.group_id)
    await _validate_linked_user(session, payload.linked_user_id)
    data = payload.model_dump()
    tag_names = data.pop("tags", [])
    data["emails"] = _to_dicts(payload.emails)
    data["phones"] = format_phones(
        _to_dicts(payload.phones),
        user.phone_country_code,
        user.phone_number_format,
        user.phone_include_country_code,
    )
    data["addresses"] = _to_dicts(payload.addresses)
    contact = Contact(
        owner_id=user.id,
        nextcloud_uid=str(uuid.uuid4()),
        dirty=True,  # pushed to Nextcloud on the next sync
        **data,
    )
    session.add(contact)
    await geocode_contact(contact)
    await session.flush()
    await _set_contact_tags(session, user, contact, tag_names)
    await session.commit()
    await session.refresh(contact, attribute_names=["tags"])
    return contact


@router.patch("/{contact_id}", response_model=ContactOut)
async def update_contact(
    contact_id: int,
    payload: ContactUpdate,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Contact:
    contact = await _owned(session, user, contact_id)
    updates = payload.model_dump(exclude_unset=True)
    tag_names = updates.pop("tags", None)
    for field in ("emails", "phones", "addresses"):
        if field in updates and updates[field] is not None:
            updates[field] = _to_dicts(getattr(payload, field))
    if updates.get("phones") is not None:
        updates["phones"] = format_phones(
            updates["phones"],
            user.phone_country_code,
            user.phone_number_format,
            user.phone_include_country_code,
        )
    for key, value in updates.items():
        setattr(contact, key, value)
    await validate_group_choice(session, user, contact.visibility, contact.group_id)
    await _validate_linked_user(session, contact.linked_user_id)
    if "addresses" in updates:
        await geocode_contact(contact)
    if tag_names is not None:
        await _set_contact_tags(session, user, contact, tag_names)
    contact.dirty = True
    await session.commit()
    await session.refresh(contact, attribute_names=["tags"])
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    contact = await _owned(session, user, contact_id)
    # Remove from the owner's Nextcloud first so the next sync does not resurrect it.
    nc = client_for_user(user)
    if contact.nextcloud_href and nc is not None:
        try:
            async with nc:
                await nc.delete_object(contact.nextcloud_href, etag=contact.etag)
        except DavError as exc:
            raise HTTPException(
                status.HTTP_502_BAD_GATEWAY, f"Could not delete from Nextcloud: {exc}"
            ) from exc
    await session.delete(contact)
    await session.commit()
    return Response(status_code=status.HTTP_204_NO_CONTENT)


@router.post("/sync", response_model=SyncResult)
async def trigger_sync(
    user: User = Depends(get_current_user), session: AsyncSession = Depends(get_session)
) -> SyncResult:
    """Sync the current user's own contacts with their Nextcloud now."""
    return await sync_contacts(session, user)
