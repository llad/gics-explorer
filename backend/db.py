from __future__ import annotations

import sqlite3
from pathlib import Path
from sqlite3 import Connection, Row

DB_PATH = Path("gics.db")


def get_conn() -> Connection:
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    schema = Path(__file__).with_name("schema.sql")
    with get_conn() as conn, open(schema) as f:
        conn.executescript(f.read())
