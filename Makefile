.PHONY: install run debug clean lint

install:
	pip install flake8 mypy

run:
	python3 main.py map.txt

debug:
	python3 -m pdb main.py map.txt

clean:
	rm -rf __pycache__ .mypy_cache .pytest_cache

lint:
	flake8 .
	mypy . --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs