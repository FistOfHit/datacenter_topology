# Datacenter Topology Generator

Generate datacenter network topologies from YAML, render condensed topology
diagrams, and export a per-cable Excel cut-sheet.

The tool takes a topology config as input and produces:

- a topology diagram
- an Excel port mapping
- a run log

Single-fabric runs write:

- `topology.png`
- `port_mapping.xlsx`
- `network_topology.log`

Multi-fabric runs still write one `port_mapping.xlsx` and one
`network_topology.log`, but emit one diagram per fabric such as
`topology_backend.png`.

## CLI

The supported entrypoints are:

```bash
python -m topology_generator.main --config <config_path> --output-dir <output_dir>
python -m topology_generator --config <config_path> --output-dir <output_dir>
topology-generator --config <config_path> --output-dir <output_dir>
```

Add `--timestamp` to place the outputs in a timestamped subdirectory under the
given output directory.

## High-Level Model

The config defines an ordered list of layers and explicit links between adjacent
layers.

- Single-fabric mode uses `groups`, `layers`, and `links`.
- Multi-fabric mode shares one `gpu_nodes` layer across multiple isolated
  fabrics via `groupings`, `gpu_nodes`, and `fabrics`.
- Port capacity is modeled in lane units, so one device can legally expose more
  than one port speed from the same hardware budget.

## Quick Start

### Prerequisites

- Python 3.12+

### Install

Runtime install:

```bash
make install
```

Development install:

```bash
make install-dev
pre-commit install
```

### Run A Small Single-Fabric Example

```bash
python -m topology_generator.main \
  --config configs/examples/two_tier_small.yaml \
  --output-dir output/two_tier_small
```

### Run A Small Multi-Fabric Example

```bash
python -m topology_generator.main \
  --config configs/examples/multi_fabric_small.yaml \
  --output-dir output/multi_fabric_small
```

For the full set of shipped examples and their expected outputs, see
[Worked Examples](docs/examples.md).

## Configuration

The YAML stays intentionally explicit.

Single-fabric configs look like:

```yaml
groups:
  - ...
layers:
  - ...
links:
  - ...
```

Multi-fabric configs look like:

```yaml
groupings:
  - ...
gpu_nodes:
  total_nodes: ...
  fabric_port_layouts:
    backend: ...
fabrics:
  - ...
```

Use [Configuration Reference](docs/configuration.md) for the canonical schema
and validation rules.

## Where To Go Next

- [Configuration Reference](docs/configuration.md): canonical config contract
- [Architecture Overview](docs/architecture.md): how the pipeline is structured
- [Worked Examples](docs/examples.md): shipped example configs and expected results
- [Contributing](CONTRIBUTING.md): developer workflow, validation, and profiling
- [Agent Guide](AGENTS.md): repo-specific guidance for coding agents

## License

MIT. See [LICENSE](LICENSE).
