# Configuration Reference

This document is the normative configuration contract for the project.

- Use this file for the exact supported schema and validation rules.
- Use [README.md](../README.md) for a quick-start overview.
- Use [examples.md](examples.md) for illustrative example configs and expected
  results.

Examples in this document are illustrative. They do not define alternate or
more permissive schema behavior.

## Shape

Single-fabric mode expects:

```yaml
groups:
  - ...
layers:
  - ...
links:
  - ...
```

Multi-fabric mode expects:

```yaml
groupings:
  - ...
gpu_nodes:
  total_nodes: ...
  fabric_port_pools:
    backend:
      - ...
fabrics:
  - ...
```

Single-fabric `layers:` and `links:` cannot be mixed with multi-fabric
`gpu_nodes:` and `fabrics:`.

Layer order defines the topology:

- layer `0` is the bottom layer
- layer `N-1` is the top layer
- only adjacent layers can be linked
- in multi-fabric mode, layer `0` is always `gpu_nodes`

## Groups And Groupings

`groups` is only used in single-fabric mode and supports zero or one repeated
group definition.

```yaml
groups:
  - name: pod
    count: 2
```

Rules:

- `name` is required, unique, and must remain unique after identifier normalization
- `name` must contain at least one alphanumeric character
- `global` is reserved and must not be used as a group name
- `count` is required and must be greater than zero

`groupings` is only used in multi-fabric mode. It defines reusable partitions
over the shared `gpu_nodes` population.

```yaml
groupings:
  - name: pod
    members_per_group: 64
  - name: rack
    members_per_group: 8
```

Rules:

- `name` is required, unique, and must remain unique after identifier normalization
- `name` must contain at least one alphanumeric character
- `global` and `gpu_nodes` are reserved names
- `members_per_group` is required and must be greater than zero
- every `members_per_group` value must divide `gpu_nodes.total_nodes` exactly
- grouping sizes must be unique
- grouping sizes must form a clean nesting chain by divisibility

## `gpu_nodes`

`gpu_nodes` is only used in multi-fabric mode. It defines the shared layer-0
endpoint population once and is the only place where layer-0 capacity is
configured.

```yaml
gpu_nodes:
  total_nodes: 1024
  fabric_port_pools:
    backend:
      - name: fabric
        base_lane_bandwidth_gb: 400
        total_lane_units: 8
        supported_port_modes:
          - port_bandwidth_gb: 400
            lane_units: 1
    frontend:
      - name: fabric
        base_lane_bandwidth_gb: 200
        total_lane_units: 2
        supported_port_modes:
          - port_bandwidth_gb: 200
            lane_units: 1
```

Rules:

- `gpu_nodes` is required in multi-fabric mode and forbidden in single-fabric mode
- `total_nodes` is required and must be greater than zero
- legacy `gpu_nodes.nodes_per_group` is not accepted
- `fabric_port_pools` must be a non-empty mapping from fabric name to a non-empty ordered list of port pools
- every `fabric_port_pools` key must match exactly one fabric name after normalization
- extra, missing, or misspelled fabric keys are rejected

## Layers

Every layer requires:

- `name`
- `placement`
- `nodes_per_group`
- `port_pools`

In multi-fabric mode, `layers:` live inside `fabrics[*]` and do not include
`gpu_nodes`. Fabrics declare `fabrics[*].gpu_nodes_placement`, and every
fabric-local layer uses a literal `placement` such as `rack`, `pod`, or
`global`.

```yaml
layers:
  - name: leaf
    placement: pod
    nodes_per_group: 8
    port_pools:
      - name: fabric
        base_lane_bandwidth_gb: 400
        total_lane_units: 128
        supported_port_modes:
          - port_bandwidth_gb: 400
            lane_units: 1
          - port_bandwidth_gb: 800
            lane_units: 2
      - name: mgmt
        base_lane_bandwidth_gb: 100
        total_lane_units: 4
        supported_port_modes:
          - port_bandwidth_gb: 100
            lane_units: 1
```

Rules:

- `name` must be unique and remain unique after identifier normalization
- `nodes_per_group` is the only node-count field
- for grouped placement, `nodes_per_group` means nodes in each group instance
- for `placement: global`, `nodes_per_group` means total nodes in that global layer
- legacy `ports_per_node`, `port_bandwidth_gb_per_port`, and `port_layout` are not accepted
- in single-fabric mode, `placement` must be either `global` or the declared group name
- in multi-fabric mode, `placement` must be either `global` or one declared grouping name
- in multi-fabric mode, no fabric-local layer may be named `gpu_nodes`
- in multi-fabric mode, placements must widen monotonically upward: same scope, ancestor scope, or `global`

### `port_pools`

`port_pools` is a non-empty ordered list of independent lane-based capacity
banks on the same node. Pool order is significant and is preserved for
rendering and for global numeric port numbering in the Excel export.

Each pool requires:

- `name`
- `base_lane_bandwidth_gb`
- `total_lane_units`
- `supported_port_modes`

Rules:

