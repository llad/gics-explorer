from __future__ import annotations

import csv
from pathlib import Path
from typing import Iterable

from .db import get_conn


def load_sample(
    csv_path: str | Path, label: str = "sample", effective_date: str | None = None
) -> int:
    csv_path = Path(csv_path)
    rows: Iterable[dict[str, str]]
    with csv_path.open() as f:
        rows = list(csv.DictReader(f))
    with get_conn() as conn:
        cur = conn.execute(
            "INSERT INTO gics_version(label, effective_date) VALUES (?, ?)",
            (label, effective_date),
        )
        version_id = cur.lastrowid
        for r in rows:
            conn.execute(
                "INSERT OR IGNORE INTO gics_sector(code2, name, version_id) VALUES (?,?,?)",
                (r["sector_code"], r["sector_name"], version_id),
            )
            conn.execute(
                "INSERT OR IGNORE INTO gics_group(code4, name, sector_code2, version_id) VALUES (?,?,?,?)",
                (
                    r["group_code"],
                    r["group_name"],
                    r["sector_code"],
                    version_id,
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO gics_industry(code6, name, group_code4, version_id) VALUES (?,?,?,?)",
                (
                    r["industry_code"],
                    r["industry_name"],
                    r["group_code"],
                    version_id,
                ),
            )
            conn.execute(
                "INSERT OR IGNORE INTO gics_sub_industry(code8, name, definition, industry_code6, version_id) VALUES (?,?,?,?,?)",
                (
                    r["sub_code"],
                    r["sub_name"],
                    r.get("definition"),
                    r["industry_code"],
                    version_id,
                ),
            )
    return version_id
