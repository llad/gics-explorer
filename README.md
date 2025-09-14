# GICS Explorer

Minimal GICS browser built with FastAPI, SQLite and vanilla JavaScript.

## Quickstart

```bash
make venv
make install
make seed
make dev
```

Visit http://localhost:8000 to browse.

## Deployment

App platforms like DigitalOcean require an explicit start command. A `Procfile` is included to run the app:

```
web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
```
