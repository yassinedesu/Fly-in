SRC= src

install:
	python3 -m venv .venv
	./.venv/bin/python3 -m pip install -r requirements.txt
run:
	./.venv/bin/python3 -m $(SRC) $(MAP)

debug:
	./.venv/bin/python3 -m pdb -m $(SRC) $(MAP)

clean:
	find . -type d -name __pycache__ -exec rm -rf {} +
	rm -rf .mypy_cache

lint:
	./.venv/bin/python3 -m mypy src/ --warn-return-any --warn-unused-ignores --ignore-missing-imports --disallow-untyped-defs --check-untyped-defs
	./.venv/bin/python3 -m flake8 src

lint-strict:
	./.venv/bin/python3 -m mypy src --strict
	./.venv/bin/python3 -m flake8 src

.PHONY: install run debug clean lint lint-strict