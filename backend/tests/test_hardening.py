"""Regression tests for the issues found in the adversarial QA pass."""

import pytest


async def _register(client, email, name):
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": name},
    )
    assert r.status_code == 200, r.text


async def _login(client, email):
    r = await client.post("/api/auth/login", json={"email": email, "password": "password123"})
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_bearer_token_auth_works(client):
    """C1: a personal API token authenticates (previously 500'd on last_used_at)."""
    await _register(client, "a@example.com", "A")
    token = (await client.post("/api/auth/tokens", json={"name": "cli"})).json()["token"]
    client.cookies.clear()  # force Bearer path, not the cookie
    me = await client.get("/api/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert me.status_code == 200, me.text
    assert me.json()["user"]["email"] == "a@example.com"


@pytest.mark.asyncio
async def test_admin_does_not_bypass_private(client):
    """C2: the instance admin cannot see another user's private records."""
    await _register(client, "a@example.com", "A")  # first user -> admin
    await _register(client, "b@example.com", "B")  # client now B (non-admin)
    cid = (
        await client.post(
            "/api/contacts", json={"display_name": "BSecret", "visibility": "private"}
        )
    ).json()["id"]
    await _login(client, "a@example.com")  # admin, not partnered with B
    assert (await client.get(f"/api/contacts/{cid}")).status_code == 404


@pytest.mark.asyncio
async def test_group_id_validation(client):
    """H1/H2: bad or non-member group_id is rejected, not a 500 or a leak."""
    await _register(client, "a@example.com", "A")
    assert (
        await client.post(
            "/api/contacts", json={"display_name": "x", "visibility": "group", "group_id": 9999}
        )
    ).status_code == 403
    assert (
        await client.post("/api/contacts", json={"display_name": "x", "visibility": "group"})
    ).status_code == 400


@pytest.mark.asyncio
async def test_input_validation_returns_4xx(client):
    """H1/L1/L2: oversized strings, reminder overflow, and end-before-start are 4xx."""
    await _register(client, "a@example.com", "A")
    assert (await client.post("/api/contacts", json={"display_name": "Z" * 400})).status_code == 422
    assert (
        await client.post(
            "/api/events",
            json={
                "title": "x",
                "starts_at": "2026-07-01T10:00:00Z",
                "reminders": [{"minutes_before": 10**18}],
            },
        )
    ).status_code == 422
    assert (
        await client.post(
            "/api/events",
            json={
                "title": "x",
                "starts_at": "2026-07-01T10:00:00Z",
                "ends_at": "2026-07-01T09:00:00Z",
            },
        )
    ).status_code == 422


@pytest.mark.asyncio
async def test_users_directory_hides_admin_flag(client):
    """M1: the user directory must not disclose is_superuser."""
    await _register(client, "a@example.com", "A")
    users = (await client.get("/api/users")).json()
    assert users and all("is_superuser" not in u for u in users)


@pytest.mark.asyncio
async def test_sync_requires_admin(client):
    """M2: the instance-wide sync trigger is admin-only."""
    await _register(client, "a@example.com", "A")  # admin
    await _register(client, "b@example.com", "B")  # non-admin (client now B)
    assert (await client.post("/api/contacts/sync")).status_code == 403


@pytest.mark.asyncio
async def test_private_event_not_leaked_via_attendee(client):
    """L4: adding someone as an attendee of a PRIVATE event does not expose it."""
    await _register(client, "a@example.com", "A")
    await _register(client, "b@example.com", "B")  # client now B
    await _login(client, "a@example.com")
    # A has a contact whose email matches user B, attached to a private event.
    cid = (
        await client.post(
            "/api/contacts",
            json={"display_name": "B-link", "emails": [{"type": "home", "value": "b@example.com"}]},
        )
    ).json()["id"]
    priv = (
        await client.post(
            "/api/events",
            json={
                "title": "Private",
                "starts_at": "2026-08-01T19:00:00Z",
                "visibility": "private",
                "attendee_contact_ids": [cid],
            },
        )
    ).json()["id"]
    grp = (
        await client.post(
            "/api/events",
            json={
                "title": "Group",
                "starts_at": "2026-08-02T19:00:00Z",
                "visibility": "group",
                "attendee_contact_ids": [cid],
            },
        )
    ).json()["id"]
    await _login(client, "b@example.com")
    assert (await client.get(f"/api/events/{priv}")).status_code == 404  # private stays hidden
    assert (await client.get(f"/api/events/{grp}")).status_code == 200  # group = attended
