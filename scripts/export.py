from __future__ import annotations

import argparse
import csv
from pathlib import Path

from backend.db import get_conn


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--version", type=int, required=True)
    p.add_argument(
        "--level", choices=["sector", "group", "industry", "subindustry"], required=True
    )
    p.add_argument("--out", type=Path, required=True)
    args = p.parse_args()
    levels = {
        "sector": ("gics_sector", ["code2", "name"]),
        "group": ("gics_group", ["code4", "name", "sector_code2"]),
        "industry": ("gics_industry", ["code6", "name", "group_code4"]),
        "subindustry": (
            "gics_sub_industry",
            ["code8", "name", "definition", "industry_code6"],
        ),
    }
    table, cols = levels[args.level]
    with get_conn() as conn:
        rows = conn.execute(
            f"SELECT {', '.join(cols)} FROM {table} WHERE version_id=? ORDER BY 1",
            (args.version,),
        ).fetchall()
    with args.out.open("w", newline="") as f:
        writer = csv.writer(f)
        writer.writerow(cols)
        for r in rows:
            writer.writerow([r[c] for c in cols])


if __name__ == "__main__":
    main()
