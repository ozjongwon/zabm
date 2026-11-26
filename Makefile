.PHONY: install install-runtime runtime-server runtime-models runtime-smoke health download ingest smoke coverage evaluation-set evaluation evaluation-fixture acceptance lint typecheck test verify

PYTHON := .venv/bin/python
RUFF := .venv/bin/ruff
PYRIGHT := .venv/bin/pyright
EXECUTION_ENVIRONMENT ?= remote-llm

install:
	./scripts/install-dev.sh

install-runtime:
	./scripts/install-runtime.sh

runtime-server:
	./scripts/start-runtime-server.sh

runtime-models:
	./scripts/select-runtime-models.sh

runtime-smoke:
	./scripts/runtime-smoke.sh

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

acceptance:
	$(PYTHON) -m zabm acceptance \
		--execution-environment $(EXECUTION_ENVIRONMENT)

lint:
	$(RUFF) check .
	$(RUFF) format --check .

typecheck:
	$(PYRIGHT)

test:
	$(PYTHON) -m pytest

verify: health lint typecheck test
