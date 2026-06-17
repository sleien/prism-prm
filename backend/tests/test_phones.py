"""Phone number formatting to the user's settings pattern (pure logic)."""

import pytest

from app.services.phones import format_phone

CC = "+41"
MASK = "xxx xxx xx xx"


@pytest.mark.parametrize(
    "raw,expected",
    [
        ("0793360802", "079 336 08 02"),          # bare national
        ("079 336 08 02", "079 336 08 02"),        # already grouped (re-grouped)
        ("+41 79 336 08 02", "079 336 08 02"),     # international +CC
        ("+41793360802", "079 336 08 02"),
        ("00 41 79 731 32 24", "079 731 32 24"),   # 00CC prefix
        ("+41 44 558 68 08", "044 558 68 08"),      # landline, same mask
    ],
)
def test_home_country_numbers_match_mask(raw, expected):
    assert format_phone(raw, CC, MASK) == expected


def test_foreign_numbers_are_not_forced_into_mask():
    # Luxembourg / Italy stay as-is (whitespace only collapsed).
    assert format_phone("+352 661 333 145", CC, MASK) == "+352 661 333 145"
    assert format_phone("+39 339 416 0855", CC, MASK) == "+39 339 416 0855"


def test_length_mismatch_passthrough():
    # A national number that doesn't fit the 10-digit mask is left de-spaced.
    assert format_phone("044 123", CC, MASK) == "044 123"


def test_empty():
    assert format_phone("", CC, MASK) == ""
    assert format_phone("   ", CC, MASK) == ""
