# Improvement Notes

This document is not part of the normative product contract.

- Use [configuration.md](configuration.md) for the supported config shape.
- Use [architecture.md](architecture.md) for the current implementation
  structure.
- Treat this file as a lightweight record of follow-up opportunities after the
  major config/render refactors already landed.

## Current State

At the time of this note:

- the config pipeline is already split across `config_identifiers.py`,
  `config_types.py`, `config_parser.py`, and `config_validation.py`
- the render pipeline is already split across `render_environment.py`,
  `render_formatting.py`, `render_types.py`, `render_layout.py`,
  `render_drawing.py`, and `rendering.py`
- the CLI/output contract remains stable
- the automated suite is expected to stay green via:
  - `make lint`
  - `make test`
  - `./.venv/bin/python -m mypy`

## Remaining Follow-Up Opportunities

- Keep import-time side effects low.
  - Favor lazy loading for heavy rendering dependencies.
  - Avoid filesystem or environment mutation on parse-only/help paths.
- Preserve and extend contract-level coverage.
  - Keep the shipped example smoke suite current.
  - Cover module entrypoints and console-script behavior explicitly.
- Do performance work only from measurements.
  - Re-profile the larger shipped examples before scheduling optimization work.
  - Preserve row ordering, lane allocation behavior, and rendered output
    semantics if internals are optimized.
- Continue cleaning up naming drift from the refactor.
  - Prefer current architecture names in tests and contributor docs.
  - Avoid leaving references to removed modules as if they were still primary.

## Working Rule

Behavior-preserving cleanup should remain the default. Product-level changes,
schema changes, and rendering changes should be proposed separately and
documented in dedicated forward-looking design notes.
