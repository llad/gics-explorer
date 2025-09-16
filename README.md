# GICS Explorer

Minimal GICS browser built with FastAPI, SQLite and vanilla JavaScript.

## Quickstart

```bash
make venv
make install
make dev
```

On first launch the app downloads and ingests the official GICS structure from
`https://www.msci.com/documents/1296102/29559863/GICS_structure_and_definitions_effective_close_of_March_17_2023.xlsx`.
Visit http://localhost:8000 to browse. Use `make seed` if you want to load the
small sample CSV instead.

## Database storage

The app stores its SQLite database at `/var/lib/gics-explorer/gics.db` so data
survives application restarts and new deployments. Set the
`GICS_DB_PATH` environment variable if you need to place the database elsewhere
(for example when running locally without permission to create `/var/lib`
directories).

### Ingest via URL

The web UI lets you add a new GICS version by URL. Enter the Excel file URL,
label, and effective date then click **Ingest** to download and process it.

## Load from Excel

To ingest an official GICS Structure workbook:

```bash
python scripts/seed.py --excel path/to/gics.xlsx --label 2024-08 --effective 2024-08-01 [--source-url URL]
```

This creates a new `gics_version` and populates all hierarchy levels.

## Deployment

App platforms like DigitalOcean expect both a build step and a start command.
During the build step install dependencies, for example:

```
pip install -r requirements.txt
```

A `Procfile` is included to run the app during the start phase:

```
web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
```
