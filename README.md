# Datacenter Topology Generator

Generate datacenter network topologies from YAML, visualize them as a condensed diagram, and export a per-cable Excel cut-sheet.

## What This Repo Does

The tool builds a layered `networkx` model from an ordered list of generic layers. Layer order defines topology semantics:

- layer `0` is the bottom of the fabric
- layer `N-1` is the top of the fabric
- links are only modeled between adjacent layers

From that model it produces:

- `topology.png`
- `port_mapping.xlsx`
- `network_topology.log`

The CLI contract is unchanged:

```bash
python -m topology_generator.main --config <config.yaml> --output-dir <output_dir> [--timestamp]
```

Installed console entry point:

```bash
topology-generator --config <config.yaml> --output-dir <output_dir> [--timestamp]
```

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

### Run

```bash
python -m topology_generator.main --config config.yaml --output-dir output
```

Timestamped output directory:

```bash
python -m topology_generator.main --config config.yaml --output-dir output --timestamp
```

## Configuration

The input is a YAML mapping with a single ordered `layers:` list. Each layer defines its own node count, shared port capacity, and connectivity to the adjacent layers above and below it.

Example:

```yaml
layers:
  - name: gpu_server
    node_count_in_layer: 16
    ports_per_node: 4
    port_bandwidth_gb_per_port: 400
    uplink_cables_per_node_to_each_node_in_next_layer: 1
    uplink_cable_bandwidth_gb: 400

  - name: leaf_sw
    node_count_in_layer: 4
    ports_per_node: 18
    port_bandwidth_gb_per_port: 800
    downlink_cables_per_node_to_each_node_in_previous_layer: 1
    downlink_cable_bandwidth_gb: 400
    uplink_cables_per_node_to_each_node_in_next_layer: 1
    uplink_cable_bandwidth_gb: 800

  - name: spine_sw
    node_count_in_layer: 2
    ports_per_node: 6
    port_bandwidth_gb_per_port: 800
    downlink_cables_per_node_to_each_node_in_previous_layer: 1
    downlink_cable_bandwidth_gb: 800
    uplink_cables_per_node_to_each_node_in_next_layer: 2
    uplink_cable_bandwidth_gb: 800

  - name: core_sw
    node_count_in_layer: 1
    ports_per_node: 4
    port_bandwidth_gb_per_port: 800
    downlink_cables_per_node_to_each_node_in_previous_layer: 2
    downlink_cable_bandwidth_gb: 800
```

More detail:

- [Configuration Reference](docs/configuration.md)
- [Worked Examples](docs/examples.md)

## How It Works

1. Parse CLI arguments.
2. Create the output directory and configure logging.
3. Load YAML into a validated `TopologyConfig`.
4. Build a `networkx.Graph` across the ordered layers.
5. Connect each layer densely to the next layer using the configured per-pair cable count.
6. Render the condensed topology diagram.
7. Flatten graph edges into per-cable Excel rows.

Design details:

- [Architecture Overview](docs/architecture.md)
- [Agent Guide](AGENTS.md)

## Development

Helpful commands:

```bash
make lint
make test
make check
make format
```

The repository includes:

- `Ruff` for linting and formatting
- `pytest` for behavior-first testing
- `mypy` configuration for static analysis
- `pre-commit` hooks for local quality gates
- GitHub Actions for lint and test CI

## Notes and Constraints

- The schema is generic and position-based; layer names are optional labels only.
- Links are modeled only between adjacent layers in the ordered list.
- The connection strategy is intentionally dense: every node in layer `i` attempts the configured number of links to every node in layer `i+1`.
- Visualization is intentionally condensed for larger layers; it is a planning view, not a full physical layout renderer.
- Generated outputs under `output/` and `review_runs/` are disposable.

## License

MIT. See [LICENSE](LICENSE).
