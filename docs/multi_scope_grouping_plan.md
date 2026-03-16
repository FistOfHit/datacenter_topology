# Multi-Scope Grouping Plan

This document captures the original planning work for a feature that is now
shipped. The authoritative current behavior lives in
[configuration.md](configuration.md) and [architecture.md](architecture.md).

The final shipped public names differ from parts of the original proposal:

- `gpu_nodes_placement` shipped instead of `shared_endpoint_placement`
- `same_scope_full_mesh`, `to_ancestor_full_mesh`, `to_global_full_mesh`, and
  `global_full_mesh` shipped instead of the earlier policy names

- Treat the remainder of this file as historical planning context rather than
  the normative config contract.

## Summary

Implement multi-fabric grouping by layer scope instead of one grouping per fabric. A fabric may mix scopes across adjacent layers as long as scope only widens upward through the declared nesting chain. This enables cases like OOB `gpu_nodes(rack) -> leaf(rack) -> spine(pod) -> core(global)` while preserving the current CLI, output filenames, lane-based validation, and per-fabric isolation.

The canonical acceptance scenario is the large OOB fabric:

- `shared_endpoint_placement: rack`
- `leaf` uses `placement: rack`
- `spine` uses `placement: pod`
- `core` uses `placement: global`
- `gpu_nodes -> leaf` stays `within_group_full_mesh`
- `leaf -> spine` uses a new ancestor-group full mesh policy
- `spine -> core` stays `group_to_global_full_mesh`

## Public Interfaces

- Change the multi-fabric YAML shape:
  - Remove `fabrics[*].grouping`.
  - Add `fabrics[*].shared_endpoint_placement`, required, allowed values: `global` or any declared `groupings[*].name`.
  - In multi-fabric mode, `fabrics[*].layers[*].placement` must be `global` or a literal grouping name such as `rack` or `pod`.
  - Reject legacy `placement: group`.
- Add a new link policy: `group_to_ancestor_group_full_mesh`.
  - Valid only when both endpoints are non-global and the upper layer's placement is an ancestor of the lower layer's placement.
  - Expansion semantics: each lower-scope node connects to every upper-layer node within the containing ancestor group only.
- Preserve current output contracts:
  - single-fabric outputs unchanged
  - multi-fabric still emits `topology_<fabric>.png`, `port_mapping.xlsx`, `network_topology.log`
- Keep the Excel schema unchanged.
  - `source_group` and `target_group` remain single columns and store the node's own resolved placement label, e.g. rack leaf `pod_1_rack_3`, pod spine `pod_1`.

## Implementation Changes

- Update config parsing and semantic validation in the config modules (`config_parser.py`, `config_validation.py`, `config_types.py`):
  - Parse `shared_endpoint_placement`.
  - Validate that every multi-fabric layer placement is `global` or a declared grouping name.
  - Enforce monotonic wider-only scope as layer index increases: same scope, ancestor scope, or `global`; narrowing is invalid.
  - Validate new link policy compatibility against the grouping chain.
  - Keep single-fabric behavior unchanged.
  - Update docs/examples to the new schema and remove old multi-fabric examples that rely on `grouping` / `placement: group`.
- Refactor expansion and graph metadata in `topology_generator/expander.py` and `topology_generator/topology_generator.py`:
  - Expand each layer against its own placement scope rather than a fabric-wide group index.
  - Keep shared GPU physical graph node IDs grouping-neutral as today.
  - Preserve fabric-qualified expanded node IDs for validation of shared GPUs.
  - Replace the single-group internal model with scope-aware metadata:
    - `placement_scope`: the node's own scope or `None` for global
    - `scope_labels`: ordered mapping of every visible ancestor scope to resolved labels
    - `scope_indexes`: ordered mapping of every ancestor scope to 1-based indexes
    - keep `group_label` as the node's own resolved placement label for downstream compatibility
    - keep `group_index` as the node's own 1-based index within its own placement scope
  - Node IDs for grouped fabric-local layers should continue using resolved full labels, e.g. `pod_1_rack_3_leaf_1`, `pod_1_spine_2`, `core_1`.
- Update port mapping and sorting in `topology_generator/port_mapper.py`:
  - Keep row orientation and columns unchanged.
  - Sort grouped nodes by full ancestry path, then node ordinal, so racks sort within pods correctly.
  - Continue using `group_label` for `source_group` / `target_group`.
- Generalize rendering in the render modules (`rendering.py`, `render_layout.py`, `render_drawing.py`):
  - Replace the single-level group layout with a recursive visible container tree over the grouping chain.
  - At each grouping level, render only first and last visible groups inside the current visible parent container; insert `...` placeholder lanes for hidden siblings.
  - Draw nested dashed bounding boxes with resolved labels for every visible scope instance.
  - Place nodes inside the box for their own scope: rack nodes in rack boxes, pod nodes centered in pod boxes, globals centered overall.
  - Preserve current node condensation inside each visible scope: first and last node only with `...` placeholder when needed.
  - Preserve overall layer bandwidth arrows.
  - Generalize grouped bandwidth arrows to the narrowest grouped scope shared by both adjacent layers:
    - same-scope links draw per that scope
    - child-to-ancestor links draw per ancestor scope
    - grouped-to-global links keep only the overall layer arrow
  - Keep fanout labels and edge counts based on real graph totals, including hidden edges.
- Update docs and examples:
  - `docs/configuration.md`, `docs/architecture.md`, `docs/examples.md`, and the shipped multi-fabric example YAMLs.
  - Show the new OOB example explicitly with rack leafs, pod spines, and global core.

## Test Plan

- Config/schema tests:
  - accept explicit per-layer placements and `shared_endpoint_placement`
  - reject `placement: group`
  - reject removed `fabrics[*].grouping`
  - reject narrowing transitions such as `pod -> rack`
  - accept `rack -> pod -> global`
  - reject `group_to_ancestor_group_full_mesh` when upper scope is not an ancestor
- Expansion/generation tests:
  - OOB example expands rack-scoped GPUs and leafs, pod-scoped spines, global core
  - rack leaf links only to GPUs in its rack
  - pod spine links to all rack leafs in its containing pod, never cross-pod
  - shared GPU validation remains fabric-isolated
  - contiguous lane allocation and cut-sheet row counts remain deterministic
- Renderer tests:
  - nested pod and rack boxes are produced
  - only first/last pods are visible when many pods exist
  - within visible pods, only first/last racks are visible when many racks exist
  - placeholder labels appear at both hidden pod and hidden rack levels
  - pod-scoped nodes are centered within pod boxes, not rack boxes
  - grouped bandwidth arrows stay inside the correct visible container
- Integration/smoke:
  - full CLI run on updated multi-fabric examples
  - output filenames unchanged
  - merged Excel still contains one `fabric` column and correct row counts

## Assumptions and Defaults

- This is an intentional breaking change for multi-fabric config syntax; docs, examples, and tests all migrate in the same change.
- Single-fabric topology behavior is unchanged.
- The grouping chain remains a clean divisibility-based nesting hierarchy and the new behavior supports arbitrary nesting depth, not just pod/rack.
- The cut-sheet keeps one group label column per endpoint and does not add per-scope columns.
