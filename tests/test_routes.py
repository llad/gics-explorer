import httpx
import pytest

from backend.db import DB_PATH
from backend.main import app


@pytest.fixture(autouse=True, scope="module")
def setup_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


@pytest.mark.asyncio
async def test_versions_and_tree():
    async with httpx.AsyncClient(app=app, base_url="http://test") as client:
        r = await client.get("/api/versions")
        assert r.status_code == 200
        vid = r.json()[0]["id"]
        r = await client.get(f"/api/tree/{vid}")
        assert r.status_code == 200
        assert isinstance(r.json(), list)
