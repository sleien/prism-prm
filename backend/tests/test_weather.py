"""WMO weather code descriptions — pure logic, no network."""

from app.services.weather import describe


def test_describe_clear():
    assert describe(0) == ("Clear sky", "☀️")


def test_describe_rain():
    description, _emoji = describe(63)
    assert description == "Rain"


def test_describe_thunderstorm():
    description, _emoji = describe(95)
    assert "Thunderstorm" in description


def test_describe_unknown_code():
    assert describe(12345) == ("Unknown", "❓")
