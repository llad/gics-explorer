import asyncio

import httpx
import pytest

from backend.db import DB_PATH, init_db
from backend.ingest import load_sample
from backend.main import app
from pathlib import Path


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    load_sample(Path("backend/sample_gics.csv"), "sample", "2024-01-01")
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_versions_and_tree():
    async def inner() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            r = await client.get("/api/versions")
            assert r.status_code == 200
            vid = r.json()[0]["id"]
            r = await client.get(f"/api/tree/{vid}")
            assert r.status_code == 200
            assert isinstance(r.json(), list)

    asyncio.run(inner())
