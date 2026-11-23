.PHONY: install install-runtime health download ingest smoke coverage evaluation-set evaluation evaluation-fixture lint typecheck test verify

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

coverage:
	$(PYTHON) -m zabm coverage

evaluation-set:
	$(PYTHON) -m zabm evaluation-set

evaluation:
	$(PYTHON) -m zabm evaluation

evaluation-fixture:
	$(PYTHON) -m zabm evaluation \
		--evaluation-set data/evaluation/baseline-fixture-v1.json \
		--output data/evaluation/baseline-fixture-results-v1.json

lint:
	$(RUFF) check .
	$(RUFF) format --check .

typecheck:
	$(PYRIGHT)

test:
	$(PYTHON) -m pytest

verify: health lint typecheck test
