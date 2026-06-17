#!/usr/bin/env python3
"""Merge a Google Contacts CSV export and a Monica SQL dump, then upload the
result to a Prism instance over its HTTP API.

Two sources, merged by normalized name:
  * Google CSV  -> the fresher source for phones / emails / addresses / birthday.
  * Monica SQL  -> gender, notes, nickname, and the family/relationship graph.

Gender is taken from Monica where the person exists there, otherwise inferred
from the first name (gender-guesser); ambiguous names stay unspecified.

Auth is a Bearer token (a personal API token minted in Prism). Run a dry-run
first (the default) to eyeball the merge before writing anything.

    # preview only — no network writes:
    python monica_google_import.py --csv contacts.csv --monica monica.sql \
        --out-dir ./import-preview

    # real upload:
    python monica_google_import.py --csv contacts.csv --monica monica.sql \
        --base-url https://prism.home.schneider.today --token "$PRISM_TOKEN" --apply

Idempotent: contacts are matched by normalized name (create-or-update) and a
relationship is skipped if the two contacts are already linked, so re-running
does not duplicate.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path

try:
    import requests
except ImportError:  # pragma: no cover
    sys.exit("Missing dependency: pip install requests")

try:
    import gender_guesser.detector as gg

    _DETECTOR = gg.Detector(case_sensitive=False)
except ImportError:  # pragma: no cover
    _DETECTOR = None


# --------------------------------------------------------------------------- #
# Helpers
# --------------------------------------------------------------------------- #
def strip_accents(s: str) -> str:
    return "".join(c for c in unicodedata.normalize("NFKD", s) if not unicodedata.combining(c))


def norm_name(first: str | None, last: str | None, display: str | None = None) -> str:
    """A loose key for matching the same person across sources.

    When a last name is present we key on the *first* given name + last name, so
    middle names (which Prism can't store and which appear inconsistently across
    sources, e.g. "Lisa Latika Heierli" vs "Lisa Heierli") don't split a person
    into duplicates. Without a last name we fall back to the full given/display
    string to avoid over-merging mononyms.
    """
    first = (first or "").strip()
    last = (last or "").strip()
    if last:
        given = first.split()[0] if first else ""
        base = f"{given} {last}".strip()
    else:
        base = first or (display or "").strip()
    return re.sub(r"\s+", " ", strip_accents(base).lower()).strip()


_SERVICE_WORDS = {
    "ambulanz", "feuerwehr", "polizei", "giftnotruf", "notruf", "rega", "pannenhilfe",
    "tel-seelsorge", "verkehrsinfos", "werkstatt", "survival", "facility", "novadura",
    "airbnb", "pogo", "ambulance",
}


def looks_like_service(name: str, phones: list[str]) -> bool:
    """Emergency numbers / business entries we don't want as people."""
    low = strip_accents(name).lower()
    if any(w in low for w in _SERVICE_WORDS):
        return True
    # A "phone" that is just a short number (117, 118, 144, 1414, ...) is a service.
    for p in phones:
        digits = re.sub(r"\D", "", p)
        if digits and len(digits) <= 4:
            return True
    return False


def infer_gender(first_name: str | None) -> str | None:
    if not first_name or _DETECTOR is None:
        return None
    token = first_name.strip().split()[0] if first_name.strip() else ""
    g = _DETECTOR.get_gender(token)
    if g in ("male", "mostly_male"):
        return "male"
    if g in ("female", "mostly_female"):
        return "female"
    return None  # andy / unknown


_YEAR_RE = re.compile(r"^(\d{4})-(\d{2})-(\d{2})$")


def clean_birthday(value: str | None) -> str | None:
    """Keep only plausible full YYYY-MM-DD dates (drop --MM-DD and bogus years)."""
    if not value:
        return None
    m = _YEAR_RE.match(value.strip()[:10])
    if not m:
        return None
    year = int(m.group(1))
    if 1900 <= year <= 2025:
        return m.group(0)
    return None


def split_multi(value: str | None) -> list[str]:
    """Google sometimes joins multiple values with ':::'."""
    if not value:
        return []
    return [p.strip() for p in value.split(":::") if p.strip()]


