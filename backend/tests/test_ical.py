"""iCalendar builder (VEVENT + VALARM) — pure logic, no DB or network."""

from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from decimal import Decimal


@dataclass
class FakeReminder:
    message: str
    remind_at: datetime


@dataclass
class FakeEvent:
    title: str = "Dinner with Grace"
    nextcloud_uid: str | None = "evt-1"
    starts_at: datetime = datetime(2026, 6, 20, 17, 0, tzinfo=UTC)
    ends_at: datetime | None = datetime(2026, 6, 20, 19, 0, tzinfo=UTC)
    all_day: bool = False
    description: str | None = None
    location: str | None = "Zurich"
    rrule: str | None = None
    cost_amount: Decimal | None = Decimal("45.50")
    cost_currency: str | None = "EUR"


def test_build_event_ics_with_cost_attendee_and_alarm():
    from app.integrations.ical import build_event_ics

    event = FakeEvent()
    reminder = FakeReminder(message="Leave now", remind_at=event.starts_at - timedelta(hours=1))
    ics, uid = build_event_ics(event, [reminder], ["grace@navy.mil"])

    assert uid == "evt-1"
    assert "BEGIN:VEVENT" in ics
    assert "SUMMARY:Dinner with Grace" in ics
    # Timed events are emitted in UTC (Z), not a fixed-offset TZID.
    assert "DTSTART:20260620T170000Z" in ics
    assert "X-PRISM-COST:45.50 EUR" in ics
    assert "ATTENDEE:mailto:grace@navy.mil" in ics
    assert "BEGIN:VALARM" in ics
    assert "TRIGGER:-PT1H" in ics


def test_build_event_ics_mints_uid_when_missing():
    from app.integrations.ical import build_event_ics

    event = FakeEvent(nextcloud_uid=None)
    ics, uid = build_event_ics(event, [], [])
    assert uid
    assert "BEGIN:VEVENT" in ics
    assert "X-PRISM-COST" in ics  # cost still present
