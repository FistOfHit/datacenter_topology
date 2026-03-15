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

The `make` targets assume your active shell resolves `python3` to an
environment where the project dependencies are installed. If you prefer not to
activate a virtual environment, use the direct `./.venv/bin/python ...`
commands shown below.

## Validation Levels

Use the smallest validation step that matches the change, then finish with the
full project checks before opening a pull request.

Focused checks for a touched area:

```bash
./.venv/bin/python -m pytest -q tests/unit/test_main.py
./.venv/bin/python -m pytest -q tests/unit/test_config_pipeline.py
```

Core full-repo checks:

```bash
make lint
make test
```

Equivalent direct commands:

```bash
./.venv/bin/python -m ruff check .
./.venv/bin/python -m pytest -q
```

Advisory type checking:

```bash
./.venv/bin/python -m mypy
```

Shipped example smoke coverage:

```bash
./.venv/bin/python -m pytest -q tests/test_examples_smoke.py
```

## Smoke Checks

The repository already includes automated smoke coverage for every YAML file in
`configs/examples/`.

Run the smoke suite when:

- you change documented example expectations
- you change execution flow or output handling
- you want end-to-end confidence beyond a focused unit test

Use [docs/examples.md](docs/examples.md) for the expected output files and row
counts of the shipped examples.

## When To Update Docs

Update docs whenever a change affects:

- config shape, field meaning, or validation behavior
- CLI behavior, output filenames, or output locations
- worked example expectations
- module responsibilities or the high-level execution flow
- contributor workflow that other developers are expected to follow

As a rule:

- `README.md` should stay short and first-use friendly
- `docs/configuration.md` is the normative config contract
- `docs/architecture.md` explains system structure and design choices
- `CONTRIBUTING.md` covers developer workflow and maintenance guidance

## How To Validate Doc Changes

When you add or change a documented command:

1. Re-run the exact command as written.
2. Confirm the documented output files and paths still match reality.
3. Prefer tying workflow claims to existing tests where practical.

When a doc change describes supported behavior:

- point to an existing automated test when one exists
- or run an explicit smoke command before merging the change

## Profiling Large Topologies

For an end-to-end profile of a CLI run, use `cProfile`:

```bash
./.venv/bin/python -m cProfile \
  -o /tmp/topology_generator_profile.prof \
  -m topology_generator.main \
  --config configs/examples/three_tier_small.yaml \
  --output-dir /tmp/topology_generator_profile_output
```

Inspect the profile with `pstats`:

```bash
./.venv/bin/python -m pstats /tmp/topology_generator_profile.prof
```

Recommended profiling inputs:

- `configs/examples/three_tier_small.yaml`
- `configs/examples/multi_fabric_backend_frontend_oob.yaml`

Notes:

- a full CLI profile includes import time, rendering, and file output work
- use the smaller examples first when validating the profiling workflow itself

## Pull Request Expectations

- Keep the CLI and output contracts stable unless the change explicitly intends
  to revise them.
- Add or update tests for any behavior change.
- Prefer behavior-focused tests over mock-heavy implementation tests.
- Update docs when configuration, outputs, or module responsibilities change.
- Do not commit generated outputs such as `output/` or `review_runs/`.

## Repository Conventions

- Runtime behavior lives under `topology_generator/`.
- Long-lived documentation belongs in `docs/`.
- Repo automation is defined in `.pre-commit-config.yaml` and
  `.github/workflows/`.