# --------------------------------------------------------------------------- #
# Records
# --------------------------------------------------------------------------- #
@dataclass
class Person:
    first: str = ""
    middle: str = ""
    last: str = ""
    display: str = ""
    emails: list[dict] = field(default_factory=list)   # {type, value}
    phones: list[dict] = field(default_factory=list)
    addresses: list[dict] = field(default_factory=list)
    birthday: str | None = None
    organization: str | None = None
    job_title: str | None = None
    notes: str | None = None
    nickname: str | None = None
    gender: str | None = None
    tags: list[str] = field(default_factory=list)
    monica_id: int | None = None
    sources: set[str] = field(default_factory=set)

    @property
    def key(self) -> str:
        return norm_name(self.first, self.last, self.display)

    @property
    def name(self) -> str:
        return " ".join(filter(None, [self.first, self.middle, self.last])) or self.display


def _merge_typed(into: list[dict], extra: list[dict]) -> None:
    seen = {re.sub(r"\s", "", e["value"].lower()) for e in into}
    for item in extra:
        k = re.sub(r"\s", "", item["value"].lower())
        if k and k not in seen:
            into.append(item)
            seen.add(k)


# --------------------------------------------------------------------------- #
# Google CSV
# --------------------------------------------------------------------------- #
def parse_google_csv(path: Path) -> tuple[list[Person], list[dict]]:
    people: list[Person] = []
    skipped: list[dict] = []
    with path.open(newline="", encoding="utf-8") as fh:
        for row in csv.DictReader(fh):
            first = (row.get("First Name") or "").strip()
            middle = (row.get("Middle Name") or "").strip()
            last = (row.get("Last Name") or "").strip()
            display = (row.get("File As") or " ".join(filter(None, [first, middle, last]))).strip()
            if not (first or last or display):
                continue  # blank trailing row

            emails = []
            for n in (1, 2):
                for v in split_multi(row.get(f"E-mail {n} - Value")):
                    label = (row.get(f"E-mail {n} - Label") or "home").strip("* ").lower() or "home"
                    emails.append({"type": label, "value": v})
            phones = []
            for n in (1, 2, 3):
                for v in split_multi(row.get(f"Phone {n} - Value")):
                    label = (row.get(f"Phone {n} - Label") or "cell").strip("* ").lower() or "cell"
                    phones.append({"type": label, "value": v})

            phone_values = [p["value"] for p in phones]
            if looks_like_service(display or f"{first} {last}", phone_values):
                skipped.append({"name": display or f"{first} {last}", "phones": phone_values})
                continue

            addresses = []
            street = (row.get("Address 1 - Street") or "").replace("\n", " ").strip()
            city = (row.get("Address 1 - City") or "").strip()
            country = (row.get("Address 1 - Country") or "").strip()
            if street or city or country:
                addresses.append({
                    "type": (row.get("Address 1 - Label") or "home").strip("* ").lower() or "home",
                    "street": street, "city": city,
                    "region": (row.get("Address 1 - Region") or "").strip(),
                    "code": (row.get("Address 1 - Postal Code") or "").strip(),
                    "country": country,
                })

            people.append(Person(
                first=first, middle=middle, last=last, display=display,
                emails=emails, phones=phones, addresses=addresses,
                birthday=clean_birthday(row.get("Birthday")),
                organization=(row.get("Organization Name") or "").strip() or None,
                job_title=(row.get("Organization Title") or "").strip() or None,
                nickname=(row.get("Nickname") or "").strip() or None,
                sources={"google"},
            ))
    return people, skipped


