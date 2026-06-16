"""Build iCalendar (VEVENT + VALARM) documents for the Nextcloud calendar.

Events are owned by Prism and pushed to Nextcloud as VEVENTs. Each reminder
becomes a VALARM inside the VEVENT, so Nextcloud fires the notification natively.
The optional cost is carried in an X-PRISM-COST property so it round-trips.
"""

from __future__ import annotations

import uuid
from datetime import UTC, datetime
from typing import Any

from icalendar import Alarm, Calendar
from icalendar import Event as IEvent
from icalendar.prop import vRecur


def _to_utc(dt: datetime) -> datetime:
    """Normalize a datetime to UTC. Naive datetimes are assumed to be UTC."""
    if dt.tzinfo is None:
        return dt.replace(tzinfo=UTC)
    return dt.astimezone(UTC)


def build_event_ics(
    event: Any,
    reminders: list[Any] | None = None,
    attendee_emails: list[str] | None = None,
) -> tuple[str, str]:
    """Return (ics_text, uid) for an Event-like object and its reminders."""
    cal = Calendar()
    cal.add("prodid", "-//Prism PRM//Calendar//EN")
    cal.add("version", "2.0")

    ie = IEvent()
    uid = event.nextcloud_uid or str(uuid.uuid4())
    ie.add("uid", uid)
    ie.add("summary", event.title)
    ie.add("dtstamp", datetime.now(UTC))

    if event.all_day:
        ie.add("dtstart", event.starts_at.date())
        if event.ends_at:
            ie.add("dtend", event.ends_at.date())
    else:
        # Emit timed events in UTC (DTSTART:...Z) for maximum client compatibility,
        # rather than a fixed-offset TZID that lacks a VTIMEZONE definition.
        ie.add("dtstart", _to_utc(event.starts_at))
        if event.ends_at:
            ie.add("dtend", _to_utc(event.ends_at))

    if event.description:
        ie.add("description", event.description)
    if event.location:
        ie.add("location", event.location)
    if event.rrule:
        try:
            ie.add("rrule", vRecur.from_ical(event.rrule))
        except (ValueError, KeyError):
            pass  # ignore an unparseable recurrence rule rather than fail the push
    if event.cost_amount is not None:
        ie.add("x-prism-cost", f"{event.cost_amount} {event.cost_currency or ''}".strip())

    for email in attendee_emails or []:
        ie.add("attendee", f"mailto:{email}")

    for reminder in reminders or []:
        alarm = Alarm()
        alarm.add("action", "DISPLAY")
        alarm.add("description", reminder.message)
        # Relative trigger: (remind_at - starts_at). A reminder before the event
        # is a negative offset, which is exactly what VALARM expects.
        alarm.add("trigger", reminder.remind_at - event.starts_at)
        ie.add_component(alarm)

    cal.add_component(ie)
    return cal.to_ical().decode("utf-8"), uid
