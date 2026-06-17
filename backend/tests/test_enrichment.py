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
async def test_relationship_labels_are_gendered_by_related_contact(client):
    await _register(client, "a@example.com", "A")
    parent = next(
        t for t in (await client.get("/api/relationship-types")).json() if t["name"] == "Parent"
    )
    # ada (female) is the "Child" side; byron (male) is the "Parent" side.
    ada = (
        await client.post("/api/contacts", json={"display_name": "Ada", "gender": "female"})
    ).json()["id"]
    byron = (
        await client.post("/api/contacts", json={"display_name": "Byron", "gender": "male"})
    ).json()["id"]
    await client.post(
        "/api/relationships",
        json={"from_contact_id": ada, "to_contact_id": byron, "type_id": parent["id"]},
    )
    # From ada's view the related person (byron, male) reads as "Father".
    assert (await client.get(f"/api/contacts/{ada}/relationships")).json()[0]["label"] == "Father"
    # From byron's view the related person (ada, female) reads as "Daughter".
    assert (await client.get(f"/api/contacts/{byron}/relationships")).json()[0]["label"] == "Daughter"

    # A contact with no gender keeps the generic label.
    cleo = (await client.post("/api/contacts", json={"display_name": "Cleo"})).json()["id"]
    await client.post(
        "/api/relationships",
        json={"from_contact_id": ada, "to_contact_id": cleo, "type_id": parent["id"]},
    )
    cleo_label = next(
        r["label"]
        for r in (await client.get(f"/api/contacts/{ada}/relationships")).json()
        if r["contact_id"] == cleo
    )
    assert cleo_label == "Parent"


@pytest.mark.asyncio
async def test_relationship_type_male_female_editable(client):
    await _register(client, "a@example.com", "A")
    types = (await client.get("/api/relationship-types")).json()
    parent = next(t for t in types if t["name"] == "Parent")
    # Seeded gendered defaults are exposed.
    assert parent["name_male"] == "Father" and parent["name_female"] == "Mother"
    assert parent["reverse_name_female"] == "Daughter"

    # Editing the female label is reflected immediately on existing relationships.
    upd = await client.patch(
        f"/api/relationship-types/{parent['id']}", json={"name_female": "Mama"}
    )
    assert upd.status_code == 200
    assert upd.json()["name_female"] == "Mama"

    kid = (await client.post("/api/contacts", json={"display_name": "Kid"})).json()["id"]
    mom = (
        await client.post("/api/contacts", json={"display_name": "Mom", "gender": "female"})
    ).json()["id"]
    await client.post(
        "/api/relationships",
        json={"from_contact_id": kid, "to_contact_id": mom, "type_id": parent["id"]},
    )
    label = (await client.get(f"/api/contacts/{kid}/relationships")).json()[0]["label"]
    assert label == "Mama"


@pytest.mark.asyncio
async def test_auto_grandparents_derived_from_parent_chain(client):
    await _register(client, "a@example.com", "A")
    parent = next(
        t for t in (await client.get("/api/relationship-types")).json() if t["name"] == "Parent"
    )

    async def mk(name, gender=None):
        body = {"display_name": name}
        if gender:
            body["gender"] = gender
        return (await client.post("/api/contacts", json=body)).json()["id"]

    me = await mk("Me")
    mom = await mk("Mom", "female")
    granny = await mk("Granny", "female")
    # me's parent is mom; mom's parent is granny (from=child, to=parent).
    await client.post(
        "/api/relationships", json={"from_contact_id": me, "to_contact_id": mom, "type_id": parent["id"]}
    )
    await client.post(
        "/api/relationships",
        json={"from_contact_id": mom, "to_contact_id": granny, "type_id": parent["id"]},
    )

    mine = {r["contact_name"]: r for r in (await client.get(f"/api/contacts/{me}/relationships")).json()}
    assert mine["Mom"]["label"] == "Mother" and mine["Mom"]["derived"] is False
    assert mine["Granny"]["label"] == "Grandmother"  # auto-derived, gendered
    assert mine["Granny"]["derived"] is True
    assert mine["Granny"]["relationship_id"] == 0

    # The reverse: from Granny's view, Me is an (auto) grandchild.
    hers = {r["contact_name"]: r for r in (await client.get(f"/api/contacts/{granny}/relationships")).json()}
    assert hers["Mom"]["label"] == "Daughter"
    assert hers["Me"]["label"] == "Grandchild" and hers["Me"]["derived"] is True


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
async def test_tag_catalog_rename_recolor_delete(client):
    await _register(client, "a@example.com", "A")
    cid = (
        await client.post("/api/contacts", json={"display_name": "Ada", "tags": ["Friends"]})
    ).json()["id"]
    tag = (await client.get("/api/tags")).json()[0]
    assert tag["name"] == "Friends" and tag["count"] == 1

    # Rename + recolor.
    upd = await client.patch(f"/api/tags/{tag['id']}", json={"name": "Pals", "color": "#123456"})
    assert upd.json()["name"] == "Pals"
    assert upd.json()["color"] == "#123456"
    # The contact reflects the rename.
    c = (await client.get(f"/api/contacts/{cid}")).json()
    assert [t["name"] for t in c["tags"]] == ["Pals"]

    # Duplicate names are rejected.
    assert (await client.post("/api/tags", json={"name": "Pals"})).status_code == 409

    # Deleting the tag removes it from the contact.
    assert (await client.delete(f"/api/tags/{tag['id']}")).status_code == 204
    assert (await client.get(f"/api/contacts/{cid}")).json()["tags"] == []
    assert (await client.get("/api/tags")).json() == []


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
