"""Journal period math and the recurring "time to journal" Nextcloud reminder."""

from __future__ import annotations

import logging
from datetime import date, timedelta
from typing import Any
from urllib.parse import urlparse

from app.integrations.ical import build_journal_reminder_ics
from app.integrations.nextcloud import ICAL_CONTENT_TYPE, DavError
from app.services.nextcloud_accounts import client_for_user

log = logging.getLogger("prism.journal")


def period_for(d: date, cadence: str) -> tuple[date, str]:
    """Return (entry_date, period_key) for the period containing `d`.

    Daily -> the date itself (key YYYY-MM-DD).
    Weekly -> the Monday of that ISO week (key YYYY-Www).
    """
    if str(cadence) == "weekly":
        monday = d - timedelta(days=d.weekday())
        iso = monday.isocalendar()
        return monday, f"{iso.year}-W{iso.week:02d}"
    return d, d.isoformat()


def extract_mood(prompts: list[dict], data: dict) -> int | None:
    """Pull a denormalized mood (1..N) from the answers if the template has a
    scale prompt (preferring one literally named/identified 'mood')."""
    scales = [p for p in prompts if p.get("type") == "scale"]
    if not scales:
        return None
    chosen = next((p for p in scales if p.get("id") == "mood"), scales[0])
    value = data.get(chosen.get("id"))
    try:
        return int(value) if value is not None else None
    except (TypeError, ValueError):
        return None


async def push_journal_reminder(owner: Any, template: Any) -> None:
    """Upsert the template's recurring reminder VEVENT in the owner's calendar."""
    if not (template.reminder_time and template.active):
        return
    nc = client_for_user(owner)
    if nc is None:
        return
    try:
        ics, uid = build_journal_reminder_ics(template)
        async with nc:
            cal_url = await nc.calendar_url()
            href = f"{urlparse(cal_url).path.rstrip('/')}/{uid}.ics"
            await nc.put_object(href, ics, ICAL_CONTENT_TYPE, etag=None, create_only=False)
    except DavError as exc:
        log.warning("Journal reminder push failed: %s", exc)


async def delete_journal_reminder(owner: Any, template_id: int) -> None:
    nc = client_for_user(owner)
    if nc is None:
        return
    try:
        async with nc:
            cal_url = await nc.calendar_url()
            href = f"{urlparse(cal_url).path.rstrip('/')}/prism-journal-{template_id}.ics"
            await nc.delete_object(href)
    except DavError as exc:
        log.warning("Journal reminder delete failed: %s", exc)
