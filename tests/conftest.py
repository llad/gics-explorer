from __future__ import annotations

import os
from pathlib import Path

TEST_DB_DIR = Path(__file__).resolve().parent / "_tmp"
TEST_DB_DIR.mkdir(parents=True, exist_ok=True)
os.environ.setdefault("GICS_DB_PATH", str(TEST_DB_DIR / "gics.db"))
