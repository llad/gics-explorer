# agents.md

## Purpose
Build a small, extensible web app to **ingest, store, browse, export, and diff** the GICS classification structure. MVP uses **FastAPI**, **SQLite (no ORM)**, and **vanilla JavaScript**. Keep each step shippable.

## Ground Rules
- Prefer **simplicity**: stdlib `sqlite3`, small modules, no heavy frameworks or ORMs.
- Ship in **iterations**; every PR must run end-to-end locally.
- Maintain **clean separation**: backend API, ingestion utilities, static frontend.
- Add **scriptable commands** for repeatable tasks.
- Include **tests** where it’s cheap (route smoke tests, ingestion unit tests).
- Keep **licensing/IP** in mind: we handle *structure & definitions* publicly; company→GICS mappings are licensed and out-of-scope for MVP.

---

## Tech Stack
- Backend: **FastAPI**, **Uvicorn**
- Data: **SQLite** via `sqlite3` (row_factory = Row)
- Parsing: **pandas** (later for Excel), **csv** for MVP
- Frontend: **static HTML/CSS/JS** (no build step)
- Tests: **pytest**, **httpx** (for ASGI client)
- Lint/format: **ruff**, **black**
- Scripts: **Makefile** (or `justfile`) + small Python CLIs in `scripts/`

---

## Repo Layout
```
gics-app/
  backend/
    main.py            # FastAPI app + routes
    db.py              # sqlite init + connection helpers
    ingest.py          # loader functions (CSV MVP, Excel later)
    sample_gics.csv    # tiny seed
    static/
      index.html
      app.js
      styles.css
  scripts/
    seed.py            # run sample ingest
    export.py          # CLI to export CSV by level/version
    check_updates.py   # (stub) download+checksum + ingest + diff
  tests/
    test_routes.py
    test_ingest.py
  .env.example
  requirements.txt
  Makefile
  README.md
  agents.md
```

---

## Database Schema (no ORM)
Enable `PRAGMA foreign_keys=ON`.

```sql
CREATE TABLE IF NOT EXISTS gics_version(
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  label TEXT NOT NULL,            -- e.g., 'sample-1' or '2024-08'
  effective_date TEXT,            -- ISO date
  source_url TEXT,
  checksum TEXT
);

CREATE TABLE IF NOT EXISTS gics_sector(
  code2 TEXT NOT NULL,
  name TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code2, version_id),
  FOREIGN KEY(version_id) REFERENCES gics_version(id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_group(
  code4 TEXT NOT NULL,
  name TEXT NOT NULL,
  sector_code2 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code4, version_id),
  FOREIGN KEY(sector_code2, version_id) REFERENCES gics_sector(code2, version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_industry(
  code6 TEXT NOT NULL,
  name TEXT NOT NULL,
  group_code4 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code6, version_id),
  FOREIGN KEY(group_code4, version_id) REFERENCES gics_group(code4, version_id) ON DELETE CASCADE
);

CREATE TABLE IF NOT EXISTS gics_sub_industry(
  code8 TEXT NOT NULL,
  name TEXT NOT NULL,
  definition TEXT,
  industry_code6 TEXT NOT NULL,
  version_id INTEGER NOT NULL,
  PRIMARY KEY(code8, version_id),
  FOREIGN KEY(industry_code6, version_id) REFERENCES gics_industry(code6, version_id) ON DELETE CASCADE
);

-- For future diffs:
-- CREATE TABLE gics_diff(
--   id INTEGER PRIMARY KEY AUTOINCREMENT,
--   version_from INTEGER NOT NULL,
--   version_to INTEGER NOT NULL,
--   level TEXT NOT NULL,    -- sector|group|industry|subindustry
--   code TEXT NOT NULL,
--   change_type TEXT NOT NULL, -- added|removed|renamed|moved
--   detail TEXT
-- );
```

---

## API (MVP)
- `GET /api/versions` → `[ { id, label, effective_date } ]`
- `GET /api/tree/{version_id}` → hierarchy: sector→group→industry→sub_industry
- `GET /api/export/{version_id}/{level}` → CSV where `level in {sector|group|industry|subindustry}`

**Non-goals (for MVP):** search, auth, uploads. Add later.

---

## Frontend (MVP)
Static page showing:
- Version selector (populated from `/api/versions`)
- Tree viewer fetched from `/api/tree/{version_id}`
- Four CSV export buttons that link to `/api/export/...`

No frameworks or build step.

---

## Iteration Plan

### Iteration 1 — Working Scaffold (MVP)
**Deliverables**
- Running FastAPI app serving the static UI and the three endpoints.
- SQLite DB initialized on first run; seed with `sample_gics.csv`.
- Make targets to install, run, test, and lint.

**Acceptance**
- `make dev` starts server; UI loads, shows sample tree.
- CSV export downloads files with expected headers/rows.
- Basic tests pass.

### Iteration 2 — Adminless Ingest from Excel (Manual file path)
**Deliverables**
- `ingest.py` gains `load_from_excel(xlsx_path, label, eff_date, source_url)` using pandas.
- A `scripts/seed.py --excel path.xlsx --label "YYYY-MM" --effective 2024-08-01` to create a new version.
- README docs for obtaining the official “GICS Structure” workbook manually and running the ingest script.

**Acceptance**
- Loading the workbook creates a new `gics_version`; tree includes full official hierarchy.
- Previous version remains intact (versioned tables).

