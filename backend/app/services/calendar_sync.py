"""Push Prism events to the owner's Nextcloud calendar as VEVENT + VALARM.

Events are owned by Prism (one-way push). Push is best-effort: an event is
always saved locally; if Nextcloud is unavailable it simply shows as not-synced.
Each event is pushed to its owner's Nextcloud account.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.integrations.ical import build_event_ics
from app.integrations.nextcloud import ICAL_CONTENT_TYPE, DavError
from app.services.nextcloud_accounts import client_for_user

log = logging.getLogger("prism.calendar")


async def push_event(
    owner: Any, event: Any, reminders: list[Any], attendee_emails: list[str]
) -> tuple[bool, str | None]:
    """Push (create or update) an event to the owner's Nextcloud calendar.

    Mutates the event's nextcloud_uid/href/etag/last_synced_at. The caller commits.
    """
    ics, uid = build_event_ics(event, reminders, attendee_emails)
    event.nextcloud_uid = uid
    nc = client_for_user(owner)
    if nc is None:
        return False, "Nextcloud not configured"
    try:
        async with nc:
            cal_url = await nc.calendar_url()
            if event.nextcloud_href:
                etag = await nc.put_object(
                    event.nextcloud_href, ics, ICAL_CONTENT_TYPE, etag=event.etag
                )
            else:
                href = f"{urlparse(cal_url).path.rstrip('/')}/{uid}.ics"
                etag = await nc.put_object(href, ics, ICAL_CONTENT_TYPE, etag=None)
                event.nextcloud_href = href
            event.etag = etag
            event.last_synced_at = datetime.now(UTC)
        return True, None
    except DavError as exc:
        log.warning("Event push failed: %s", exc)
        return False, str(exc)


async def delete_event_remote(owner: Any, event: Any) -> None:
    """Remove an event's VEVENT from the owner's Nextcloud calendar (best-effort)."""
    if not event.nextcloud_href:
        return
    nc = client_for_user(owner)
    if nc is None:
        return
    async with nc:
        await nc.delete_object(event.nextcloud_href, etag=event.etag)