# --------------------------------------------------------------------------- #
# Monica SQL dump
# --------------------------------------------------------------------------- #
def _parse_insert(text: str, table: str) -> list[dict]:
    """Parse `INSERT IGNORE INTO `table` (cols) VALUES (...),(...);` into dicts.

    Handles single-quoted strings with backslash escapes / doubled quotes,
    NULLs, numbers, commas and newlines inside strings.
    """
    marker = f"INSERT IGNORE INTO `{table}` "
    start = text.find(marker)
    if start == -1:
        return []
    open_p = text.find("(", start)
    close_p = text.find(")", open_p)
    cols = [c.strip(" `") for c in text[open_p + 1:close_p].split(",")]
    i = text.find("VALUES", close_p) + len("VALUES")

    rows: list[dict] = []
    n = len(text)
    while i < n:
        # skip to next row opener at statement level
        while i < n and text[i] not in "(;":
            i += 1
        if i >= n or text[i] == ";":
            break
        i += 1  # past '('
        fields: list[str | None] = []
        buf: list[str] = []
        in_str = False
        is_str = False
        while i < n:
            c = text[i]
            if in_str:
                if c == "\\" and i + 1 < n:
                    nxt = text[i + 1]
                    buf.append({"n": "\n", "t": "\t", "r": "\r", "0": ""}.get(nxt, nxt))
                    i += 2
                    continue
                if c == "'":
                    if i + 1 < n and text[i + 1] == "'":  # doubled quote
                        buf.append("'")
                        i += 2
                        continue
                    in_str = False
                    i += 1
                    continue
                buf.append(c)
                i += 1
                continue
            if c == "'":
                in_str = True
                is_str = True
                i += 1
                continue
            if c == ",":
                fields.append(_finish_field("".join(buf), is_str))
                buf, is_str = [], False
                i += 1
                continue
            if c == ")":
                fields.append(_finish_field("".join(buf), is_str))
                i += 1
                break
            buf.append(c)
            i += 1
        rows.append(dict(zip(cols, fields, strict=False)))
    return rows


def _finish_field(raw: str, is_str: bool) -> str | None:
    if is_str:
        return raw
    raw = raw.strip()
    if raw == "" or raw.upper() == "NULL":
        return None
    return raw


def parse_monica(path: Path) -> tuple[dict[int, Person], list[tuple[str, int, int]]]:
    text = path.read_text(encoding="utf-8", errors="replace")

    genders = {int(g["id"]): (g["name"] or "").lower() for g in _parse_insert(text, "genders")}
    # Monica gender 'type' M/F/U is the reliable signal; fall back to name.
    gender_type = {int(g["id"]): (g.get("type") or "").upper() for g in _parse_insert(text, "genders")}

    def gender_of(gid: str | None) -> str | None:
        if gid is None:
            return None
        t = gender_type.get(int(gid), "")
        if t == "M":
            return "male"
        if t == "F":
            return "female"
        name = genders.get(int(gid), "")
        return {"man": "male", "woman": "female"}.get(name)

    # contact fields -> emails / phones, keyed by contact_id
    ftypes = {int(t["id"]): (t.get("type") or "").lower() for t in _parse_insert(text, "contact_field_types")}
    fields_by_contact: dict[int, dict[str, list[str]]] = {}
    for f in _parse_insert(text, "contact_fields"):
        cid = int(f["contact_id"])
        kind = ftypes.get(int(f["contact_field_type_id"]), "")
        if kind in ("email", "phone") and f.get("data"):
            fields_by_contact.setdefault(cid, {}).setdefault(kind, []).append(f["data"])

    # birthdays: special_dates referenced by contacts.birthday_special_date_id
    sdates = {
        int(s["id"]): s
        for s in _parse_insert(text, "special_dates")
    }

    people: dict[int, Person] = {}
    for c in _parse_insert(text, "contacts"):
        if c.get("is_active") == "0":
            continue
        cid = int(c["id"])
        first = (c.get("first_name") or "").strip()
        middle = (c.get("middle_name") or "").strip()
        last = (c.get("last_name") or "").strip()
        emails = [{"type": "home", "value": v} for v in fields_by_contact.get(cid, {}).get("email", [])]
        phones = [{"type": "cell", "value": v} for v in fields_by_contact.get(cid, {}).get("phone", [])]
        bday = None
        sd_id = c.get("birthday_special_date_id")
        if sd_id and int(sd_id) in sdates:
            sd = sdates[int(sd_id)]
            if sd.get("is_year_unknown") == "0" and sd.get("is_age_based") == "0":
                bday = clean_birthday(sd.get("date"))
        people[cid] = Person(
            first=first, middle=middle, last=last,
            display=" ".join(filter(None, [first, middle, last])),
            emails=emails, phones=phones, birthday=bday,
            organization=(c.get("company") or None),
            job_title=(c.get("job") or None),
            notes=(c.get("description") or None),
            nickname=(c.get("nickname") or None),
            gender=gender_of(c.get("gender_id")),
            monica_id=cid,
            sources={"monica"},
        )

    # tags: id -> name, then attach the names to each tagged contact.
    tag_name = {int(t["id"]): (t.get("name") or "").strip() for t in _parse_insert(text, "tags")}
    for ct in _parse_insert(text, "contact_tag"):
        cid = int(ct["contact_id"])
        name = tag_name.get(int(ct["tag_id"]))
        if name and cid in people and name not in people[cid].tags:
            people[cid].tags.append(name)

    # relationship types: id -> (name, reverse)
    rtypes = {
        int(t["id"]): ((t.get("name") or "").lower(), (t.get("name_reverse_relationship") or "").lower())
        for t in _parse_insert(text, "relationship_types")
    }
    rels: list[tuple[str, int, int]] = []  # (prism_type_name, from_monica_id, to_monica_id)
    seen_pairs: set[tuple[int, int]] = set()
    for r in _parse_insert(text, "relationships"):
        tid = int(r["relationship_type_id"])
        contact_is = int(r["contact_is"])
        of_contact = int(r["of_contact"])
        mname, _mrev = rtypes.get(tid, ("", ""))
        mapped = _map_relationship(mname, contact_is, of_contact)
        if mapped is None:
            continue
        prism_name, frm, to = mapped
        pair = (min(frm, to), max(frm, to))
        if pair in seen_pairs:
            continue
        seen_pairs.add(pair)
        rels.append((prism_name, frm, to))
    return people, rels


