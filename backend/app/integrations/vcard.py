"""Map between Nextcloud vCards and Prism's Contact fields.

Parsing is defensive: malformed or partial vCards yield best-effort data rather
than raising. Building preserves unknown properties when an existing vCard text
is supplied, so a round-trip through Prism does not strip data it does not model.
"""

from __future__ import annotations

import uuid
from datetime import date, datetime
from typing import Any

import vobject


def _typed_list(component: Any, attr: str) -> list[dict[str, str]]:
    """Collect repeated typed properties (EMAIL, TEL) as {type, value} dicts."""
    out: list[dict[str, str]] = []
    for line in getattr(component, f"{attr}_list", []):
        value = getattr(line, "value", None)
        if not value:
            continue
        types = line.params.get("TYPE", []) if hasattr(line, "params") else []
        out.append({"type": (types[0].lower() if types else ""), "value": str(value)})
    return out


def _addresses(component: Any) -> list[dict[str, str]]:
    out: list[dict[str, str]] = []
    for line in getattr(component, "adr_list", []):
        adr = getattr(line, "value", None)
        if adr is None:
            continue
        types = line.params.get("TYPE", []) if hasattr(line, "params") else []
        out.append(
            {
                "type": (types[0].lower() if types else ""),
                "street": getattr(adr, "street", "") or "",
                "city": getattr(adr, "city", "") or "",
                "region": getattr(adr, "region", "") or "",
                "code": getattr(adr, "code", "") or "",
                "country": getattr(adr, "country", "") or "",
            }
        )
    return out


def _parse_gender(value: Any) -> str | None:
    """vCard 4.0 GENDER sex component -> Prism gender. M/F/O map across; N/U/empty
    (and the structured `;identity` suffix) yield unspecified."""
    if not value:
        return None
    sex = str(value).strip().split(";", 1)[0].strip().upper()
    return {"M": "male", "F": "female", "O": "other"}.get(sex)


def _parse_bday(value: Any) -> date | None:
    if not value:
        return None
    text = str(value).strip().replace("/", "-")
    # vCard birthdays may be full dates or --MM-DD (no year). Try common forms.
    for fmt in ("%Y-%m-%d", "%Y%m%d"):
        try:
            return datetime.strptime(text[:10], fmt).date()
        except ValueError:
            continue
    return None


def parse_vcard(text: str) -> dict[str, Any]:
    """Parse a vCard into a dict of Contact fields. Never raises on bad input."""
    empty = {"display_name": "", "emails": [], "phones": [], "addresses": [], "custom_fields": {}}
    try:
        card = vobject.readOne(text)
    except Exception:  # noqa: BLE001 - tolerate any malformed card
        return empty

    def val(attr: str) -> str | None:
        node = getattr(card, attr, None)
        return str(node.value) if node is not None and node.value else None

    name = getattr(card, "n", None)
    first = last = None
    if name is not None and name.value is not None:
        first = getattr(name.value, "given", None) or None
        last = getattr(name.value, "family", None) or None

    org = getattr(card, "org", None)
    org_value = None
    if org is not None and org.value:
        org_value = org.value[0] if isinstance(org.value, list) else str(org.value)

    return {
        "nextcloud_uid": val("uid"),
        "display_name": val("fn") or " ".join(filter(None, [first, last])) or "",
        "first_name": first,
        "last_name": last,
        "organization": org_value,
        "job_title": val("title"),
        "birthday": _parse_bday(getattr(getattr(card, "bday", None), "value", None)),
        "gender": _parse_gender(getattr(getattr(card, "gender", None), "value", None)),
        "notes": val("note"),
        "emails": _typed_list(card, "email"),
        "phones": _typed_list(card, "tel"),
        "addresses": _addresses(card),
        "custom_fields": {},
    }


def build_vcard(contact: Any, existing_text: str | None = None) -> str:
    """Serialize a Contact-like object to vCard text.

    When `existing_text` is given, its unknown properties are preserved and the
    modeled fields are overwritten; otherwise a fresh vCard is created.
    """
    if existing_text:
        try:
            card = vobject.readOne(existing_text)
        except Exception:  # noqa: BLE001
            card = vobject.vCard()
    else:
        card = vobject.vCard()

    def reset(attr: str) -> None:
        while getattr(card, attr, None) is not None:
            card.remove(getattr(card, attr))

    # UID — keep existing or mint one.
    uid = contact.nextcloud_uid or (card.uid.value if hasattr(card, "uid") else None)
    if not uid:
        uid = str(uuid.uuid4())
    reset("uid")
    card.add("uid").value = uid

    reset("fn")
    card.add("fn").value = contact.display_name or " ".join(
        filter(None, [contact.first_name, contact.last_name])
    ) or "Unnamed"

    reset("n")
    card.add("n").value = vobject.vcard.Name(
        family=contact.last_name or "", given=contact.first_name or ""
    )

    if contact.organization:
        reset("org")
        card.add("org").value = [contact.organization]
    if contact.job_title:
        reset("title")
        card.add("title").value = contact.job_title
    if contact.birthday:
        reset("bday")
        card.add("bday").value = contact.birthday.isoformat()
    reset("gender")
    if getattr(contact, "gender", None):
        card.add("gender").value = {"male": "M", "female": "F", "other": "O"}[contact.gender]
    if contact.notes:
        reset("note")
        card.add("note").value = contact.notes

    reset("email")
    for item in contact.emails or []:
        line = card.add("email")
        line.value = item["value"]
        if item.get("type"):
            line.type_param = item["type"].upper()

    reset("tel")
    for item in contact.phones or []:
        line = card.add("tel")
        line.value = item["value"]
        if item.get("type"):
            line.type_param = item["type"].upper()

    reset("adr")
    for item in contact.addresses or []:
        line = card.add("adr")
        line.value = vobject.vcard.Address(
            street=item.get("street", ""),
            city=item.get("city", ""),
            region=item.get("region", ""),
            code=item.get("code", ""),
            country=item.get("country", ""),
        )
        if item.get("type"):
            line.type_param = item["type"].upper()

    # Bump revision so clients see a change.
    reset("rev")
    card.add("rev").value = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")

    return card.serialize()
