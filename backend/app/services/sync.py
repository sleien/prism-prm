"""Contact sync between Prism and a user's Nextcloud.

Nextcloud is the source of truth. Per user, the engine:
  1. pushes that user's locally-changed ("dirty") contacts up (create / If-Match),
  2. pulls new/changed remote contacts down (ETag comparison),
  3. removes local mirrors whose remote vCard has disappeared.

On a write conflict (HTTP 412) the local edit is left dirty and the remote copy
wins on the next pull, keeping Nextcloud authoritative without losing data.

Each user syncs their own Nextcloud account (or the instance-level fallback);
synced contacts are owned by that user and default to PRIVATE visibility.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from datetime import UTC, datetime
from urllib.parse import urlparse

from sqlalchemy import select
from sqlalchemy.ext.asyncio import AsyncSession

from app.constants import Visibility
from app.integrations.nextcloud import VCARD_CONTENT_TYPE, DavError, NextcloudClient
from app.integrations.vcard import build_vcard, parse_vcard
from app.models import Contact, User
from app.services.nextcloud_accounts import client_for_user

log = logging.getLogger("prism.sync")

_PARSED_FIELDS = (
    "display_name",
    "first_name",
    "middle_name",
    "last_name",
    "organization",
    "job_title",
    "birthday",
    "notes",
    "gender",
    "emails",
    "phones",
    "addresses",
)


@dataclass
class SyncResult:
    pushed: int = 0
    created: int = 0
    updated: int = 0
    deleted: int = 0
    conflicts: int = 0
    skipped_reason: str | None = None
    errors: list[str] = field(default_factory=list)


def _apply_fields(contact: Contact, fields: dict) -> None:
    for key in _PARSED_FIELDS:
        if key in fields and fields[key] is not None:
            setattr(contact, key, fields[key])
    if fields.get("nextcloud_uid"):
        contact.nextcloud_uid = fields["nextcloud_uid"]


async def _push_dirty(
    session: AsyncSession, nc: NextcloudClient, ab_url: str, owner_id: int, result: SyncResult
) -> None:
    dirty = (
        await session.scalars(
            select(Contact).where(Contact.dirty.is_(True), Contact.owner_id == owner_id)
        )
    ).all()
    ab_path = urlparse(ab_url).path
    for contact in dirty:
        try:
            vcard = build_vcard(contact, contact.vcard_raw)
            if contact.nextcloud_href:
                etag = await nc.put_object(
                    contact.nextcloud_href, vcard, VCARD_CONTENT_TYPE, etag=contact.etag
                )
            else:
                uid = contact.nextcloud_uid or parse_vcard(vcard).get("nextcloud_uid")
                href = f"{ab_path.rstrip('/')}/{uid}.vcf"
                etag = await nc.put_object(href, vcard, VCARD_CONTENT_TYPE, etag=None)
                contact.nextcloud_href = href
                contact.nextcloud_uid = uid
            contact.etag = etag
            contact.vcard_raw = vcard
            contact.dirty = False
            contact.last_synced_at = datetime.now(UTC)
            result.pushed += 1
        except DavError as exc:
            if exc.status == 412:
                result.conflicts += 1  # leave dirty; remote wins on pull
                log.warning("Contact %s push conflicted; remote wins", contact.id)
            else:
                result.errors.append(f"push contact {contact.id}: {exc}")
    await session.flush()


async def sync_contacts(session: AsyncSession, user: User) -> SyncResult:
    """Two-way sync of one user's contacts with their Nextcloud address book."""
    result = SyncResult()
    nc = client_for_user(user)
    if nc is None:
        result.skipped_reason = "Nextcloud not configured"
        return result

    async with nc:
        ab_url = await nc.addressbook_url()
        await _push_dirty(session, nc, ab_url, user.id, result)

        remote = {obj.href: obj for obj in await nc.list_objects(ab_url)}
        local = (
            await session.scalars(
                select(Contact).where(
                    Contact.owner_id == user.id, Contact.nextcloud_href.is_not(None)
                )
            )
        ).all()
        local_by_href = {c.nextcloud_href: c for c in local}

        # Pull new / changed.
        for href, obj in remote.items():
            existing = local_by_href.get(href)
            if existing is not None and existing.etag == obj.etag and not existing.dirty:
                continue
            try:
                full = await nc.get_object(href)
            except DavError as exc:
                result.errors.append(f"get {href}: {exc}")
                continue
            fields = parse_vcard(full.data or "")
            if existing is None:
                contact = Contact(
                    owner_id=user.id,
                    visibility=Visibility.PRIVATE,
                    nextcloud_href=href,
                )
                session.add(contact)
                result.created += 1
            else:
                contact = existing
                result.updated += 1
            _apply_fields(contact, fields)
            contact.etag = full.etag
            contact.vcard_raw = full.data
            contact.dirty = False
            contact.last_synced_at = datetime.now(UTC)

        # Remote deletions -> drop local mirror (unless it has a pending local edit).
        for href, contact in local_by_href.items():
            if href not in remote and not contact.dirty:
                await session.delete(contact)
                result.deleted += 1

    await session.commit()
    log.info(
        "Contact sync (user %d): +%d ~%d -%d pushed=%d conflicts=%d",
        user.id,
        result.created,
        result.updated,
        result.deleted,
        result.pushed,
        result.conflicts,
    )
    return result
