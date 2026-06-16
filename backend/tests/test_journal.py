"""Journal period math and mood extraction — pure logic, no DB."""

from datetime import date, timedelta

from app.services.journal import extract_mood, period_for


def test_period_for_daily():
    d = date(2026, 6, 16)
    entry_date, key = period_for(d, "daily")
    assert entry_date == d
    assert key == "2026-06-16"


def test_period_for_weekly_snaps_to_monday():
    d = date(2026, 6, 17)  # mid-week
    entry_date, key = period_for(d, "weekly")
    assert entry_date.weekday() == 0  # Monday
    assert entry_date == d - timedelta(days=d.weekday())
    assert key.startswith("2026-W")


def test_extract_mood_prefers_mood_id():
    prompts = [
        {"id": "energy", "type": "scale"},
        {"id": "mood", "type": "scale"},
        {"id": "note", "type": "text"},
    ]
    assert extract_mood(prompts, {"energy": 3, "mood": 8, "note": "hi"}) == 8


def test_extract_mood_falls_back_to_first_scale():
    assert extract_mood([{"id": "energy", "type": "scale"}], {"energy": 5}) == 5


def test_extract_mood_none_without_scale():
    assert extract_mood([{"id": "note", "type": "text"}], {"note": "x"}) is None


def test_extract_mood_tolerates_bad_value():
    assert extract_mood([{"id": "mood", "type": "scale"}], {"mood": "abc"}) is None
