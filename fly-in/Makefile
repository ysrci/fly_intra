MAP ?= maps/easy/01_linear_path.txt

.PHONY: install run debug clean lint

install:
	@pip install -r requirements.txt

run:
	@python3 main.py $(MAP)

debug:
	@python3 -m pdb main.py $(MAP)

clean:
	@rm -rf __pycache__ .mypy_cache .vscode .test.txt

lint:
	@flake8 . && mypy .  --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs