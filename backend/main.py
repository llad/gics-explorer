from __future__ import annotations

import csv
import logging
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
from .ingest import load_from_excel

app = FastAPI()

logger = logging.getLogger(__name__)


DEFAULT_INGEST_URL = (
    "https://www.msci.com/documents/1296102/29559863/"
    "GICS_structure_and_definitions_effective_close_of_March_17_2023.xlsx"
)
DEFAULT_LABEL = "2023-03-17"
DEFAULT_EFFECTIVE_DATE = "2023-03-17"


def _ingest_workbook_from_url(url: str, label: str, effective_date: str) -> int:
    logger.info(
        "Downloading workbook from %s for label=%s (effective=%s)",
        url,
        label,
        effective_date,
    )
    with httpx.Client() as client:
        resp = client.get(url)
        resp.raise_for_status()
    logger.info("Downloaded %d bytes from %s", len(resp.content), url)
    with tempfile.NamedTemporaryFile(suffix=".xlsx", delete=False) as tmp:
        tmp.write(resp.content)
        tmp_path = Path(tmp.name)
    logger.debug("Saved temporary workbook to %s", tmp_path)
    try:
        version_id = load_from_excel(tmp_path, label, effective_date, url)
        logger.info(
            "Workbook ingest completed for label=%s version_id=%s",
            label,
            version_id,
        )
    finally:
        tmp_path.unlink(missing_ok=True)
        logger.debug("Removed temporary workbook %s", tmp_path)
    return version_id


@app.on_event("startup")
def startup() -> None:
    init_db()
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_version")
        if cur.fetchone()[0] == 0:
            logger.info(
                "No GICS data found; ingesting default workbook from %s",
                DEFAULT_INGEST_URL,
            )
            try:
                _ingest_workbook_from_url(
                    DEFAULT_INGEST_URL,
                    DEFAULT_LABEL,
                    DEFAULT_EFFECTIVE_DATE,
                )
            except httpx.HTTPError:  # pragma: no cover - network failure on startup
                logger.exception(
                    "Default ingest failed while downloading %s", DEFAULT_INGEST_URL
                )
            except Exception:  # pragma: no cover - unexpected ingest failure
                logger.exception(
                    "Default ingest failed for workbook %s", DEFAULT_INGEST_URL
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
    logger.info(
        "Received ingest request for url=%s label=%s effective_date=%s",
        payload.url,
        payload.label,
        payload.effective_date,
    )
    try:
        version_id = _ingest_workbook_from_url(
            payload.url, payload.label, payload.effective_date
        )
    except httpx.HTTPError as exc:  # pragma: no cover - network failure
        logger.exception("Download failed for %s", payload.url)
        raise HTTPException(status_code=400, detail="download failed") from exc
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
                            "subs": [
                                {
                                    "code": s["code8"],
                                    "name": s["name"],
                                    "definition": s["definition"],
                                }
                                for s in subs
                            ],
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
