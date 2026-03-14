.PHONY: help install install-dev test lint format check

PYTHON ?= python3

help:
	@printf "Available targets:\n"
	@printf "  install      Install runtime dependencies in editable mode\n"
	@printf "  install-dev  Install runtime and development dependencies\n"
	@printf "  test         Run the full test suite\n"
	@printf "  lint         Run Ruff lint checks\n"
	@printf "  format       Format the codebase with Ruff\n"
	@printf "  check        Run lint and tests\n"

install:
	$(PYTHON) -m pip install -e .

install-dev:
	$(PYTHON) -m pip install -e ".[dev]"

test:
	$(PYTHON) -m pytest -q

lint:
	$(PYTHON) -m ruff check .

format:
	$(PYTHON) -m ruff format .

check: lint test
