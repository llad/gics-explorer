from __future__ import annotations

import asyncio

import pandas as pd
import pytest

from pathlib import Path

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


def _make_first_sheet(rows: list[list[str | None]]) -> pd.DataFrame:
    data = [row + [None] * (8 - len(row)) for row in rows]
    return pd.DataFrame(data)


def test_load_excel_happy_path(monkeypatch):
    df = _make_first_sheet(
        [
            [
                "Sector",
                None,
                "Industry Group",
                None,
                "Industry",
                None,
                "Sub-Industry",
                None,
            ],
            [
                "1",
                "Energy",
                "101",
                "Equip",
                "10101",
                "Drilling",
                "1010101",
                "Drill Sub",
            ],
            [None, None, None, None, None, None, None, "This is a definition."],
        ]
    )

    def fake_read_excel(*args, **kwargs):
        return df

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
            "SELECT code8, name, definition, industry_code6 FROM gics_sub_industry WHERE version_id=?",
            (vid,),
        )
        assert [tuple(r) for r in cur.fetchall()] == [
            ("01010101", "Drill Sub", "This is a definition.", "010101")
        ]


def test_missing_parent(monkeypatch, caplog):
    df = _make_first_sheet(
        [
            [
                "Sector",
                None,
                "Industry Group",
                None,
                "Industry",
                None,
                "Sub-Industry",
                None,
            ],
            [
                None,
                None,
                "202",
                "No Sector",
                "202010",
                "Test Industry",
                "20201010",
                "Test Sub",
            ],
        ]
    )

    def fake_read_excel(*args, **kwargs):
        return df

    monkeypatch.setattr(pd, "read_excel", fake_read_excel)

    with caplog.at_level("WARNING"):
        vid = load_from_excel("dummy.xlsx", "2024-09", "2024-09-01")
    assert vid == 1
    assert "missing sector" in caplog.text
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_group WHERE version_id=?", (vid,))
        assert cur.fetchone()[0] == 0


def test_api_reflects_excel(monkeypatch):
    df = _make_first_sheet(
        [
            [
                "Sector",
                None,
                "Industry Group",
                None,
                "Industry",
                None,
                "Sub-Industry",
                None,
            ],
            [
                "1",
                "Energy",
                "101",
                "Equip",
                "10101",
                "Drilling",
                "1010101",
                "Drill Sub",
            ],
            [None, None, None, None, None, None, None, "Definition"],
        ]
    )

    def fake_read_excel(*args, **kwargs):
        return df

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
