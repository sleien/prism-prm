"""Contact CRUD (visibility-filtered) and the manual sync trigger.

Reads are filtered through the visibility layer. Writes are restricted to the
owner (or an admin) and mark the row `dirty`, so the next sync — or the "Sync
now" action — pushes the change up to Nextcloud. Deletes remove the vCard from
Nextcloud first (the source of truth), then the local mirror.
"""

from __future__ import annotations

import uuid

from fastapi import APIRouter, Depends, HTTPException, Response, status
from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.auth.deps import get_current_user, require_admin
from app.config import settings
from app.db import get_session
from app.integrations.nextcloud import DavError, NextcloudClient
from app.models import Contact, User
from app.schemas.contact import ContactCreate, ContactOut, ContactUpdate
from app.services.sync import SyncResult, sync_contacts
from app.visibility import validate_group_choice, visibility_filter

router = APIRouter(prefix="/contacts", tags=["contacts"])


def _to_dicts(items) -> list[dict]:
    return [i.model_dump() if hasattr(i, "model_dump") else dict(i) for i in (items or [])]


async def _owned(session: AsyncSession, user: User, contact_id: int) -> Contact:
    contact = await session.get(Contact, contact_id)
    if contact is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "Contact not found")
    if contact.owner_id != user.id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "Not your contact")
    return contact


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
    data = payload.model_dump()
    data["emails"] = _to_dicts(payload.emails)
    data["phones"] = _to_dicts(payload.phones)
    data["addresses"] = _to_dicts(payload.addresses)
    contact = Contact(
        owner_id=user.id,
        nextcloud_uid=str(uuid.uuid4()),
        dirty=True,  # pushed to Nextcloud on the next sync
        **data,
    )
    session.add(contact)
    await session.commit()
    await session.refresh(contact)
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
    for field in ("emails", "phones", "addresses"):
        if field in updates and updates[field] is not None:
            updates[field] = _to_dicts(getattr(payload, field))
    for key, value in updates.items():
        setattr(contact, key, value)
    await validate_group_choice(session, user, contact.visibility, contact.group_id)
    contact.dirty = True
    await session.commit()
    await session.refresh(contact)
    return contact


@router.delete("/{contact_id}", status_code=status.HTTP_204_NO_CONTENT)
async def delete_contact(
    contact_id: int,
    user: User = Depends(get_current_user),
    session: AsyncSession = Depends(get_session),
) -> Response:
    contact = await _owned(session, user, contact_id)
    # Remove from Nextcloud first so the next sync does not resurrect it.
    if contact.nextcloud_href and settings.nextcloud_configured:
        try:
            async with NextcloudClient.from_settings() as nc:
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
    user: User = Depends(require_admin), session: AsyncSession = Depends(get_session)
) -> SyncResult:
    """Run a contact sync now. Instance-wide, so restricted to admins."""
    return await sync_contacts(session)
