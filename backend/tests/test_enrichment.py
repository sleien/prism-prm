"""Relationships, life events, and their per-user customizable type catalogs."""

import pytest


async def _register(client, email, name):
    r = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": name},
    )
    assert r.status_code == 200, r.text


@pytest.mark.asyncio
async def test_relationship_types_seeded_and_directional(client):
    await _register(client, "a@example.com", "A")
    types = (await client.get("/api/relationship-types")).json()
    assert len(types) >= 5  # seeded on first read
    parent = next(t for t in types if t["name"] == "Parent")

    ada = (await client.post("/api/contacts", json={"display_name": "Ada"})).json()["id"]
    byron = (await client.post("/api/contacts", json={"display_name": "Byron"})).json()["id"]
    r = await client.post(
        "/api/relationships",
        json={"from_contact_id": ada, "to_contact_id": byron, "type_id": parent["id"]},
    )
    assert r.status_code == 201

    ada_rels = (await client.get(f"/api/contacts/{ada}/relationships")).json()
    assert ada_rels[0]["label"] == "Parent"
    assert ada_rels[0]["contact_name"] == "Byron"
    # The reverse side shows the reverse label.
    byron_rels = (await client.get(f"/api/contacts/{byron}/relationships")).json()
    assert byron_rels[0]["label"] == "Child"
    assert byron_rels[0]["contact_name"] == "Ada"


@pytest.mark.asyncio
async def test_relationship_to_self_rejected(client):
    await _register(client, "a@example.com", "A")
    types = (await client.get("/api/relationship-types")).json()
    cid = (await client.post("/api/contacts", json={"display_name": "Solo"})).json()["id"]
    r = await client.post(
        "/api/relationships",
        json={"from_contact_id": cid, "to_contact_id": cid, "type_id": types[0]["id"]},
    )
    assert r.status_code == 400


@pytest.mark.asyncio
async def test_custom_relationship_type(client):
    await _register(client, "a@example.com", "A")
    await client.get("/api/relationship-types")  # seed
    r = await client.post(
        "/api/relationship-types", json={"name": "Mentor", "reverse_name": "Mentee"}
    )
    assert r.status_code == 201
    names = [t["name"] for t in (await client.get("/api/relationship-types")).json()]
    assert "Mentor" in names


@pytest.mark.asyncio
async def test_life_events(client):
    await _register(client, "a@example.com", "A")
    types = (await client.get("/api/life-event-types")).json()
    assert any(t["name"] == "Got married" for t in types)

    cid = (await client.post("/api/contacts", json={"display_name": "Ada"})).json()["id"]
    ev = await client.post(
        "/api/life-events",
        json={
            "contact_id": cid,
            "title": "Moved house",
            "emoji": "🏠",
            "happened_on": "2020-01-01",
        },
    )
    assert ev.status_code == 201
    events = (await client.get(f"/api/contacts/{cid}/life-events")).json()
    assert events[0]["title"] == "Moved house"
    assert events[0]["emoji"] == "🏠"


@pytest.mark.asyncio
async def test_enrichment_is_owner_scoped(client):
    # A adds a life event on a public contact; B must not see A's annotation.
    await _register(client, "a@example.com", "A")
    cid = (
        await client.post("/api/contacts", json={"display_name": "Shared", "visibility": "public"})
    ).json()["id"]
    await client.post("/api/life-events", json={"contact_id": cid, "title": "Secret note"})
    await _register(client, "b@example.com", "B")  # client now B
    # B can see the public contact but not A's life-event annotations on it.
    assert (await client.get(f"/api/contacts/{cid}")).status_code == 200
    assert (await client.get(f"/api/contacts/{cid}/life-events")).json() == []
