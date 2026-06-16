"""Cross-user visibility: private records, partner designation, public sharing."""

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


async def _uid(client) -> int:
    return (await client.get("/api/auth/me")).json()["user"]["id"]


@pytest.mark.asyncio
async def test_public_visible_private_hidden_then_shared(client):
    # User A (first user / admin) creates a public and a private contact.
    await _register(client, "a@example.com", "A")
    public_id = (
        await client.post("/api/contacts", json={"display_name": "Public", "visibility": "public"})
    ).json()["id"]
    private_id = (
        await client.post("/api/contacts", json={"display_name": "Secret", "visibility": "private"})
    ).json()["id"]

    # User B registers (client switches to B).
    await _register(client, "b@example.com", "B")
    b_id = await _uid(client)
    # B sees the public contact but not the private one.
    assert (await client.get(f"/api/contacts/{public_id}")).status_code == 200
    assert (await client.get(f"/api/contacts/{private_id}")).status_code == 404
    names = [c["display_name"] for c in (await client.get("/api/contacts")).json()]
    assert "Public" in names and "Secret" not in names

    # A designates B as a partner.
    await _login(client, "a@example.com")
    assert (await client.put(f"/api/sharing/partners/{b_id}")).status_code == 204

    # Now B can see A's private contact.
    await _login(client, "b@example.com")
    assert (await client.get(f"/api/contacts/{private_id}")).status_code == 200

    # Revoking the partnership hides it again.
    await _login(client, "a@example.com")
    assert (await client.delete(f"/api/sharing/partners/{b_id}")).status_code == 204
    await _login(client, "b@example.com")
    assert (await client.get(f"/api/contacts/{private_id}")).status_code == 404


@pytest.mark.asyncio
async def test_group_visibility(client):
    await _register(client, "a@example.com", "A")
    await _register(client, "b@example.com", "B")
    b_id = await _uid(client)

    # A creates a group, adds B, and a group-visibility contact.
    await _login(client, "a@example.com")
    group_id = (await client.post("/api/groups", json={"name": "Family"})).json()["id"]
    assert (await client.put(f"/api/groups/{group_id}/members/{b_id}")).status_code == 204
    contact_id = (
        await client.post(
            "/api/contacts",
            json={"display_name": "Kin", "visibility": "group", "group_id": group_id},
        )
    ).json()["id"]

    # B, a group member, can see it.
    await _login(client, "b@example.com")
    assert (await client.get(f"/api/contacts/{contact_id}")).status_code == 200


@pytest.mark.asyncio
async def test_cannot_partner_with_self(client):
    await _register(client, "a@example.com", "A")
    a_id = await _uid(client)
    assert (await client.put(f"/api/sharing/partners/{a_id}")).status_code == 400
