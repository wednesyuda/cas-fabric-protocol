PYTHON ?= python
PYREF := reference/python

.PHONY: compile schemas compliance

compile:
	$(PYTHON) -m compileall $(PYREF)

schemas:
	$(PYTHON) -c "import json, pathlib; [json.load(open(p, encoding='utf-8')) for p in pathlib.Path('schemas').glob('*.json')]; print('PASS json_schemas_parse')"

compliance:
	cd $(PYREF) && $(PYTHON) verify_compliance_runtime.py
