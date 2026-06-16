"""Auth flow: first-user-is-admin, login, me, config."""

import pytest


@pytest.mark.asyncio
async def test_first_user_becomes_admin(client):
    resp = await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "password123", "display_name": "A"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["is_superuser"] is True


@pytest.mark.asyncio
async def test_second_user_is_not_admin(client):
    await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "password123", "display_name": "A"},
    )
    # The config endpoint reports registration is allowed in tests (default).
    resp = await client.post(
        "/api/auth/register",
        json={"email": "b@example.com", "password": "password123", "display_name": "B"},
    )
    assert resp.status_code == 200, resp.text
    assert resp.json()["user"]["is_superuser"] is False


@pytest.mark.asyncio
async def test_login_and_me(client):
    await client.post(
        "/api/auth/register",
        json={"email": "a@example.com", "password": "password123", "display_name": "A"},
    )
    # Cookies from register persist on the client; /me should resolve the user.
    me = await client.get("/api/auth/me")
    assert me.status_code == 200
    assert me.json()["user"]["email"] == "a@example.com"

    bad = await client.post(
        "/api/auth/login", json={"email": "a@example.com", "password": "wrong"}
    )
    assert bad.status_code == 401


@pytest.mark.asyncio
async def test_me_requires_auth(client):
    resp = await client.get("/api/auth/me")
    assert resp.status_code == 401
