from __future__ import annotations

import argparse
from pathlib import Path

from backend.db import init_db
from backend.ingest import load_sample


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--csv", type=Path, required=True)
    p.add_argument("--label", required=True)
    p.add_argument("--effective", required=False)
    args = p.parse_args()
    init_db()
    load_sample(args.csv, args.label, args.effective)


if __name__ == "__main__":
    main()