# Monica's family graph is bidirectional; we keep one Prism edge per pair and
# let Prism's gendering turn generic labels into Father/Mother/Brother/etc.
_SYMMETRIC = {
    "sibling": "Sibling",
    "partner": "Partner", "spouse": "Partner", "date": "Partner", "lover": "Partner",
    "ex": "Partner", "ex_husband": "Partner", "inlovewith": "Partner", "lovedby": "Partner",
    "friend": "Friend", "bestfriend": "Friend",
    "colleague": "Colleague", "boss": "Colleague", "subordinate": "Colleague",
    "mentor": "Colleague", "protege": "Colleague",
    "cousin": "Relative", "uncle": "Relative", "nephew": "Relative",
    "godfather": "Relative", "godson": "Relative",
    "stepparent": "Relative", "stepchild": "Relative",
}


def _map_relationship(mname: str, contact_is: int, of_contact: int):
    """Return (prism_type_name, from_monica_id, to_monica_id) or None to skip.

    Monica row semantics: `of_contact is the {mname} of contact_is`. Prism type
    semantics: rel(from=A, to=B, name=N, reverse=R) shows B as "N" when viewing A
    and A as "R" when viewing B, with N/R gendered by the *other* contact. We
    therefore always orient directed family edges as from=child → to=parent and
    use the existing "Parent"/"Grandparent" Prism types; gendering turns these
    into Father/Mother + Son/Daughter (and Grand…) per contact. Monica stores
    both mirror rows, so mapping each direction to the same oriented edge plus
    pair-deduping is robust even if one mirror is missing.
    """
    if mname == "parent":          # of_contact is parent of contact_is
        return ("Parent", contact_is, of_contact)        # from=child, to=parent
    if mname == "child":           # of_contact is child of contact_is
        return ("Parent", of_contact, contact_is)        # from=child, to=parent
    if mname == "grandparent":
        return ("Grandparent", contact_is, of_contact)   # from=grandchild, to=grandparent
    if mname == "grandchild":
        return ("Grandparent", of_contact, contact_is)   # from=grandchild, to=grandparent
    # Symmetric (or treated-as-symmetric) relations: orient by id to dedupe.
    prism = _SYMMETRIC.get(mname, "Relative")
    if contact_is < of_contact:
        return (prism, contact_is, of_contact)
    return (prism, of_contact, contact_is)


