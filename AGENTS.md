# Repository Agent Guide

## Purpose

This repository generates datacenter topologies from YAML input, renders a condensed topology diagram, and exports a per-cable Excel cut-sheet. The public contract is the CLI:

```bash
python -m topology_generator.main --config <path> --output-dir <dir> [--timestamp]
python -m topology_generator --config <path> --output-dir <dir> [--timestamp]
topology-generator --config <path> --output-dir <dir> [--timestamp]
```

Do not change that contract casually.

## High-Signal Commands

```bash
make test
make lint
python -m topology_generator.main --config config.yaml --output-dir output
```

## Important Files

- `topology_generator/main.py`: end-to-end orchestration.
- `topology_generator/config_types.py`: typed configuration model and `TopologyConfig`.
- `topology_generator/config_parser.py` / `topology_generator/config_validation.py`: config parsing and semantic validation.
- `topology_generator/topology_generator.py`: graph construction and link allocation.
- `topology_generator/rendering.py` / `topology_generator/render_layout.py` / `topology_generator/render_drawing.py`: condensed rendering pipeline, layout, and annotation logic.
- `topology_generator/port_mapper.py`: Excel row extraction and export.
- `tests/`: behavior-focused unit and integration coverage.
- `docs/architecture.md`: system-level design notes.
- `docs/configuration.md`: config field meanings and validation expectations.
- `configs/examples/multi_fabric_small.yaml`: minimal shared-`gpu_nodes` example.
- `configs/examples/multi_fabric_backend_frontend.yaml`: larger shared-`gpu_nodes` example with separate backend and frontend fabrics.

## Project Invariants

- Preserve the output filenames `topology.png`, `port_mapping.xlsx`, and `network_topology.log` for single-fabric runs.
- Multi-fabric runs intentionally emit `topology_<fabric>.png` files while still preserving `port_mapping.xlsx` and `network_topology.log`.
- `generate_topology(...)` should keep accepting dict-like config input.
- Links are modeled only between adjacent layers in the ordered `layers:` list.
- Current connection semantics intentionally attempt full adjacency between neighboring layers using the configured per-pair cable count.
- Visualization is condensed for layers with more than two nodes; do not expand the drawing model without a deliberate product decision.
- Multi-fabric mode shares only `gpu_nodes`, which is always layer `0`.
- In multi-fabric mode, validation, rendering, and port-mapping logic must remain fabric-isolated even though one giant graph is built internally.

## Editing Guidance

- Prefer small, behavior-preserving refactors unless the task explicitly asks for a functional change.
- If you touch config handling, update both validation tests and `docs/configuration.md`.
- If you touch outputs or rendering behavior, run the full test suite.
- Generated artifacts in `output/` and `review_runs/` are disposable and should not be committed.

## Testing Expectations

- Prefer `make test` and `make lint`.
- If you need direct commands, use `python3 -m ...` or `./.venv/bin/python -m ...`, not bare `python`, for validation tooling.
- Keep tests behavior-oriented; avoid adding new mock-only tests where a real graph or real file is practical.
