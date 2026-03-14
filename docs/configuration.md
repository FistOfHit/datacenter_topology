# Configuration Reference

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
  fabric_port_layouts:
    backend: ...
fabrics:
  - ...
```

Single-fabric `layers:` and `links:` cannot be mixed with multi-fabric `gpu_nodes:` and `fabrics:`.

Layer order defines the topology:

- layer `0` is the bottom layer
- layer `N-1` is the top layer
- only adjacent layers can be linked
- in multi-fabric mode, layer `0` is always `gpu_nodes`

## Groupings

`groupings` is only used in multi-fabric mode. It defines reusable partitions over the
shared `gpu_nodes` population in one place so each fabric can choose which grouping it
uses.

Example:

```yaml
groupings:
  - name: pod
    members_per_group: 64
  - name: rack
    members_per_group: 8
```

Rules:

- `name` is required, unique, and must remain unique after identifier normalization.
- `name` must contain at least one alphanumeric character.
- `global`, `group`, and `gpu_nodes` are reserved names and must not be used.
- `members_per_group` is required and must be greater than zero.
- every `members_per_group` value must divide `gpu_nodes.total_nodes` exactly.
- grouping sizes must form a clean nesting chain by divisibility.
- grouping sizes must be unique.

## Groups

Groups describe repeated scopes such as `pod` or `SU`.

Example:

```yaml
groups:
  - name: pod
    count: 2
```

Rules:

- v1 supports zero or one repeated group definition.
- `name` is required, unique, and must remain unique after identifier normalization.
- `name` must contain at least one alphanumeric character.
- `global` is reserved for placement semantics and must not be used as a group name.
- `count` is required and must be greater than zero.
- `count` is always explicit.

If `groups` is empty, all layers must use `placement: global`.

## `gpu_nodes`

`gpu_nodes` is only used in multi-fabric mode. It defines the shared layer-0 endpoint population once and is the only place where layer-0 capacity is configured.

Example:

```yaml
gpu_nodes:
  total_nodes: 1024
  fabric_port_layouts:
    backend:
      base_lane_bandwidth_gb: 400
      total_lane_units: 8
      supported_port_modes:
        - port_bandwidth_gb: 400
          lane_units: 1
    frontend:
      base_lane_bandwidth_gb: 200
      total_lane_units: 2
      supported_port_modes:
        - port_bandwidth_gb: 200
          lane_units: 1
```

Rules:

- `gpu_nodes` is required in multi-fabric mode and forbidden in single-fabric mode.
- `total_nodes` is required and must be greater than zero.
- `fabric_port_layouts` must be a non-empty mapping from fabric name to a valid port layout
- every `fabric_port_layouts` key must match exactly one fabric name after normalization
- extra, missing, or misspelled fabric keys are rejected

Each `fabric_port_layouts.<fabric>` value uses the same schema and rules as `port_layout`.

## Layers

Every layer requires:

- `name`
- `placement`
- `nodes_per_group`
- `port_layout`

In multi-fabric mode, `layers:` live inside `fabrics[*]` and do not include `gpu_nodes`.
Fabrics choose one grouping namespace with `fabrics[*].grouping`, and grouped fabric-local
layers use `placement: group`.

Example:

```yaml
layers:
  - name: leaf
    placement: group
    nodes_per_group: 8
    port_layout:
      base_lane_bandwidth_gb: 400
      total_lane_units: 128
      supported_port_modes:
        - port_bandwidth_gb: 400
          lane_units: 1
        - port_bandwidth_gb: 800
          lane_units: 2
```

Rules:

- `name` must be unique and remain unique after identifier normalization.
- `nodes_per_group` is the only node-count field.
- For grouped placement, `nodes_per_group` means nodes in each group instance.
- For `placement: global`, `nodes_per_group` means total nodes in that global layer.
- legacy `ports_per_node` and `port_bandwidth_gb_per_port` are no longer accepted.
- in single-fabric mode, `placement` must be either `global` or the declared group name.
- in multi-fabric mode, `placement` must be either `global` or `group`
- in multi-fabric mode, no fabric-local layer may be named `gpu_nodes`

### `port_layout`

`port_layout` models hardware capacity in base lane units and allowed logical port modes.

Fields:

- `base_lane_bandwidth_gb`: bandwidth of one lane unit
- `total_lane_units`: total lane units available on each node in the layer
- `supported_port_modes`: list of valid logical port modes for the node

Each supported port mode requires:

- `port_bandwidth_gb`
- `lane_units`

Rules:

- `base_lane_bandwidth_gb` must be greater than zero.
- `total_lane_units` must be an integer greater than zero.
- `supported_port_modes` must not be empty.
- `lane_units` must be an integer greater than zero and less than or equal to `total_lane_units`.
- each mode must satisfy `port_bandwidth_gb == base_lane_bandwidth_gb * lane_units`
- `port_bandwidth_gb` values must be unique within a layer
- `lane_units` values must be unique within a layer
- fractional bandwidth values are supported; validation compares bandwidths robustly rather than relying on exact binary float equality

Interpretation:

- a `400G` mode with `lane_units: 1` consumes one lane unit per cable
- an `800G` mode with `lane_units: 2` consumes two contiguous lane units per cable
- mixed `400G` and `800G` links are allowed on the same node as long as the sum of consumed lane units fits within `total_lane_units`

## Links

Links are the sole source of connectivity truth.

Example:

```yaml
links:
  - from: leaf
    to: spine
    policy: group_to_global_full_mesh
    cables_per_pair: 1
    cable_bandwidth_gb: 800
