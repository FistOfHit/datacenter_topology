# Architecture Overview

This document describes the current system structure and the stable design
choices behind the topology generation pipeline.

## Execution Flow

The application runs as one CLI pipeline:

1. Parse CLI arguments in `argparser.py`.
2. Resolve the final output directory path in `file_handler.py`.
3. Create the output directory and configure logging in `logger.py`.
4. Load YAML and validate it into `TopologyConfig`.
5. Expand grouped intent into concrete nodes and concrete link bundles.
6. Validate the expanded topology against lane-unit capacity and supported port
   modes.
7. Build a `networkx.Graph` with node metadata and coalesced per-pair link bundles.
8. Render `topology.png` or per-fabric `topology_<fabric>.png`.
9. Flatten graph edge bundles into `port_mapping.xlsx`.

Important execution details:

- `parse_args()` is pure and only parses arguments.
- Output directory resolution happens before logging, but directory creation
  happens when logging/output writers need it.
- The CLI contract and output filenames are intentionally stable.

## Core Modules

### Config pipeline

The config pipeline is split across:

- `config_identifiers.py`
- `config_types.py`
- `config_parser.py`
- `config_validation.py`

Together these modules define the immutable configuration model, parse YAML
input, normalize identifiers, and enforce semantic validation.

Key guarantees:

- single-fabric and multi-fabric config shapes are mutually exclusive
- layer, group, grouping, and fabric names stay unique after normalization
- port-pool names stay unique within each node-capable config object
- links are limited to adjacent layers in declared order
- link policies must match endpoint placement semantics
- lane-based port math must be valid in every named port pool
- `gpu_nodes` is the only shared layer in multi-fabric mode
- multi-fabric layers carry explicit literal scope placements such as `rack`,
  `pod`, or `global`

### `expander.py`

Expansion converts validated grouped config into concrete topology intent:

- concrete nodes
- concrete full-mesh link bundles
- ancestry-aware scope metadata for grouped layers
- per-end lane consumption for each cable bandwidth in the named port pool

Expansion is intentionally graph-free. It produces a deterministic intermediate
representation that later stages can validate and materialize.

### `validator.py`

Validation runs on the expanded topology, not the raw YAML shape.

It checks:

- per-node, per-pool lane-unit demand
- per-node aggregate up/down bandwidth
- supported cable bandwidth on each endpoint in the named pool
- per-pool lane demand against hardware capacity

In multi-fabric mode, validation remains fabric-local even for shared
`gpu_nodes`.

### `topology_generator.py`

This module turns expanded, validated intent into the final graph.

It is responsible for:

- expansion and expanded-topology validation orchestration
- graph node creation
- graph edge creation
- deterministic contiguous lane allocation per cable within each `(node, pool)`
- storing usage metadata, per-pool metadata, scope-path metadata, and allocation metadata
- merging multi-fabric runs into one graph while preserving per-fabric views

### Render pipeline

Rendering is split across:

- `render_environment.py`
- `render_formatting.py`
- `render_types.py`
- `render_layout.py`
- `render_drawing.py`
- `rendering.py`

The render pipeline keeps layout computation, drawing primitives, environment
setup, and formatting logic separate.

Stable rendering behavior:

- large grouped layers are rendered in condensed form
- only the first and last visible groups/nodes are shown when counts are large
- nested scope boxes are shown for multi-scope fabrics
- global layers are kept visually separate from grouped layers
- aggregate bandwidth and fanout annotations come from graph metadata
- multi-fabric runs are rendered through isolated per-fabric graph views

### `graph_metadata.py`

This module centralizes typed access to graph, node, and edge metadata used by
rendering and export code.

Its role is to reduce scattered string-key dict handling and provide a clearer
internal contract around graph attributes.

### `port_mapper.py`

This module converts graph edge bundles into the Excel cut-sheet.

Stable export behavior:

- one row per physical cable
- lower-layer to upper-layer orientation
- explicit source and target group columns
- per-end globally unique base-lane start indices and lane widths
- merged multi-fabric workbook with a `fabric` column

## Design Choices

### Expand first, validate concrete intent, then build the graph

The code validates the topology against the concrete node/link set that will
actually be built, rather than validating only the abstract YAML shape. This
keeps grouped and multi-fabric behavior easier to reason about and test.

### Links exist only between adjacent layers

The ordered `layers` list defines topology order. Links are modeled only
between neighboring layers, and the link policy defines the full adjacency
pattern between those two layers.

### Multi-fabric mode shares only `gpu_nodes`

Multi-fabric mode uses one shared layer-0 endpoint population, exposed in YAML
as `gpu_nodes`. Each fabric declares a `gpu_nodes_placement` and then assigns
literal placements to each fabric-local layer, allowing one fabric to treat the
shared endpoints as `pod` scoped while another treats them as `rack` scoped.

### Shared endpoints remain physically shared but logically fabric-local

During expansion and validation, shared GPU nodes are duplicated per fabric so
capacity checks remain isolated. During graph materialization, those fabrics map
back onto shared physical graph node IDs so downstream consumers can still view
one combined topology.

### Scope widening is explicit

Multi-fabric placements must widen monotonically as layers move upward.
Adjacent layers may stay in the same scope, move to an ancestor scope, or move
to `global`, but may not narrow. Link policies mirror that model through
`same_scope_full_mesh`, `to_ancestor_full_mesh`, `to_global_full_mesh`, and
`global_full_mesh`.

### Port pools isolate hardware budgets

Port hardware is modeled in named base-lane pools instead of a single fixed
“ports per node” budget. That allows mixed-speed port modes within one pool
while keeping unrelated hardware banks on the same device isolated for
validation and allocation.

### The renderer is a planning view, not a physical layout

The rendered diagram is intentionally condensed and annotation-heavy. It is
designed to communicate topology shape, bandwidth, and cable fanout without
trying to draw every node literally at large scales.
