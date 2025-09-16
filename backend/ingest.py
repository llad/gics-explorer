from __future__ import annotations

import csv
import logging
from pathlib import Path
from typing import Any

import pandas as pd

from .db import get_conn


def load_sample(
    csv_path: str | Path, label: str = "sample", effective_date: str | None = None
) -> int:
    csv_path = Path(csv_path)
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


def _clean(val: str | None) -> str | None:
    if val is None:
        return None
    val = str(val).replace("\xa0", " ").strip()
    if not val:
        return None
    lowered = val.lower()
    if lowered in {"nan", "none"}:
        return None
    return val


def _pad(val: str | None, length: int) -> str | None:
    val = _clean(val)
    if val is None:
        return None
    if not val.isdigit():
        return None
    return val.zfill(length)


def _parse_first_sheet(df: pd.DataFrame) -> list[dict[str, Any]]:
    if df.empty:
        return []

    df = df.copy()
    df.columns = list(range(df.shape[1]))

    records: list[dict[str, Any]] = []
    current: dict[str, str | None] = {
        "sector_code": None,
        "sector_name": None,
        "group_code": None,
        "group_name": None,
        "industry_code": None,
        "industry_name": None,
    }
    pending_record: dict[str, Any] | None = None
    definition_parts: list[str] = []

    for idx in range(len(df)):
        values = [df.iat[idx, col] if col < df.shape[1] else None for col in range(8)]
        (
            sector_code_raw,
            sector_name_raw,
            group_code_raw,
            group_name_raw,
            industry_code_raw,
            industry_name_raw,
            sub_code_raw,
            text_raw,
        ) = values

        sector_code = _pad(sector_code_raw, 2)
        sector_name = _clean(sector_name_raw)
        if sector_code:
            current["sector_code"] = sector_code
            if sector_name:
                current["sector_name"] = sector_name
        elif (
            sector_name
            and current["sector_code"]
            and sector_name.lower() not in {"sector"}
        ):
            current["sector_name"] = sector_name

        group_code = _pad(group_code_raw, 4)
        group_name = _clean(group_name_raw)
        if group_code:
            current["group_code"] = group_code
            if group_name:
                current["group_name"] = group_name
        elif (
            group_name
            and current["group_code"]
            and group_name.lower() not in {"industry group"}
        ):
            current["group_name"] = group_name

        industry_code = _pad(industry_code_raw, 6)
        industry_name = _clean(industry_name_raw)
        if industry_code:
            current["industry_code"] = industry_code
            if industry_name:
                current["industry_name"] = industry_name
        elif (
            industry_name
            and current["industry_code"]
            and industry_name.lower() not in {"industry"}
        ):
            current["industry_name"] = industry_name

        sub_code = _pad(sub_code_raw, 8)
        text = _clean(text_raw)

        if sub_code:
            if pending_record and definition_parts:
                pending_record["definition"] = " ".join(definition_parts)
            definition_parts = []
            pending_record = {
                "sector_code": current["sector_code"],
                "sector_name": current["sector_name"],
                "group_code": current["group_code"],
                "group_name": current["group_name"],
                "industry_code": current["industry_code"],
                "industry_name": current["industry_name"],
                "sub_code": sub_code,
                "sub_name": text,
                "definition": None,
            }
            records.append(pending_record)
            continue

        if pending_record and text:
            definition_parts.append(text)
            pending_record["definition"] = " ".join(definition_parts)

    return records


def load_from_excel(
    xlsx_path: str | Path,
    label: str,
    eff_date: str,
    source_url: str | None = None,
) -> int:
    xlsx_path = Path(xlsx_path)
    df = pd.read_excel(xlsx_path, sheet_name=0, header=None, dtype=str)
    records = _parse_first_sheet(df)
    if not records:
        raise ValueError("no GICS rows found in workbook")
    with get_conn() as conn:
        conn.execute("BEGIN")
        cur = conn.execute(
            "INSERT INTO gics_version(label, effective_date, source_url) VALUES (?,?,?)",
            (label, eff_date, source_url),
        )
        version_id = cur.lastrowid
        inserted_sectors: set[str] = set()
        inserted_groups: set[str] = set()
        inserted_industries: set[str] = set()
        inserted_subs: set[str] = set()
        for r in records:
            sec_code = r.get("sector_code")
            sec_name = _clean(r.get("sector_name"))
            if sec_code and sec_name and sec_code not in inserted_sectors:
                conn.execute(
                    "INSERT OR IGNORE INTO gics_sector(code2, name, version_id) VALUES (?,?,?)",
                    (sec_code, sec_name, version_id),
                )
                inserted_sectors.add(sec_code)

            grp_code = r.get("group_code")
            grp_name = _clean(r.get("group_name"))
            if grp_code and grp_name:
                parent_sec = r.get("sector_code")
                if not parent_sec or parent_sec not in inserted_sectors:
                    logging.warning("Skipping group %s due to missing sector", grp_code)
                else:
                    if grp_code not in inserted_groups:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_group(code4, name, sector_code2, version_id) VALUES (?,?,?,?)",
                            (grp_code, grp_name, parent_sec, version_id),
                        )
                        inserted_groups.add(grp_code)

            ind_code = r.get("industry_code")
            ind_name = _clean(r.get("industry_name"))
            if ind_code and ind_name:
                parent_grp = r.get("group_code")
                parent_sec = r.get("sector_code")
                if not parent_grp:
                    logging.warning(
                        "Skipping industry %s due to missing group", ind_code
                    )
                elif parent_grp not in inserted_groups:
                    logging.warning(
                        "Skipping industry %s due to missing parent group %s",
                        ind_code,
                        parent_grp,
                    )
                else:
                    if ind_code not in inserted_industries:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_industry(code6, name, group_code4, version_id) VALUES (?,?,?,?)",
                            (ind_code, ind_name, parent_grp, version_id),
                        )
                        inserted_industries.add(ind_code)

            sub_code = r.get("sub_code")
            sub_name = _clean(r.get("sub_name"))
            definition = _clean(r.get("definition"))
            if sub_code and sub_name:
                parent_ind = r.get("industry_code")
                parent_grp = r.get("group_code")
                if not parent_ind:
                    logging.warning(
                        "Skipping sub-industry %s due to missing industry", sub_code
                    )
                elif parent_ind not in inserted_industries:
                    logging.warning(
                        "Skipping sub-industry %s due to missing parent industry %s",
                        sub_code,
                        parent_ind,
                    )
                else:
                    if sub_code not in inserted_subs:
                        conn.execute(
                            "INSERT OR IGNORE INTO gics_sub_industry(code8, name, definition, industry_code6, version_id) VALUES (?,?,?,?,?)",
                            (sub_code, sub_name, definition, parent_ind, version_id),
                        )
                        inserted_subs.add(sub_code)
    return version_id