# --------------------------------------------------------------------------- #
# Merge
# --------------------------------------------------------------------------- #
def merge(google: list[Person], monica: dict[int, Person]) -> tuple[list[Person], dict[int, str]]:
    by_key: dict[str, Person] = {}
    monica_key: dict[int, str] = {}

    # Monica first (carries gender / relationships); Google overlays contact info.
    for cid, m in monica.items():
        key = m.key
        if not key:
            continue
        monica_key[cid] = key
        if key in by_key:
            tgt = by_key[key]
            tgt.monica_id = tgt.monica_id or cid
            tgt.gender = tgt.gender or m.gender
            tgt.notes = tgt.notes or m.notes
            tgt.nickname = tgt.nickname or m.nickname
            tgt.middle = tgt.middle or m.middle
            tgt.tags = list(dict.fromkeys(tgt.tags + m.tags))
            _merge_typed(tgt.emails, m.emails)
            _merge_typed(tgt.phones, m.phones)
            tgt.birthday = tgt.birthday or m.birthday
            tgt.sources |= m.sources
        else:
            by_key[key] = m

    for g in google:
        key = g.key
        if not key:
            continue
        if key in by_key:
            tgt = by_key[key]
            # Google wins for contact info; Monica keeps gender/notes.
            _merge_typed(g.emails, tgt.emails)
            _merge_typed(g.phones, tgt.phones)
            tgt.emails, tgt.phones = g.emails, g.phones
            tgt.addresses = g.addresses or tgt.addresses
            tgt.birthday = g.birthday or tgt.birthday
            tgt.organization = g.organization or tgt.organization
            tgt.job_title = g.job_title or tgt.job_title
            tgt.nickname = tgt.nickname or g.nickname
            tgt.first = tgt.first or g.first
            tgt.middle = tgt.middle or g.middle
            tgt.last = tgt.last or g.last
            tgt.display = tgt.display or g.display
            tgt.sources |= g.sources
        else:
            by_key[key] = g

    # Fill missing gender by first-name inference.
    for p in by_key.values():
        if not p.gender:
            p.gender = infer_gender(p.first or p.display)

    return list(by_key.values()), monica_key


# --------------------------------------------------------------------------- #
# Prism API client
# --------------------------------------------------------------------------- #
def _err(e: Exception) -> str:
    """Compact error message, including a server response body when present."""
    resp = getattr(e, "response", None)
    if resp is not None:
        body = (resp.text or "")[:200].replace("\n", " ")
        return f"HTTP {resp.status_code} {body}"
    return str(e)


class Prism:
    def __init__(self, base_url: str, token: str, verify: bool = True):
        self.base = base_url.rstrip("/")
        self.s = requests.Session()
        self.s.headers["Authorization"] = f"Bearer {token}"
        self.s.verify = verify

    def get(self, path: str):
        r = self.s.get(self.base + path, timeout=30)
        r.raise_for_status()
        return r.json()

    def post(self, path: str, body: dict):
        r = self.s.post(self.base + path, json=body, timeout=30)
        r.raise_for_status()
        return r.json() if r.content else {}

    def patch(self, path: str, body: dict):
        r = self.s.patch(self.base + path, json=body, timeout=30)
        r.raise_for_status()
        return r.json()


def contact_payload(p: Person) -> dict:
    return {
        "display_name": p.name,
        "first_name": p.first or None,
        "middle_name": p.middle or None,
        "last_name": p.last or None,
        "organization": p.organization,
        "job_title": p.job_title,
        "birthday": p.birthday,
        "notes": p.notes,
        "gender": p.gender,
        "emails": p.emails,
        "phones": p.phones,
        "addresses": p.addresses,
        "tags": p.tags,
        "visibility": "public",
    }


