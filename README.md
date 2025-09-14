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

App platforms like DigitalOcean expect both a build step and a start command.
During the build step install dependencies, for example:

```
pip install -r requirements.txt
```

A `Procfile` is included to run the app during the start phase:

```
web: uvicorn backend.main:app --host 0.0.0.0 --port ${PORT:-8080}
```
