from pathlib import Path

from backend.db import init_db, get_conn, DB_PATH
from backend.ingest import load_sample


def setup_module(module):
    if DB_PATH.exists():
        DB_PATH.unlink()
    init_db()


def test_load_sample_inserts_data():
    vid = load_sample(Path("backend/sample_gics.csv"), "sample", "2024-01-01")
    assert vid == 1
    with get_conn() as conn:
        cur = conn.execute("SELECT COUNT(*) FROM gics_sector WHERE version_id=1")
        assert cur.fetchone()[0] == 2
