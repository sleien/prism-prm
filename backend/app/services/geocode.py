"""Geocode a contact's postal address to coordinates via OpenStreetMap Nominatim.

Best-effort and no API key. Nominatim's usage policy requires an identifying
User-Agent and modest request rates, which is fine for occasional contact saves.
"""

from __future__ import annotations

import logging
from typing import Any

import httpx

log = logging.getLogger("prism.geocode")

NOMINATIM_URL = "https://nominatim.openstreetmap.org/search"
_HEADERS = {"User-Agent": "Prism-PRM/0.1 (+https://github.com/sleien/prism-prm)"}


def address_to_query(address: dict[str, str]) -> str:
    parts = [address.get(k, "") for k in ("street", "city", "region", "code", "country")]
    return ", ".join(p for p in parts if p)


async def geocode_address(query: str) -> tuple[float, float] | None:
    if not query.strip():
        return None
    async with httpx.AsyncClient(timeout=httpx.Timeout(15.0), headers=_HEADERS) as client:
        resp = await client.get(NOMINATIM_URL, params={"q": query, "format": "json", "limit": 1})
        resp.raise_for_status()
        results = resp.json()
    if not results:
        return None
    return float(results[0]["lat"]), float(results[0]["lon"])


async def geocode_contact(contact: Any) -> None:
    """Set contact.latitude/longitude from its first address (best-effort)."""
    addresses = contact.addresses or []
    if not addresses:
        contact.latitude = None
        contact.longitude = None
        return
    query = address_to_query(addresses[0])
    if not query:
        return
    try:
        coords = await geocode_address(query)
    except (httpx.HTTPError, KeyError, ValueError, IndexError) as exc:
        log.warning("Geocode failed for %r: %s", query, exc)
        return
    if coords:
        contact.latitude, contact.longitude = coords
