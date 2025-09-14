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
