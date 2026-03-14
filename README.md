# Datacenter Topology Generator

Generate grouped datacenter network topologies from YAML, render condensed topology diagrams, and export a per-cable Excel cut-sheet.

Single-fabric runs produce:

- `topology.png`
- `port_mapping.xlsx`
- `network_topology.log`

Multi-fabric runs still produce one `port_mapping.xlsx` and one `network_topology.log`, but emit one diagram per fabric such as `topology_backend.png`.

The CLI entrypoints are:

```bash
python -m topology_generator.main --config <config_path> --output-dir <output_dir>
python -m topology_generator --config <config_path> --output-dir <output_dir>
topology-generator --config <config_path> --output-dir <output_dir>
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
python -m topology_generator.main --config configs/examples/two_tier_small.yaml --output-dir output
```

Add `--timestamp` to create a timestamped output directory:

```bash
python -m topology_generator.main --config configs/examples/two_tier_small.yaml --output-dir output --timestamp
```

## Configuration

The YAML stays intentionally simple.

Single-fabric mode uses:

- `groups`: optional repeated scopes such as `pod`
- `layers`: ordered tiers and per-node port capacity
- `links`: explicit connectivity between adjacent layers

Example:

```yaml
groups:
  - name: pod
    count: 2

layers:
  - name: compute
    placement: pod
    nodes_per_group: 32
    port_layout:
      base_lane_bandwidth_gb: 400
      total_lane_units: 8
      supported_port_modes:
        - port_bandwidth_gb: 400
          lane_units: 1

  - name: leaf
    placement: pod
    nodes_per_group: 8
    port_layout:
      base_lane_bandwidth_gb: 400
      total_lane_units: 128
      supported_port_modes:
        - port_bandwidth_gb: 400
          lane_units: 1
        - port_bandwidth_gb: 800
          lane_units: 2

links:
  - from: compute
    to: leaf
    policy: within_group_full_mesh
    cables_per_pair: 1
    cable_bandwidth_gb: 400
```

For the full config reference, validation rules, and examples:

- [Configuration Reference](docs/configuration.md)
- [Worked Examples](docs/examples.md)

Multi-fabric mode shares a single `gpu_nodes` layer across several isolated fabrics.
Shared endpoint partitions live in one top-level `groupings` section, and each
fabric selects which grouping it operates in:

```yaml
groupings:
  - name: pod
    members_per_group: 2
  - name: rack
    members_per_group: 1

gpu_nodes:
  total_nodes: 2
  fabric_port_layouts:
    backend:
      base_lane_bandwidth_gb: 100
      total_lane_units: 1
      supported_port_modes:
        - port_bandwidth_gb: 100
          lane_units: 1
    frontend:
      base_lane_bandwidth_gb: 50
      total_lane_units: 1
      supported_port_modes:
        - port_bandwidth_gb: 50
          lane_units: 1

fabrics:
  - name: backend
    grouping: pod
    layers:
      - name: leaf
        placement: group
        nodes_per_group: 1
        port_layout: ...
    links:
      - from: gpu_nodes
        to: leaf
        policy: within_group_full_mesh
        cables_per_pair: 1
        cable_bandwidth_gb: 100

  - name: frontend
    grouping: pod
    layers:
      - name: tor
        placement: group
        nodes_per_group: 1
        port_layout: ...
    links:
      - from: gpu_nodes
        to: tor
        policy: within_group_full_mesh
        cables_per_pair: 1
        cable_bandwidth_gb: 50

  - name: oob
    grouping: rack
    layers:
      - name: mgmt
        placement: global
        nodes_per_group: 1
        port_layout: ...
    links:
      - from: gpu_nodes
        to: mgmt
        policy: group_to_global_full_mesh
        cables_per_pair: 1
        cable_bandwidth_gb: 25
```

See [`configs/examples/multi_fabric_small.yaml`](configs/examples/multi_fabric_small.yaml) for a minimal complete example with `backend`, `frontend`, and `oob`.
See [`configs/examples/multi_fabric_backend_frontend.yaml`](configs/examples/multi_fabric_backend_frontend.yaml) for a larger two-fabric example built from the sixteen-pod three-tier backend plus a separate frontend fabric.
See [`configs/examples/multi_fabric_backend_frontend_oob.yaml`](configs/examples/multi_fabric_backend_frontend_oob.yaml) for the same large shared endpoint population plus a third `OOB` fabric that uses `rack = 8` grouping and 1G management links.

## Development

Helpful commands:

```bash
./.venv/bin/python -m pytest -q
./.venv/bin/python -m ruff check .
./.venv/bin/python -m mypy
python -m topology_generator.main --config configs/examples/three_tier_small.yaml --output-dir output/example
```

Developer-oriented detail lives in:

- [Architecture Overview](docs/architecture.md)
- [Configuration Reference](docs/configuration.md)
- [Worked Examples](docs/examples.md)
- [Agent Guide](AGENTS.md)

## License

MIT. See [LICENSE](LICENSE).
