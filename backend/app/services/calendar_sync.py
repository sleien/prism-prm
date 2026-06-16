"""Push Prism events to the Nextcloud calendar as VEVENT + VALARM.

Events are owned by Prism (one-way push to Nextcloud, unlike contacts which are
Nextcloud-canonical). Push is best-effort: an event is always saved locally; if
Nextcloud is down the event simply shows as not-yet-synced and can be re-pushed.
"""

from __future__ import annotations

import logging
from datetime import UTC, datetime
from typing import Any
from urllib.parse import urlparse

from app.config import settings
from app.integrations.ical import build_event_ics
from app.integrations.nextcloud import ICAL_CONTENT_TYPE, DavError, NextcloudClient

log = logging.getLogger("prism.calendar")


async def push_event(
    event: Any, reminders: list[Any], attendee_emails: list[str]
) -> tuple[bool, str | None]:
    """Push (create or update) an event to the Nextcloud calendar.

    Mutates the event's nextcloud_uid/href/etag/last_synced_at. The caller
    commits. Returns (ok, error_message).
    """
    ics, uid = build_event_ics(event, reminders, attendee_emails)
    event.nextcloud_uid = uid
    if not settings.nextcloud_configured:
        return False, "Nextcloud not configured"
    try:
        async with NextcloudClient.from_settings() as nc:
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


async def delete_event_remote(event: Any) -> None:
    """Remove an event's VEVENT from the Nextcloud calendar (best-effort)."""
    if event.nextcloud_href and settings.nextcloud_configured:
        async with NextcloudClient.from_settings() as nc:
            await nc.delete_object(event.nextcloud_href, etag=event.etag)
