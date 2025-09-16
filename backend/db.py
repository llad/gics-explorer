from __future__ import annotations

import logging
import os
import sqlite3
from pathlib import Path
from sqlite3 import Connection, Row

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("/var/lib/gics-explorer/gics.db")
DB_PATH = Path(os.environ.get("GICS_DB_PATH", DEFAULT_DB_PATH)).expanduser()


def _ensure_parent_directory(path: Path) -> None:
    parent = path.parent
    if parent and parent != Path("."):
        try:
            parent.mkdir(parents=True, exist_ok=True)
        except PermissionError as exc:
            raise RuntimeError(
                f"Unable to create database directory {parent!s}."
            ) from exc


def get_conn() -> Connection:
    _ensure_parent_directory(DB_PATH)
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = Row
    conn.execute("PRAGMA foreign_keys = ON")
    return conn


def init_db() -> None:
    schema = Path(__file__).with_name("schema.sql")
    with get_conn() as conn, open(schema) as f:
        conn.executescript(f.read())
