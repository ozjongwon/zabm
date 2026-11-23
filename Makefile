.PHONY: install install-runtime health download ingest smoke lint typecheck test verify

PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
PYRIGHT := .venv/bin/pyright

install:
	./scripts/install-dev.sh

install-runtime:
	./scripts/install-dev.sh --profile runtime

health:
	$(PYTHON) -m zabm health

download:
	./scripts/download-sources.sh

ingest:
	./scripts/ingest-sources.sh

smoke:
	$(PYTHON) -m zabm retrieval-smoke

lint:
	$(RUFF) check .
	$(RUFF) format --check .

typecheck:
	$(PYRIGHT)

test:
	$(PYTHON) -m pytest

verify: health lint typecheck test
