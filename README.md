<div align="center">

# 🔷 Prism

**A self-hosted personal relationship manager that keeps your contacts in Nextcloud.**

Prism turns your Nextcloud address book into a warm, private CRM for your life:
track the people you care about, log events and what they cost, keep a
customizable journal / feeling tracker, and have reminders land natively in your
Nextcloud calendar. Multi-user, SSO via Authentik, with public / group / private
visibility so families and circles can share what they choose.

</div>

> **Status:** all core phases implemented and tested end-to-end against a
> Nextcloud-compatible DAV server (auth, contacts, events, journal, summaries,
> sharing, weather), with an adversarial QA hardening pass. See the
> [roadmap](#roadmap).

---

## Why "Prism"?

A prism splits white light into a spectrum. Prism splits your relationships into
facets — public, group, and private — and into the many things you track about
the people in your life. One source of truth (Nextcloud), many views.

## Features

- **Nextcloud-backed contacts.** Your CardDAV address book is the source of
  truth. Prism mirrors it, lets you manage contacts with a rich UI, and writes
  changes back. Your phone and desktop keep seeing the same contacts.
- **Rich contact profiles.** Full vCard data — multiple emails/phones/addresses,
  birthday (with age), organization/title — all syncing back to Nextcloud. Plus
  a map of the contact's address and Prism-side enrichment: customizable
  **relationships** (partner / parent / …) and **life events** (got married,
  moved house, …), with per-user editable catalogs.
- **Events with optional cost.** Log get-togethers, attach attendees (contacts
  and/or users), and record what an outing cost.
- **Reminders into your Nextcloud calendar.** Events and reminders are pushed as
  `VEVENT` + `VALARM`, so notifications fire natively in Nextcloud even if Prism
  is asleep.
- **Journal / feeling tracker.** Build your own daily or weekly check-in from mood
  scales and free-text prompts; get reminded; watch mood trends over time.
- **Summary pages.** Per-contact, per-period and dashboard overviews.
- **Weather enrichment.** Optional forecast for events with a location, via
  Open-Meteo (no API key).
- **Multi-user + SSO.** In-app **Authentik OIDC** login (plus optional local
  accounts). Authentik groups flow in to drive visibility.
- **Visibility tiers.** Every record is **public** (all users), **group** (a
  circle / an event's attendees), or **private** (you + designated partners),
  enforced at the query layer.

## Architecture

```
                ┌──────────── Browser (React SPA) ────────────┐
                │   contacts · calendar · journal · summaries  │
                └───────────────────┬──────────────────────────┘
                                    │ /api (cookies or API token)
                        ┌───────────▼───────────┐
                        │   FastAPI (one image)  │
                        │  auth · CRUD · sync     │      ┌─────────────┐
   Authentik (OIDC) ◀───┤  APScheduler loop  ────┼─────▶│  Nextcloud  │
                        │                        │ CardDAV/CalDAV (DAV)
                        └───────────┬────────────┘      └─────────────┘
                                    │ asyncpg
                              ┌─────▼─────┐
                              │ Postgres  │
                              └───────────┘
```

- **One container** serves the API and the built SPA (multi-stage Docker image).
- **Nextcloud is canonical** for contacts. A scheduler syncs every
  `SYNC_INTERVAL_MINUTES`; edits are written back with ETag-based conflict
  handling (Nextcloud wins on conflict).
- **Postgres** stores Prism-only data (events, journal, visibility, reminders)
  using `JSONB` for customizable journal templates and contact custom fields.

Backend: Python 3.12 · FastAPI · SQLAlchemy 2 (async) · Alembic · Authlib ·
`httpx` DAV client · `vobject`/`icalendar` · APScheduler.
Frontend: React + Vite (TypeScript).

## Quick start (production, behind Traefik + Authentik)

This mirrors the deployment pattern of the other apps on the stack (Traefik on a
shared external `proxy` network, Homepage + Uptime-Kuma autodiscovery). Unlike a
forward-auth setup, **Prism does its own Authentik OIDC**, so no forward-auth
middleware is attached to its router.

```bash
cp .env.example .env
# edit .env: SECRET_KEY, POSTGRES_PASSWORD, OIDC_*, NEXTCLOUD_*
docker compose up -d
```

The image is published to `ghcr.io/sleien/prism-prm`. CI builds a multi-arch
(amd64 + arm64) image on every push to `main`.

### Configure Authentik

1. Create an **OAuth2/OIDC provider** + application in Authentik.
2. Redirect URI: `${PUBLIC_URL}/api/auth/oidc/callback`.
3. Put the issuer URL in `OIDC_ISSUER`, plus the client id/secret.
4. (Optional) add a **groups** scope/claim so Prism can map Authentik groups to
   its visibility groups, and set `OIDC_ADMIN_GROUP` to grant admin.

### Configure Nextcloud

1. Create an **app password** (Nextcloud → Settings → Security → Devices &
   sessions) and put it in `NEXTCLOUD_APP_PASSWORD` with `NEXTCLOUD_USERNAME`.
2. Set `NEXTCLOUD_URL` (no trailing slash), and the address book / calendar
   slugs (`NEXTCLOUD_ADDRESSBOOK`, `NEXTCLOUD_CALENDAR`).

## Local development & tests

A self-contained stack with a **Radicale** server standing in for Nextcloud's
CardDAV/CalDAV (same protocols, boots in seconds):

```bash
docker compose -f docker-compose.test.yml up --build
# Prism on http://localhost:8000 ; Radicale on http://localhost:5232
```

Backend tests (Postgres, schema built from models):

```bash
cd backend
pip install -e ".[dev]"
DATABASE_URL=postgresql+asyncpg://prism:prism@localhost:5432/prism_test pytest -q
```

## Configuration

See [`.env.example`](.env.example) for the full, commented list. The essentials:

| Variable | What it does |
| --- | --- |
| `SECRET_KEY` | Signs sessions/JWTs. `openssl rand -hex 32`. |
| `PUBLIC_URL` | External URL; used for OIDC redirects. |
| `POSTGRES_*` | Database credentials. |
| `OIDC_*` | Authentik OIDC provider + admin group. |
| `NEXTCLOUD_*` | URL, app-password creds, address book / calendar, sync interval. |
| `WEATHER_ENABLED` | Toggle Open-Meteo enrichment. |

## Project layout

```
backend/   FastAPI app (app/api, app/models, app/services, app/integrations)
frontend/  React + Vite SPA            (coming in Phase 1)
Dockerfile docker-compose.yml          production (Traefik/Authentik labels)
           docker-compose.test.yml     dev/test stack with Radicale mock
```

## Roadmap

- ✅ **Phase 1** — scaffold, auth (OIDC + local), Nextcloud contact sync, contacts UI.
- ✅ **Phase 2** — events + cost, CalDAV push, VALARM reminders, events UI.
- ✅ **Phase 3** — journal / feeling tracker, dashboard summaries.
- ✅ **Phase 4** — query-layer visibility (public/group/private + partners), weather.
- ✅ **Phase 5** — adversarial QA hardening pass (auth, validation, visibility leaks).

Future ideas: PostgreSQL row-level security (defense-in-depth), per-user
Nextcloud account linking, a full month/week calendar grid, recurring-event
editing, and web-push notifications.

## License

[AGPL-3.0](LICENSE).
