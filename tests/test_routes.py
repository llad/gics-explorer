import asyncio
import httpx
import pandas as pd
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


def test_ingest_url(monkeypatch, tmp_path):
    df = pd.DataFrame(
        {
            "Sector Code": ["10"],
            "Sector Name": ["Energy"],
            "Group Code": ["1010"],
            "Group Name": ["Energy Equipment"],
            "Industry Code": ["101010"],
            "Industry Name": ["Oil & Gas Drilling"],
            "Sub Code": ["10101010"],
            "Sub Name": ["Drilling"],
        }
    )
    xlsx = tmp_path / "gics.xlsx"
    df.to_excel(xlsx, index=False)

    def fake_get(self, url, *args, **kwargs):
        return httpx.Response(
            200, content=xlsx.read_bytes(), request=httpx.Request("GET", url)
        )

    monkeypatch.setattr(httpx.Client, "get", fake_get)

    async def inner() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            payload = {
                "url": "http://example.com/gics.xlsx",
                "label": "u1",
                "effective_date": "2024-09-01",
            }
            r = await client.post("/api/ingest-url", json=payload)
            assert r.status_code == 200
            vid = r.json()["version_id"]
            r = await client.get("/api/versions")
            ids = [v["id"] for v in r.json()]
            assert vid in ids

    asyncio.run(inner())
