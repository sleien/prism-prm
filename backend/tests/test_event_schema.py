"""Event schema validation: input enforces time order, output never does."""

from datetime import UTC, datetime
from types import SimpleNamespace

import pytest
from pydantic import ValidationError

from app.schemas.event import EventCreate, EventOut

_EARLIER = datetime(2026, 1, 1, tzinfo=UTC)
_LATER = datetime(2026, 1, 2, tzinfo=UTC)


def test_eventcreate_rejects_end_before_start():
    with pytest.raises(ValidationError):
        EventCreate(title="x", starts_at=_LATER, ends_at=_EARLIER)


def test_eventout_allows_end_before_start():
    """EventOut serializes existing rows as-is — it must NOT re-validate time
    order, or reading a legacy/odd row would 500 the list endpoint."""
    row = SimpleNamespace(
        id=1,
        owner_id=1,
        title="x",
        description=None,
        starts_at=_LATER,
        ends_at=_EARLIER,
        all_day=False,
        rrule=None,
        location=None,
        cost_amount=None,
        cost_currency=None,
        visibility="public",
        group_id=None,
        attendees=[],
        reminders=[],
        nextcloud_uid=None,
        last_synced_at=None,
        weather=None,
    )
    out = EventOut.model_validate(row)
    assert out.ends_at < out.starts_at
