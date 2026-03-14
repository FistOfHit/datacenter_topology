# Architecture Overview

## Execution Flow

The application remains a single CLI pipeline:

1. Parse arguments.
2. Create the output directory and configure logging.
3. Load and validate YAML into `TopologyConfig`.
4. Normalize either single-fabric config or multi-fabric shared-endpoint config into effective per-fabric topologies.
5. Expand grouped layers into concrete nodes and concrete link bundles.
6. Validate the expanded topology per node.
7. Build a `networkx.Graph`.
8. Render `topology.png` or per-fabric `topology_<fabric>.png`.
9. Flatten graph edges into `port_mapping.xlsx`.

## Core Modules

### `config_schema.py`

Defines the grouped config model.

- `GroupConfig`
- `GroupingConfig`
- `PortModeConfig`
- `PortLayoutConfig`
- `LayerConfig`
- `LinkConfig`
- `FabricConfig`
- `GpuNodesConfig`
- `TopologyConfig`

Semantic validation enforces:

- one repeated group at most
- unique literal and normalized group, grouping, layer, and fabric names
- valid placements
- adjacent-layer-only links
- policy/placement compatibility
- valid lane-based port layouts
- link bandwidth support against endpoint port modes
- exact correspondence between `gpu_nodes.fabric_port_layouts` and `fabrics`
- a clean nesting chain across `groupings`
- `gpu_nodes` as the only shared layer in multi-fabric mode

### `expander.py`

Turns the validated grouped config into concrete intent:

- expands group instances
- expands concrete nodes
- expands concrete link bundles
- resolves the selected grouping for each fabric
- duplicates shared `gpu_nodes` intent per fabric for validation while retaining a shared physical graph node ID
- resolves per-end lane consumption for each cable bandwidth

This module does not mutate a graph. It is a pure expansion stage that makes later validation and testing straightforward.

### `validator.py`

Validates the expanded topology:

- computes required lane units per node
- computes per-node up/down bandwidth usage
- verifies that each node supports the requested cable bandwidth
- checks that aggregate lane consumption fits the hardware budget

For multi-fabric runs, validation remains fabric-local even on shared `gpu_nodes`.

All validation is performed against the expanded node IDs that will appear in the graph and cut-sheet.

### `topology_generator.py`

Orchestrates grouped topology generation:

- validates the config
- expands it
- validates expanded intent
- creates graph nodes and graph edges
- assigns deterministic contiguous base-lane spans per cable
- stores lane-based usage metadata on nodes and edges
- keeps one giant graph for all fabrics while storing per-fabric grouping-aware metrics on shared `gpu_nodes`
- exposes helpers to derive a flattened per-fabric graph view for downstream consumers

### `visualiser.py`

Responsible for grouped condensed rendering.

- renders first and last visible groups when many groups exist
- renders first and last visible nodes inside a rendered group/layer when many nodes exist
- keeps global layers separate from grouped local layers
- draws aggregate bandwidth indicators and fanout annotations from the actual graph
- shows lane consumption per node rather than a single-speed port-equivalent metric
- renders each multi-fabric graph through an isolated per-fabric view

### `port_mapper.py`

Responsible for the Excel cut-sheet data.

- converts graph edges into one row per cable
- includes explicit source and target group columns
- includes per-end base-lane start indices and lane widths
- normalizes source/target orientation to lower layer -> higher layer
- merges per-fabric tables into one workbook in multi-fabric mode and adds a `fabric` column
- writes `port_mapping.xlsx`

## Design Notes

- The grouped model is explicit. There is no hidden derivation of pod counts or placement scopes.
- Multi-fabric mode always shares only layer 0, exposed in YAML as `gpu_nodes`.
- Multi-fabric group membership is defined centrally in `groupings`; each fabric selects one grouping namespace and uses `placement: group` for grouping-relative layers.
- Links remain adjacent-layer only within each fabric's effective layer order.
- Validation is performed after expansion so grouped fabrics and shared `gpu_nodes` are checked against the actual intended link set.
- Shared endpoint graph node IDs stay grouping-neutral so multiple fabrics can view the same physical endpoints through different groupings without collisions.
- Port hardware is modeled in lane units so a single switch can expose multiple logical port speeds, such as `128 x 400G` or `64 x 800G`, without duplicating the layer.
- The renderer is deliberately condensed; it is a planning view rather than a physical layout drawing.
