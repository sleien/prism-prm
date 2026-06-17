#!/usr/bin/env python3
"""Import Monica activities into Prism as calendar events.

Each Monica activity becomes a private, all-day Prism event (title = summary,
description, date = happened_at) with its participant contacts attached as
attendees, matched to existing Prism contacts by name (display name, "first
last", or the import key, plus a few hand-mapped spelling variants). Participants
whose contact no longer exists are dropped. Idempotent: events already present
(same normalized title + date) are skipped, so re-runs don't duplicate.

    python import_monica_events.py --monica monica.sql \
        --base-url https://prism.home.schneider.today --token "$TOKEN" --apply --insecure
"""

from __future__ import annotations

import argparse
import sys
import unicodedata
from collections import defaultdict
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from monica_google_import import Prism, _err, _parse_insert, norm_name, parse_monica  # noqa: E402

# Unresolved participant names confirmed to map to a kept contact (display name).
VARIANT_TO_DISPLAY = {
    "ester fitze": "Esther Fitze",
    "karoline kriemler": "Caroline Kriemler",
    "raffael giezendanner": "Rafael Giezedanner",
}


def norm(s: str | None) -> str:
    base = "".join(c for c in unicodedata.normalize("NFKD", s or "") if not unicodedata.combining(c))
    return " ".join(base.lower().split())


def build_lookup(contacts: list[dict]) -> dict[str, int]:
    look: dict[str, int] = {}
    for c in contacts:
        forms = {
            norm(c.get("display_name")),
            norm(f"{c.get('first_name') or ''} {c.get('last_name') or ''}"),
            norm_name(c.get("first_name"), c.get("last_name"), c.get("display_name")),
        }
        for f in forms:
            if f:
                look.setdefault(f, c["id"])
    return look


def _fix_dates(api: Prism, acts: dict[int, dict], apply: bool) -> None:
    """Repair imported all-day events whose date drifted by a day. An event is
    only touched if its title matches a Monica activity AND its current date is
    exactly one day before that activity's date (so we never touch unrelated or
    already-correct events)."""
    from datetime import date as _date, timedelta

    by_title: dict[str, list[str]] = defaultdict(list)
    for a in acts.values():
        d = (a.get("happened_at") or a.get("created_at") or "")[:10]
        if d:
            by_title[norm((a.get("summary") or "").strip() or "Activity")].append(d)

    fixed = skipped = 0
    for e in api.get("/api/events"):
        intended = by_title.get(norm(e["title"]))
        cur = (e.get("starts_at") or "")[:10]
        target = None
        for d in intended or []:
            y, m, dd = (int(x) for x in d.split("-"))
            if (_date(y, m, dd) - timedelta(days=1)).isoformat() == cur:
                target = d
                break
        if target is None or target == cur:
            skipped += 1
            continue
        if apply:
            api.patch(f"/api/events/{e['id']}", {"starts_at": f"{target}T12:00:00Z"})
        fixed += 1
    print(f"event dates {'fixed' if apply else 'to fix'}: {fixed} | left as-is: {skipped}")


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--monica", required=True, type=Path)
    ap.add_argument("--base-url", required=True)
    ap.add_argument("--token", required=True)
    ap.add_argument("--apply", action="store_true", help="actually create events (default is dry-run)")
    ap.add_argument(
        "--fix-dates",
        action="store_true",
        help="repair already-imported events whose all-day date drifted, matching by title",
    )
    ap.add_argument("--insecure", action="store_true")
    args = ap.parse_args()

    text = args.monica.read_text(encoding="utf-8", errors="replace")
    acts = {int(a["id"]): a for a in _parse_insert(text, "activities")}
    links: dict[int, list[int]] = defaultdict(list)
    for r in _parse_insert(text, "activity_contact"):
        links[int(r["activity_id"])].append(int(r["contact_id"]))
    people, _ = parse_monica(args.monica)

    api = Prism(args.base_url, args.token, verify=not args.insecure)

    if args.fix_dates:
        _fix_dates(api, acts, apply=args.apply)
        return

    look = build_lookup(api.get("/api/contacts"))

    def resolve(mid: int) -> int | None:
        p = people.get(mid)
        if not p:
            return None
        for k in (norm(p.name), p.key):
            if k in look:
                return look[k]
        disp = VARIANT_TO_DISPLAY.get(norm(p.name))
        return look.get(norm(disp)) if disp else None

    existing = {(norm(e["title"]), (e.get("starts_at") or "")[:10]) for e in api.get("/api/events")}

    created = skipped = 0
    dropped: dict[str, int] = defaultdict(int)
    errors: list[str] = []
    for aid, a in sorted(acts.items()):
        title = (a.get("summary") or "").strip() or "Activity"
        date = (a.get("happened_at") or a.get("created_at") or "")[:10]
        if not date or (norm(title), date) in existing:
            skipped += 1
            continue
        ids: list[int] = []
        for c in links.get(aid, []):
            r = resolve(c)
            if r and r not in ids:
                ids.append(r)
            elif r is None:
                dropped[people[c].name if c in people else str(c)] += 1
        payload = {
            "title": title[:300],
            "description": a.get("description") or None,
            # Noon UTC keeps the calendar date stable across time zones for
            # all-day events (matches the app's own convention).
            "starts_at": f"{date}T12:00:00Z",
            "all_day": True,
            "visibility": "private",
            "attendee_contact_ids": ids,
        }
        if not args.apply:
            created += 1
            continue
        try:
            api.post("/api/events", payload)
            existing.add((norm(title), date))
            created += 1
        except Exception as e:  # noqa: BLE001
            errors.append(f"{title!r} ({date}): {_err(e)}")

    verb = "to create" if not args.apply else "created"
    print(f"events {verb}: {created} | skipped (existing/no date): {skipped}")
    if dropped:
        print("dropped (deleted) participants:")
        for n, c in sorted(dropped.items(), key=lambda x: -x[1]):
            print(f"  {c}x {n}")
    if errors:
        print(f"errors ({len(errors)}):")
        for e in errors[:20]:
            print("  -", e)


if __name__ == "__main__":
    main()