- pool `name` must be unique within a node and remain unique after identifier normalization
- `base_lane_bandwidth_gb` must be greater than zero
- `total_lane_units` must be an integer greater than zero
- `supported_port_modes` must not be empty
- each mode requires `port_bandwidth_gb` and `lane_units`
- `lane_units` must be an integer greater than zero and less than or equal to `total_lane_units`
- each mode must satisfy `port_bandwidth_gb == base_lane_bandwidth_gb * lane_units`
- `port_bandwidth_gb` values must be unique within a pool
- `lane_units` values must be unique within a pool
- fractional bandwidth values are supported; validation compares bandwidths robustly rather than relying on exact binary float equality

Interpretation:

- a `400G` mode with `lane_units: 1` consumes one lane unit per cable
- an `800G` mode with `lane_units: 2` consumes two contiguous lane units per cable
- two different pools on the same node do not share capacity or allocation state

## Links

Links are the sole source of connectivity truth.

```yaml
links:
  - from: leaf
    to: spine
    policy: to_global_full_mesh
    port_pool: fabric
    cables_per_pair: 1
    cable_bandwidth_gb: 800
```

Rules:

- `from` and `to` must reference existing layers
- each adjacent layer pair and `port_pool` combination may only appear once
- links are only allowed between adjacent layers in `layers` order
- `port_pool` is required
- `port_pool` must exist on both endpoint layers after identifier normalization
- `cables_per_pair` must be an integer greater than or equal to zero
- `cable_bandwidth_gb` must be:
  - greater than zero when `cables_per_pair > 0`
  - exactly zero when `cables_per_pair == 0`
- `cable_bandwidth_gb` must match a supported port mode in the named pool on both endpoint layers
- in multi-fabric mode, links are validated within each fabric's effective layer order `[gpu_nodes] + fabrics[*].layers`

### Supported policies

`same_scope_full_mesh`

- both layers must share the same non-global placement
- every node in a scope instance connects to every node in the next layer within the same scope instance

`to_ancestor_full_mesh`

- both layers must be non-global
- target placement must be a strict ancestor of the source placement
- every source node connects to every target node in its containing ancestor scope instance

`to_global_full_mesh`

- source layer must be grouped
- target layer must be global
- every grouped source node connects to every global target node

`global_full_mesh`

- both layers must be global
- every node in the lower layer connects to every node in the next global layer

## Validation Rules

Validation happens in two passes.

### Semantic validation

- group names must be unique in single-fabric mode
- grouping names must be unique in multi-fabric mode
- layer names must be unique within a fabric or single-fabric config
- fabric names must be unique
- normalized group, grouping, layer, fabric, and pool identifiers must remain unique in their scopes
- expanded node IDs implied by group, layer, and ordinal names must remain unique after normalization
- placements must reference `global`, the declared single-fabric group name, or one declared grouping name depending on the active config shape
- link policies must be compatible with endpoint placements
- links must connect adjacent layers only
- link pool names must exist on both endpoints
- link bandwidth must be supported by the named pool on both endpoints
- `gpu_nodes.fabric_port_pools` must match `fabrics[*].name`
- `gpu_nodes` may not be redefined inside `fabrics[*].layers`
- `fabrics[*].gpu_nodes_placement` must be `global` or reference a declared grouping

### Expanded topology validation

After the config is expanded into concrete nodes and concrete link bundles, the
tool checks:

- required lane units per node and per port pool
- supported cable bandwidth on each expanded endpoint within the named pool

Deterministic contiguous lane allocation happens later during graph
materialization, after expanded-topology validation succeeds.

All failures are reported together using the expanded node IDs.

Examples:

- `pod_2_leaf_7 port pool 'fabric' requires 40 lane units but has 36`
- `links[0].cable_bandwidth_gb 800 GB/s is not supported by layer 'compute' port pool 'mgmt'`
- `gpu_nodes.fabric_port_pools must match fabrics by name after normalization`

## Node Naming

Expanded node IDs are stable and literal to the YAML concepts:

- grouped nodes: `<group_name>_<group_index>_<layer_name>_<ordinal>`
- global nodes: `<layer_name>_<ordinal>`
- multi-fabric shared endpoints use grouping-neutral physical IDs such as `gpu_nodes_17`
- multi-fabric internal upper-layer nodes are fabric-qualified to avoid collisions
- multi-fabric grouped labels are resolved from the selected placement path, such as `backend__pod_1_leaf_3` or `oob__pod_1_rack_2_mgmt_1`

These IDs appear in the graph metadata, log messages, and Excel output.

## `fabrics`

`fabrics` is only used in multi-fabric mode. Each fabric defines a self-contained
topology above `gpu_nodes`.

```yaml
fabrics:
  - name: backend
    gpu_nodes_placement: pod
    layers:
      - name: leaf
        placement: pod
        nodes_per_group: 8
        port_pools:
          - ...
    links:
      - from: gpu_nodes
        to: leaf
        policy: same_scope_full_mesh
        port_pool: fabric
        cables_per_pair: 1
        cable_bandwidth_gb: 400
```

Rules:

- `name` is required and must be unique after normalization
- `gpu_nodes_placement` is required and must be either `global` or one declared `groupings[*].name`
- `layers` must contain at least one fabric-local layer
- `links` uses the same schema as single-fabric mode
- every fabric uses the full `gpu_nodes` population in v1
- only `gpu_nodes` is shared across fabrics in v1