### Iteration 3 — Change Monitor (Checksum + Diff)
**Deliverables**
- `scripts/check_updates.py` downloads the current-structure workbook (URL configurable via `.env`), computes SHA256, compares to latest `gics_version.checksum`, ingests if changed, and computes diffs into `gics_diff`.
- Backend: `GET /api/diff/{from}/{to}` returns structured changes.
- Frontend: simple “What changed?” view (latest two versions).

**Acceptance**
- Changing the source file produces an additional version and a non-empty diff payload.
- Diff API lists added/removed/renamed/moved codes.

---

## Agent Roles & Loop

### 1) Planner
- Read this file and the repo.
- Create/maintain a task list in `README.md` under “Backlog”.
- For each iteration, propose a tiny scope with acceptance tests.

### 2) Implementer
- Write minimal, clean code and docs.
- Prefer pure functions for ingestion/CSV writing.
- Keep SQL in small helper functions inside `db.py` or per-module.

### 3) Reviewer
- Run `make lint test` locally.
- Verify endpoints with `httpx` tests.
- Reject scope creep; request follow-ups if requirements unclear.

### 4) Data Ingester
- Implement `load_sample()` (CSV) and `load_from_excel()` (pandas).
- Normalize codes to 2/4/6/8 digits as strings, preserve leading zeros (if any).

### 5) Diff Monitor (later)
- Implement checksum, version creation, and diff generation.
- Diff logic: compare sets per level keyed by `(code, name, parent_code)`.

### 6) UI Dev
- Keep HTML semantic and JS minimal (no frameworks).
- Avoid global leaks; namespaced functions in `app.js`.

---

## Coding Conventions

**Python**
- Type hints on public functions.
- `sqlite3.Row` row_factory; access by column name.
- Small modules. Functions ≤50–60 lines if possible.
- Logging: `logging` stdlib; INFO for major steps.

**JS**
- No frameworks. Fetch API with async/await.
- DOM helpers only; no custom state management.

**Git**
- Commit messages: `<area>: <short message>` (e.g., `api: add /api/export route`).
- One change per commit. Keep diffs readable.

---

## Makefile (expected targets)
```make
.PHONY: venv install dev lint test format seed export

venv:
	python -m venv .venv

install: venv
	. .venv/bin/activate && pip install -r requirements.txt

dev:
	. .venv/bin/activate && uvicorn backend.main:app --reload

lint:
	. .venv/bin/activate && ruff check .
	. .venv/bin/activate && black --check .

format:
	. .venv/bin/activate && black .

test:
	. .venv/bin/activate && pytest -q

seed:
	. .venv/bin/activate && python scripts/seed.py --csv backend/sample_gics.csv --label sample-1 --effective 2024-08-01

export:
	. .venv/bin/activate && python scripts/export.py --version 1 --level subindustry --out /tmp/subs.csv
```

---

## Requirements
```
fastapi
uvicorn[standard]
pandas
python-multipart
pytest
httpx
ruff
black
```

---

## Minimal Files (MVP expectations)

**backend/db.py**
- `get_conn()` with `sqlite3.connect("gics.db")` and `Row` factory
- `init_db()` runs schema (see above)

**backend/ingest.py**
- `load_sample(csv_path) -> version_id`
- `load_from_excel(xlsx_path, label, eff_date, source_url=None) -> version_id` (stub in Iteration 1; implement in Iteration 2)

**backend/main.py**
- `init_db()` + seed if empty
- Routes: `/api/versions`, `/api/tree/{version_id}`, `/api/export/{version_id}/{level}`
- Static mount for `/`

**backend/static/index.html, app.js, styles.css**
- Basic UI elements and fetch logic

**scripts/seed.py**
- CLI to create a version and load CSV/XLSX
- Flags: `--csv | --excel`, `--label`, `--effective`, `--source-url`

**scripts/export.py**
- CLI to export to CSV by `--version` and `--level`

**tests/test_routes.py**
- Spin up app with `from backend.main import app`
- Use `httpx.AsyncClient` to assert 200s + payload shapes

**README.md**
- 5-minute quickstart, run, endpoints, and next steps

---

## Security/Compliance Notes
- This repo handles *structure & definitions only*. Do not ingest or distribute *company mappings* without explicit license.
- Add attribution in the UI footer and README when ingesting official files.

---

## Backlog (initial)
- [ ] Iteration 1: scaffold + CSV seed + endpoints + static UI + tests
- [ ] Iteration 2: Excel ingest path + CLI + docs
- [ ] Iteration 3: change monitor + diff API + minimal UI
- [ ] Search endpoint `/api/search?q=` across names/definitions
- [ ] Small admin upload UI (authenticated) for manual Excel ingest

---

## Definition of Done (per iteration)
- Runs locally with `make dev`
- Tests pass; coverage includes happy path
- Docs updated (README + changelog snippet)
- No TODOs left in code for committed features

---

## Kickoff Prompt (paste into Codex)
> You are the lead engineer. Build **Iteration 1** of the GICS Explorer using FastAPI, SQLite (no ORM), and vanilla JS as specified in `agents.md`.  
> Deliverables: project layout, schema + `init_db()`, `load_sample()` with `backend/sample_gics.csv`, endpoints `/api/versions`, `/api/tree/{version_id}`, `/api/export/{version_id}/{level}`, static UI (version selector, tree, CSV buttons), minimal tests, Makefile targets.  
> Constraints: keep modules small, high clarity, no ORMs or frontend frameworks.  
> When done, run tests and list exact commands I should run to boot the app locally.
