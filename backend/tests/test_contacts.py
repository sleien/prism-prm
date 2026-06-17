"""Contact CRUD, visibility enforcement, and the sync trigger (no Nextcloud)."""

import pytest


async def _register(client, email, name):
    resp = await client.post(
        "/api/auth/register",
        json={"email": email, "password": "password123", "display_name": name},
    )
    assert resp.status_code == 200, resp.text


@pytest.mark.asyncio
async def test_create_marks_dirty_and_sets_owner(client):
    await _register(client, "a@example.com", "A")
    resp = await client.post(
        "/api/contacts", json={"display_name": "Grace Hopper", "visibility": "public"}
    )
    assert resp.status_code == 201, resp.text
    body = resp.json()
    assert body["display_name"] == "Grace Hopper"
    assert body["dirty"] is True
    assert body["owner_id"] >= 1
    assert body["nextcloud_uid"]  # a UID is minted up front


@pytest.mark.asyncio
async def test_visibility_hides_private_from_others(client):
    await _register(client, "a@example.com", "A")  # admin (first user)
    secret = await client.post(
        "/api/contacts", json={"display_name": "Secret", "visibility": "private"}
    )
    secret_id = secret.json()["id"]
    pal = await client.post(
        "/api/contacts", json={"display_name": "Public Pal", "visibility": "public"}
    )
    pal_id = pal.json()["id"]

    assert len((await client.get("/api/contacts")).json()) == 2

    # Registering B switches the client's cookies to user B (non-admin).
    await _register(client, "b@example.com", "B")
    names = [c["display_name"] for c in (await client.get("/api/contacts")).json()]
    assert "Public Pal" in names
    assert "Secret" not in names

    # B cannot read or edit the private contact, nor edit the public one it doesn't own.
    assert (await client.get(f"/api/contacts/{secret_id}")).status_code == 404
    assert (
        await client.patch(f"/api/contacts/{pal_id}", json={"notes": "x"})
    ).status_code == 403


@pytest.mark.asyncio
async def test_update_then_delete(client):
    await _register(client, "a@example.com", "A")
    cid = (
        await client.post("/api/contacts", json={"display_name": "Temp"})
    ).json()["id"]

    upd = await client.patch(f"/api/contacts/{cid}", json={"notes": "updated"})
    assert upd.status_code == 200
    assert upd.json()["notes"] == "updated"
    assert upd.json()["dirty"] is True

    assert (await client.delete(f"/api/contacts/{cid}")).status_code == 204
    assert (await client.get(f"/api/contacts/{cid}")).status_code == 404


@pytest.mark.asyncio
async def test_gender_round_trips_and_validates(client):
    await _register(client, "a@example.com", "A")
    created = await client.post(
        "/api/contacts", json={"display_name": "Grace", "gender": "female"}
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert created.json()["gender"] == "female"

    assert (await client.patch(f"/api/contacts/{cid}", json={"gender": "male"})).json()[
        "gender"
    ] == "male"
    # Explicit null clears it back to unspecified.
    assert (await client.patch(f"/api/contacts/{cid}", json={"gender": None})).json()[
        "gender"
    ] is None
    # Unknown values are rejected.
    bad = await client.post("/api/contacts", json={"display_name": "X", "gender": "yes"})
    assert bad.status_code == 422


@pytest.mark.asyncio
async def test_sync_without_nextcloud_is_skipped(client):
    await _register(client, "a@example.com", "A")
    resp = await client.post("/api/contacts/sync")
    assert resp.status_code == 200
    assert resp.json()["skipped_reason"] == "Nextcloud not configured"
