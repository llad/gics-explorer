from __future__ import annotations

from pathlib import Path

import asyncio

import pandas as pd
import pytest

from backend.db import DB_PATH, get_conn, init_db
from backend.ingest import load_from_excel, load_sample


@pytest.fixture(autouse=True)
def fresh_db():
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()
    yield
    if DB_PATH.exists():
        DB_PATH.unlink()


def test_load_sample_inserts_data():
    vid = load_sample(Path("backend/sample_gics.csv"), "sample", "2024-01-01")
    assert vid == 1
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_sector WHERE version_id=1")
        assert cur.fetchone()[0] == 2


def test_load_excel_happy_path(monkeypatch):
    df = pd.DataFrame(
        {
            "sector code": ["1", "1"],
            "sector name": ["Energy", "Energy"],
            "group-code": ["101", "101"],
            "group name": ["Equip", "Equip"],
            "industry code": ["10101", "10101"],
            "industry name": ["Drilling", "Drilling"],
            "subindustry code": ["1010101", "1010101"],
            "subindustry name": ["Drill Sub", "Drill Sub"],
        }
    )

    def fake_read_excel(*args, **kwargs):
        return {"Sheet1": df}

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    vid = load_from_excel("dummy.xlsx", "2024-08", "2024-08-01")
    assert vid == 1
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT code2, name FROM gics_sector WHERE version_id=?", (vid,)
        )
        assert [tuple(r) for r in cur.fetchall()] == [("01", "Energy")]
        cur = conn.execute(
            "SELECT code4, name, sector_code2 FROM gics_group WHERE version_id=?",
            (vid,),
        )
        assert [tuple(r) for r in cur.fetchall()] == [("0101", "Equip", "01")]
        cur = conn.execute(
            "SELECT code6, name, group_code4 FROM gics_industry WHERE version_id=?",
            (vid,),
        )
        assert [tuple(r) for r in cur.fetchall()] == [("010101", "Drilling", "0101")]
        cur = conn.execute(
            "SELECT code8, name, industry_code6 FROM gics_sub_industry WHERE version_id=?",
            (vid,),
        )
        assert [tuple(r) for r in cur.fetchall()] == [
            ("01010101", "Drill Sub", "010101")
        ]


def test_missing_parent(monkeypatch, caplog):
    df = pd.DataFrame(
        {
            "group code": ["202"],
            "group name": ["No Sector"],
        }
    )

    def fake_read_excel(*args, **kwargs):
        return {"Sheet1": df}

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    with caplog.at_level("WARNING"):
        vid = load_from_excel("dummy.xlsx", "2024-09", "2024-09-01")
    assert vid == 1
    assert "missing sector" in caplog.text
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_group WHERE version_id=?", (vid,))
        assert cur.fetchone()[0] == 0


def test_api_reflects_excel(monkeypatch):
    df = pd.DataFrame(
        {
            "sectorcode": ["1"],
            "sectorname": ["Energy"],
            "groupcode": ["101"],
            "groupname": ["Equip"],
            "industrycode": ["10101"],
            "industryname": ["Drilling"],
            "subindustrycode": ["1010101"],
            "subindustryname": ["Drill Sub"],
        }
    )

    def fake_read_excel(*args, **kwargs):
        return {"Sheet1": df}

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)
    vid = load_from_excel("dummy.xlsx", "2024-10", "2024-10-01")

    import httpx
    from backend.main import app

    async def inner() -> None:
        transport = httpx.ASGITransport(app=app)
        async with httpx.AsyncClient(
            transport=transport, base_url="http://test"
        ) as client:
            r = await client.get("/api/versions")
            assert any(v["id"] == vid for v in r.json())
            r = await client.get(f"/api/tree/{vid}")
            tree = r.json()
            assert tree[0]["code"] == "01"
            assert tree[0]["groups"][0]["code"] == "0101"

    asyncio.run(inner())
