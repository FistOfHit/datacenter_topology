.PHONY: help install install-dev test lint format check

help:
	@printf "Available targets:\n"
	@printf "  install      Install runtime dependencies in editable mode\n"
	@printf "  install-dev  Install runtime and development dependencies\n"
	@printf "  test         Run the full test suite\n"
	@printf "  lint         Run Ruff lint checks\n"
	@printf "  format       Format the codebase with Ruff\n"
	@printf "  check        Run lint and tests\n"

install:
	pip install -e .

install-dev:
	pip install -e ".[dev]"

test:
	python -m pytest -q

lint:
	python -m ruff check .

format:
	python -m ruff format .

check: lint test
