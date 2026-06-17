"""vCard parsing/building round-trips (pure logic — no DB or network)."""

from dataclasses import dataclass, field
from datetime import date

from app.integrations.vcard import build_vcard, parse_vcard

SAMPLE = """BEGIN:VCARD
VERSION:3.0
UID:abc-123
FN:Ada Lovelace
N:Lovelace;Ada;;;
ORG:Analytical Engines
TITLE:Mathematician
EMAIL;TYPE=WORK:ada@example.com
TEL;TYPE=CELL:+441234567890
BDAY:1815-12-10
GENDER:F
NOTE:First programmer
X-CUSTOM:keep-me
END:VCARD
"""


def test_parse_basic_fields():
    fields = parse_vcard(SAMPLE)
    assert fields["nextcloud_uid"] == "abc-123"
    assert fields["display_name"] == "Ada Lovelace"
    assert fields["first_name"] == "Ada"
    assert fields["last_name"] == "Lovelace"
    assert fields["organization"] == "Analytical Engines"
    assert fields["job_title"] == "Mathematician"
    assert fields["birthday"] == date(1815, 12, 10)
    assert fields["gender"] == "female"
    assert fields["emails"] == [{"type": "work", "value": "ada@example.com"}]
    assert fields["phones"] == [{"type": "cell", "value": "+441234567890"}]
    assert fields["notes"] == "First programmer"


def test_parse_malformed_does_not_raise():
    fields = parse_vcard("this is not a vcard")
    assert fields["display_name"] == ""
    assert fields["emails"] == []


@dataclass
class FakeContact:
    nextcloud_uid: str | None = "abc-123"
    display_name: str = "Ada Lovelace"
    first_name: str | None = "Ada"
    last_name: str | None = "Lovelace"
    organization: str | None = "Analytical Engines"
    job_title: str | None = "Mathematician"
    birthday: date | None = date(1815, 12, 10)
    notes: str | None = "First programmer"
    gender: str | None = "female"
    emails: list = field(default_factory=lambda: [{"type": "work", "value": "ada@example.com"}])
    phones: list = field(default_factory=lambda: [{"type": "cell", "value": "+441234567890"}])
    addresses: list = field(default_factory=list)


def test_build_preserves_unknown_properties():
    out = build_vcard(FakeContact(), existing_text=SAMPLE)
    assert "X-CUSTOM:keep-me" in out
    # And the modeled data survives a parse of the rebuilt card.
    reparsed = parse_vcard(out)
    assert reparsed["display_name"] == "Ada Lovelace"
    assert reparsed["emails"] == [{"type": "work", "value": "ada@example.com"}]
    assert reparsed["nextcloud_uid"] == "abc-123"
    assert reparsed["gender"] == "female"


def test_build_mints_uid_when_missing():
    c = FakeContact(nextcloud_uid=None)
    out = build_vcard(c)
    assert "UID:" in out
    assert parse_vcard(out)["display_name"] == "Ada Lovelace"
