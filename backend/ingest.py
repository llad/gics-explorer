from __future__ import annotations

import csv
import logging
import re
from pathlib import Path
from typing import Iterable

import pandas as pd

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


_COL_PATTERNS = {
    "sector_code": re.compile(r"sector.*code"),
    "sector_name": re.compile(r"sector.*name"),
    "group_code": re.compile(r"group.*code"),
    "group_name": re.compile(r"group.*name"),
    "industry_code": re.compile(r"industry.*code"),
    "industry_name": re.compile(r"industry.*name"),
    "sub_code": re.compile(r"sub.?industry.*code"),
    "sub_name": re.compile(r"sub.?industry.*name"),
    "definition": re.compile(r"definition"),
}


def _norm(col: str) -> str:
    col = col.strip().lower()
    col = re.sub(r"[-\s]+", "_", col)
    return col


def _clean(val: str | None) -> str | None:
    if val is None:
        return None
    val = str(val).strip()
    return val or None


def _pad(val: str | None, length: int) -> str | None:
    val = _clean(val)
    if val is None:
        return None
    return val.zfill(length)


def load_from_excel(
    xlsx_path: str | Path,
    label: str,
    eff_date: str,
    source_url: str | None = None,
) -> int:
    xlsx_path = Path(xlsx_path)
    sheets = pd.read_excel(xlsx_path, sheet_name=None, dtype=str)
    records: list[dict[str, str]] = []
    for df in sheets.values():
        df = df.rename(columns=lambda c: _norm(str(c)))
        rename_map: dict[str, str] = {}
        for col in list(df.columns):
            n = col
            for key, pat in _COL_PATTERNS.items():
                if key not in rename_map and pat.search(n):
                    rename_map[col] = key
                    break
        df = df.rename(columns=rename_map)
        records.extend(df.to_dict(orient="records"))
    with get_conn() as conn:
        conn.execute("BEGIN")
        cur = conn.execute(
            "INSERT INTO gics_version(label, effective_date, source_url) VALUES (?,?,?)",
            (label, eff_date, source_url),
        )
        version_id = cur.lastrowid
        seen_sec: set[tuple[str, str]] = set()
        seen_grp: set[tuple[str, str, str]] = set()
        seen_ind: set[tuple[str, str, str]] = set()
        seen_sub: set[tuple[str, str, str]] = set()
        for r in records:
            sec_code = _pad(r.get("sector_code"), 2)
            sec_name = _clean(r.get("sector_name"))
            if sec_code and sec_name and (sec_code, sec_name) not in seen_sec:
                conn.execute(
                    "INSERT OR IGNORE INTO gics_sector(code2, name, version_id) VALUES (?,?,?)",
                    (sec_code, sec_name, version_id),
                )
                seen_sec.add((sec_code, sec_name))

            grp_code = _pad(r.get("group_code"), 4)
            grp_name = _clean(r.get("group_name"))
            if grp_code and grp_name:
                if not sec_code:
                    sec_code = _pad(r.get("sector_code"), 2)
                if not sec_code:
                    logging.warning("Skipping group %s due to missing sector", grp_code)
                else:
                    key = (grp_code, grp_name, sec_code)
                    if key not in seen_grp:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_group(code4, name, sector_code2, version_id) VALUES (?,?,?,?)",
                            (grp_code, grp_name, sec_code, version_id),
                        )
                        seen_grp.add(key)

            ind_code = _pad(r.get("industry_code"), 6)
            ind_name = _clean(r.get("industry_name"))
            if ind_code and ind_name:
                if not grp_code:
                    grp_code = _pad(r.get("group_code"), 4)
                if not grp_code:
                    logging.warning(
                        "Skipping industry %s due to missing group", ind_code
                    )
                else:
                    key = (ind_code, ind_name, grp_code)
                    if key not in seen_ind:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_industry(code6, name, group_code4, version_id) VALUES (?,?,?,?)",
                            (ind_code, ind_name, grp_code, version_id),
                        )
                        seen_ind.add(key)

            sub_code = _pad(r.get("sub_code"), 8)
            sub_name = _clean(r.get("sub_name"))
            definition = _clean(r.get("definition"))
            if sub_code and sub_name:
                if not ind_code:
                    ind_code = _pad(r.get("industry_code"), 6)
                if not ind_code:
                    logging.warning(
                        "Skipping sub-industry %s due to missing industry", sub_code
                    )
                else:
                    key = (sub_code, sub_name, ind_code)
                    if key not in seen_sub:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_sub_industry(code8, name, definition, industry_code6, version_id) VALUES (?,?,?,?,?)",
                            (sub_code, sub_name, definition, ind_code, version_id),
                        )
                        seen_sub.add(key)
    return version_id
