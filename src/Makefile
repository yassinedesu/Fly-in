MAIN = main.py
MAP ?= $(if $(ARGS),$(ARGS),maps/easy/01_linear_path.txt)

install:
	python3 -m pip install -r requirements.txt

run:
	python3 $(MAIN) $(MAP)

debug:
	python3 -m pdb $(MAIN) $(MAP)

clean:
	find . -type d -name "__pycache__" -exec rm -rf {} +
	rm -rf .mypy_cache

lint:
	python3 -m mypy --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs *.py
	python3 -m flake8 *.py

lint-strict:
	python3 -m mypy --strict *.py
	python3 -m flake8 *.py

.PHONY: install run debug clean lint lint-strict
