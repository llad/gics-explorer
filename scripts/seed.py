from __future__ import annotations

import argparse
from pathlib import Path

from backend.db import init_db
from backend.ingest import load_from_excel, load_sample


def main() -> None:
    p = argparse.ArgumentParser()
    g = p.add_mutually_exclusive_group(required=True)
    g.add_argument("--csv", type=Path)
    g.add_argument("--excel", type=Path)
    p.add_argument("--label", required=True)
    p.add_argument("--effective", required=True)
    p.add_argument("--source-url")
    args = p.parse_args()
    init_db()
    if args.csv:
        load_sample(args.csv, args.label, args.effective)
    else:
        load_from_excel(args.excel, args.label, args.effective, args.source_url)


if __name__ == "__main__":
    main()
