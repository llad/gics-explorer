from __future__ import annotations

import csv
import tempfile
from io import StringIO
from pathlib import Path
from typing import Any

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import StreamingResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from .db import get_conn, init_db
from .ingest import load_from_excel, load_sample

app = FastAPI()


@app.on_event("startup")
def startup() -> None:
    init_db()
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_version")
        if cur.fetchone()[0] == 0:
            load_sample(
                Path(__file__).with_name("sample_gics.csv"), "sample-1", "2024-08-01"
            )


@app.get("/api/versions")
def get_versions() -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute(
            "SELECT id, label, effective_date FROM gics_version ORDER BY id"
        )
        return [dict(row) for row in cur.fetchall()]


class IngestURL(BaseModel):
    url: str
    label: str
    effective_date: str


@app.post("/api/ingest-url")
def ingest_url(payload: IngestURL) -> dict[str, int]:
    try:
        with httpx.Client() as client:
            resp = client.get(payload.url)
            resp.raise_for_status()
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        raise HTTPException(status_code=400, detail="download failed") from exc
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = Path(tmp.name)
    try:
        version_id = load_from_excel(
            tmp_path, payload.label, payload.effective_date, payload.url
        )
    finally:
        tmp_path.unlink(missing_ok=True)
    return {"version_id": version_id}


@app.get("/api/tree/{version_id}")
def get_tree(version_id: int) -> list[dict[str, Any]]:
    with get_conn() as conn:
        cur = conn.execute("SELECT id FROM gics_version WHERE id=?", (version_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="version not found")
        sectors = conn.execute(
            "SELECT code2, name FROM gics_sector WHERE version_id=? ORDER BY code2",
            (version_id,),
        ).fetchall()
        result = []
        for sec in sectors:
            groups = conn.execute(
                "SELECT code4, name FROM gics_group WHERE version_id=? AND sector_code2=? ORDER BY code4",
                (version_id, sec["code2"]),
            ).fetchall()
            group_list = []
            for grp in groups:
                industries = conn.execute(
                    "SELECT code6, name FROM gics_industry WHERE version_id=? AND group_code4=? ORDER BY code6",
                    (version_id, grp["code4"]),
                ).fetchall()
                ind_list = []
                for ind in industries:
                    subs = conn.execute(
                        "SELECT code8, name, definition FROM gics_sub_industry WHERE version_id=? AND industry_code6=? ORDER BY code8",
                        (version_id, ind["code6"]),
                    ).fetchall()
                    ind_list.append(
                        {
                            "code": ind["code6"],
                            "name": ind["name"],
                            "subs": [dict(s) for s in subs],
                        }
                    )
                group_list.append(
                    {"code": grp["code4"], "name": grp["name"], "industries": ind_list}
                )
            result.append(
                {"code": sec["code2"], "name": sec["name"], "groups": group_list}
            )
        return result


@app.get("/api/export/{version_id}/{level}")
def export_level(version_id: int, level: str):
    levels = {
        "sector": ("gics_sector", ["code2", "name"]),
        "group": ("gics_group", ["code4", "name", "sector_code2"]),
        "industry": ("gics_industry", ["code6", "name", "group_code4"]),
        "subindustry": (
            "gics_sub_industry",
            ["code8", "name", "definition", "industry_code6"],
        ),
    }
    if level not in levels:
        raise HTTPException(status_code=400, detail="invalid level")
    table, cols = levels[level]
    with get_conn() as conn:
        cur = conn.execute("SELECT id FROM gics_version WHERE id=?", (version_id,))
        if cur.fetchone() is None:
            raise HTTPException(status_code=404, detail="version not found")
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM {table} WHERE version_id=? ORDER BY 1",
            (version_id,),
        ).fetchall()
    buf = StringIO()
    writer = csv.writer(buf)
    writer.writerow(cols)
    for r in rows:
        writer.writerow([r[c] for c in cols])
    buf.seek(0)
    return StreamingResponse(buf, media_type="text/csv")


app.mount(
    "/",
    StaticFiles(directory=Path(__file__).with_name("static"), html=True),
    name="static",
)
