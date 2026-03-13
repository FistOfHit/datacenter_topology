# Contributing

## Development Setup

1. Use Python 3.12.
2. Create and activate a virtual environment.
3. Install the project in editable mode with development dependencies:

```bash
make install-dev
```

4. Install the Git hooks:

```bash
pre-commit install
```

## Daily Workflow

Run the core checks locally before opening a pull request:

```bash
make lint
make test
```

If you need automatic formatting:

```bash
make format
```

## Pull Request Expectations

- Keep the CLI and output contracts stable unless the change explicitly intends to revise them.
- Add or update tests for any behavior change.
- Prefer behavior-focused tests over mock-heavy implementation tests.
- Update docs when configuration, outputs, or module responsibilities change.
- Do not commit generated outputs such as `output/` or `review_runs/`.

## Repository Conventions

- Runtime behavior lives under `topology_generator/`.
- Long-lived documentation belongs in `docs/`.
- Repo automation is defined in `.pre-commit-config.yaml` and `.github/workflows/`.
