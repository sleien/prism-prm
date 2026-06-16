"""Pytest fixtures: a clean schema per test and an ASGI HTTP client.

Tests run against PostgreSQL (matching production). Point DATABASE_URL at a
disposable test database before running.
"""

import os

os.environ.setdefault("SECRET_KEY", "test-secret-key-at-least-32-bytes-long!!")
os.environ.setdefault(
    "DATABASE_URL",
    "postgresql+asyncpg://prism:prism@localhost:5432/prism_test",
)
# Each test runs on its own event loop; disable pooling to avoid reusing
# asyncpg connections bound to a closed loop.
os.environ["DB_DISABLE_POOL"] = "true"
# Never start the background scheduler during tests.
os.environ["SCHEDULER_ENABLED"] = "false"

import httpx  # noqa: E402
import pytest_asyncio  # noqa: E402
from httpx import ASGITransport  # noqa: E402

from app.db import Base, engine  # noqa: E402
from app.main import app  # noqa: E402


@pytest_asyncio.fixture(autouse=True)
async def clean_db():
    """Rebuild the schema before each test so model changes are always reflected."""
    async with engine.begin() as conn:
        await conn.exec_driver_sql("DROP SCHEMA public CASCADE")
        await conn.exec_driver_sql("CREATE SCHEMA public")
        await conn.run_sync(Base.metadata.create_all)
    yield


@pytest_asyncio.fixture
async def client():
    transport = ASGITransport(app=app)
    async with httpx.AsyncClient(transport=transport, base_url="http://test") as c:
        yield c


@pytest_asyncio.fixture
async def auth_client(client):
    """A client registered as a fresh user (the first user becomes admin)."""
    resp = await client.post(
        "/api/auth/register",
        json={
            "email": "owner@example.com",
            "password": "password123",
            "display_name": "Owner",
        },
    )
    assert resp.status_code == 200, resp.text
    return client