def upload(api: Prism, merged: list[Person], rels, monica_key, *, self_contact_id, self_key):
    existing = {norm_name(c.get("first_name"), c.get("last_name"), c.get("display_name")): c
                for c in api.get("/api/contacts")}
    created = updated = 0
    errors: list[str] = []
    key_to_id: dict[str, int] = {}

    for p in merged:
        if self_key and p.key == self_key:
            if self_contact_id:
                key_to_id[p.key] = self_contact_id  # don't duplicate "me"
            continue
        payload = contact_payload(p)
        try:
            if p.key in existing:
                cid = existing[p.key]["id"]
                api.patch(f"/api/contacts/{cid}", payload)
                updated += 1
            else:
                cid = api.post("/api/contacts", payload)["id"]
                created += 1
            key_to_id[p.key] = cid
        except Exception as e:  # noqa: BLE001 - keep going; re-run is idempotent
            errors.append(f"contact {p.name!r}: {_err(e)}")
    if self_contact_id and self_key:
        key_to_id[self_key] = self_contact_id

    # Relationship type name -> id (seed defaults by reading first).
    types = {t["name"]: t["id"] for t in api.get("/api/relationship-types")}

    # Existing links (unordered pairs) so re-runs don't duplicate.
    linked: set[tuple[int, int]] = set()
    rel_added = rel_skipped = 0
    monica_id_to_key = monica_key

    for prism_name, frm_mid, to_mid in rels:
        frm = key_to_id.get(monica_id_to_key.get(frm_mid, ""))
        to = key_to_id.get(monica_id_to_key.get(to_mid, ""))
        type_id = types.get(prism_name)
        if not frm or not to or frm == to or not type_id:
            rel_skipped += 1
            continue
        pair = (min(frm, to), max(frm, to))
        if pair not in linked:
            # lazily fetch existing links for `frm`
            for r in api.get(f"/api/contacts/{frm}/relationships"):
                linked.add((min(frm, r["contact_id"]), max(frm, r["contact_id"])))
        if pair in linked:
            rel_skipped += 1
            continue
        try:
            api.post("/api/relationships",
                     {"from_contact_id": frm, "to_contact_id": to, "type_id": type_id})
            linked.add(pair)
            rel_added += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"relationship {frm}->{to} ({prism_name}): {_err(e)}")

    return {"created": created, "updated": updated, "rel_added": rel_added,
            "rel_skipped": rel_skipped, "errors": errors}


# --------------------------------------------------------------------------- #
# Main
# --------------------------------------------------------------------------- #
def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--csv", required=True, type=Path)
    ap.add_argument("--monica", required=True, type=Path)
    ap.add_argument("--base-url", help="e.g. https://prism.home.schneider.today")
    ap.add_argument("--token", help="Prism personal API token (Bearer)")
    ap.add_argument("--apply", action="store_true", help="actually write (default is dry-run)")
    ap.add_argument("--insecure", action="store_true", help="skip TLS verification")
    ap.add_argument("--out-dir", type=Path, default=Path("./import-preview"))
    args = ap.parse_args()

    google, skipped = parse_google_csv(args.csv)
    monica, rels = parse_monica(args.monica)
    merged, monica_key = merge(google, monica)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "merged.json").write_text(
        json.dumps([{**p.__dict__, "sources": sorted(p.sources)} for p in merged],
                   indent=2, ensure_ascii=False))
    (args.out_dir / "skipped.json").write_text(json.dumps(skipped, indent=2, ensure_ascii=False))

    with_gender = sum(1 for p in merged if p.gender)
    both = sum(1 for p in merged if {"google", "monica"} <= p.sources)
    print(f"Google people:      {len(google)}  (skipped non-people: {len(skipped)})")
    print(f"Monica contacts:    {len(monica)}")
    print(f"Merged unique:      {len(merged)}  (in both sources: {both})")
    print(f"  with gender:      {with_gender}  ({len(merged) - with_gender} unspecified)")
    print(f"Relationships:      {len(rels)} edges")
    tagged = sum(1 for p in merged if p.tags)
    distinct_tags = sorted({t for p in merged for t in p.tags})
    print(f"Tags:               {tagged} contacts tagged; {len(distinct_tags)} distinct: {distinct_tags}")
    print(f"Preview written to: {args.out_dir}/merged.json , skipped.json")
    if _DETECTOR is None:
        print("NOTE: gender-guesser not installed; name inference disabled.")

    if not args.apply:
        print("\nDry-run only. Re-run with --base-url/--token/--apply to upload.")
        return

    if not (args.base_url and args.token):
        sys.exit("--apply requires --base-url and --token")
    api = Prism(args.base_url, args.token, verify=not args.insecure)
    me = api.get("/api/auth/me")
    self_contact_id = me.get("self_contact_id")
    self_key = None
    if self_contact_id:
        for c in api.get("/api/contacts"):
            if c["id"] == self_contact_id:
                self_key = norm_name(c.get("first_name"), c.get("last_name"), c.get("display_name"))
                break
    result = upload(api, merged, rels, monica_key,
                    self_contact_id=self_contact_id, self_key=self_key)
    print(f"\nUploaded: created {result['created']}, updated {result['updated']} contacts; "
          f"added {result['rel_added']} relationships ({result['rel_skipped']} skipped).")
    errs = result["errors"]
    if errs:
        print(f"\n{len(errs)} error(s):")
        for line in errs[:25]:
            print("  -", line)


if __name__ == "__main__":
    main()