```

Rules:

- `from` and `to` must reference existing layers.
- each adjacent layer pair may only appear once
- links are only allowed between adjacent layers in `layers` order
- `cables_per_pair` must be an integer greater than or equal to zero
- `cable_bandwidth_gb` must be:
  - greater than zero when `cables_per_pair > 0`
  - exactly zero when `cables_per_pair == 0`
- `cable_bandwidth_gb` must match a supported port mode on both endpoint layers
- in multi-fabric mode, links are validated within each fabric's effective layer order `[gpu_nodes] + fabrics[*].layers`

### Supported policies

`within_group_full_mesh`

- both layers must share the same non-global placement
- every node in a group instance connects to every node in the next layer within the same group instance

`group_to_global_full_mesh`

- source layer must be grouped
- target layer must be global
- every grouped source node connects to every global target node

`global_to_global_full_mesh`

- both layers must be global
- every node in the lower layer connects to every node in the next global layer

## Validation Rules

Validation happens in two passes.

### Semantic validation

- group names must be unique in single-fabric mode
- grouping names must be unique in multi-fabric mode
- layer names must be unique within a fabric or single-fabric config
- fabric names must be unique
- normalized group, grouping, layer, and fabric identifiers must remain unique in their scopes
- expanded node IDs implied by group, layer, and ordinal names must remain unique after normalization
- placements must reference `global`, the declared single-fabric group name, or `group` depending on the active config shape
- link policies must be compatible with endpoint placements
- links must connect adjacent layers only
- link bandwidth must be supported by both endpoint layers
- `gpu_nodes.fabric_port_layouts` must match `fabrics[*].name`
- `gpu_nodes` may not be redefined inside `fabrics[*].layers`
- `fabrics[*].grouping` must reference a declared grouping

### Expanded topology validation

After the config is expanded into concrete nodes and concrete link bundles, the tool checks:

- required lane units per node
- deterministic contiguous lane allocation for every cable

All failures are reported together using the expanded node IDs.

Examples:

- `pod_2_leaf_7 requires 40 lane units but has 36`
- `links[0].cable_bandwidth_gb 800 GB/s is not supported by layer 'compute'`
- `gpu_nodes.fabric_port_layouts must match fabrics by name after normalization`

## Node Naming

Expanded node IDs are stable and literal to the YAML concepts:

- grouped nodes: `<group_name>_<group_index>_<layer_name>_<ordinal>`
- global nodes: `<layer_name>_<ordinal>`
- multi-fabric shared endpoints use grouping-neutral physical IDs such as `gpu_nodes_17`
- multi-fabric internal upper-layer nodes are fabric-qualified to avoid collisions
- multi-fabric grouped labels are resolved from the selected grouping, such as
  `backend__pod_1_leaf_3` or `oob__pod_1_rack_2_mgmt_1`

The names are normalized to lowercase identifier form internally for node IDs, but the original YAML layer names are preserved for display in the diagram.

Because node IDs are derived mechanically, some otherwise-distinct YAML names can still collide after expansion. For example, a grouped layer named `compute` inside `pod_1` conflicts with a global layer named `pod_1_compute`. These collisions are rejected during config validation.

Examples:

- `pod_1_compute_17`
- `pod_2_leaf_switch_3`
- `spine_8`
- `backend__pod_1_leaf_3`

These IDs appear in the graph metadata, log messages, and Excel output.

## `fabrics`

`fabrics` is only used in multi-fabric mode. Each fabric defines a self-contained topology above `gpu_nodes`.

Example:

```yaml
fabrics:
  - name: backend
    grouping: pod
    layers:
      - name: leaf
        placement: group
        nodes_per_group: 8
        port_layout: ...
    links:
      - from: gpu_nodes
        to: leaf
        policy: within_group_full_mesh
        cables_per_pair: 1
        cable_bandwidth_gb: 400
```

Rules:

- `name` is required and must be unique after normalization
- `grouping` is required for canonical multi-fabric configs and must reference one declared `groupings[*].name`
- `layers` must contain at least one fabric-local layer
- `links` uses the same schema as single-fabric mode
- every fabric uses the full `gpu_nodes` population in v1
- only `gpu_nodes` is shared across fabrics in v1

Compatibility:

- the parser still accepts the previous multi-fabric shape using top-level `groups`,
  `gpu_nodes.nodes_per_group`, and fabric-local placements like `pod`
- legacy multi-fabric configs are normalized internally to the canonical `groupings`
  representation for one compatibility cycle
- legacy multi-fabric configs that used only global placements do not need `fabrics[*].grouping`
