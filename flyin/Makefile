PYTHON = python3
PIP = pip3
MAIN = main.py
MAP ?= maps/easy/01_linear_path.txt

.PHONY: install run debug clean lint lint-strict

install:
	@if [ -f requirements.txt ]; then $(PIP) install --break-system-packages -r requirements.txt; fi

run:
	$(PYTHON) $(MAIN) $(MAP)

debug:
	$(PYTHON) -m pdb $(MAIN) $(MAP)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	find . -type d -name ".mypy_cache" -exec rm -rf {} +

lint:
	flake8 . && mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs

lint-strict:
	flake8 . && mypy . --strict