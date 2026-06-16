"""Address-to-query building for geocoding (pure logic, no network)."""

from app.services.geocode import address_to_query


def test_address_to_query_joins_present_parts():
    q = address_to_query(
        {"street": "12 Main", "city": "London", "region": "", "code": "SW1", "country": "UK"}
    )
    assert q == "12 Main, London, SW1, UK"


def test_address_to_query_empty():
    assert address_to_query({}) == ""
    assert address_to_query({"city": ""}) == ""
