PYTHON ?= python
PYREF := reference/python

.PHONY: compile schemas compliance check test lint release-check

lint:
	$(PYTHON) -m ruff check reference/python tests scripts --select E9,F63,F7,F82

test:
	$(PYTHON) -m pytest tests --cov=$(PYREF) --cov-report=json:coverage.json --junitxml=test-results.xml -q

check: lint test compile schemas

release-check: check
	$(PYTHON) scripts/verify_release.py

compile:
	$(PYTHON) -m compileall $(PYREF)

schemas:
	$(PYTHON) -c "import json, pathlib; [json.load(open(p, encoding='utf-8')) for p in pathlib.Path('schemas').glob('*.json')]; print('PASS json_schemas_parse')"

compliance:
	cd $(PYREF) && $(PYTHON) verify_compliance_runtime.py
