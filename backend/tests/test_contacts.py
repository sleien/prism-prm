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
async def test_telegram_round_trips(client):
    await _register(client, "a@example.com", "A")
    created = await client.post(
        "/api/contacts", json={"display_name": "Grace", "telegram": "graceh"}
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    assert created.json()["telegram"] == "graceh"
    assert (await client.patch(f"/api/contacts/{cid}", json={"telegram": None})).json()[
        "telegram"
    ] is None


@pytest.mark.asyncio
async def test_new_contact_is_public_by_default(client):
    await _register(client, "a@example.com", "A")
    body = (await client.post("/api/contacts", json={"display_name": "Pat"})).json()
    assert body["visibility"] == "public"


@pytest.mark.asyncio
async def test_phone_formatted_to_settings_pattern_on_save(client):
    await _register(client, "a@example.com", "A")  # defaults: +41 / xxx xxx xx xx
    created = await client.post(
        "/api/contacts",
        json={
            "display_name": "Grace",
            "phones": [
                {"type": "cell", "value": "0793360802"},
                {"type": "home", "value": "+41 44 558 68 08"},
                {"type": "work", "value": "+39 339 416 0855"},  # foreign, untouched
            ],
        },
    )
    phones = {p["type"]: p["value"] for p in created.json()["phones"]}
    assert phones["cell"] == "079 336 08 02"
    assert phones["home"] == "044 558 68 08"
    assert phones["work"] == "+39 339 416 0855"


@pytest.mark.asyncio
async def test_tags_create_and_update(client):
    await _register(client, "a@example.com", "A")
    created = await client.post(
        "/api/contacts", json={"display_name": "Ada", "tags": ["Family", "Work"]}
    )
    assert created.status_code == 201, created.text
    cid = created.json()["id"]
    names = sorted(t["name"] for t in created.json()["tags"])
    assert names == ["Family", "Work"]
    assert all(t["color"] for t in created.json()["tags"])  # auto-colored

    # Catalog reflects the auto-created tags with counts.
    cat = {t["name"]: t["count"] for t in (await client.get("/api/tags")).json()}
    assert cat["Family"] == 1 and cat["Work"] == 1

    # Replacing the tag set drops Work and keeps Family.
    upd = await client.patch(f"/api/contacts/{cid}", json={"tags": ["Family"]})
    assert [t["name"] for t in upd.json()["tags"]] == ["Family"]
    assert {t["name"]: t["count"] for t in (await client.get("/api/tags")).json()}["Work"] == 0


@pytest.mark.asyncio
async def test_sync_without_nextcloud_is_skipped(client):
    await _register(client, "a@example.com", "A")
    resp = await client.post("/api/contacts/sync")
    assert resp.status_code == 200
    assert resp.json()["skipped_reason"] == "Nextcloud not configured"
