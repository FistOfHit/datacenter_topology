# Configuration Reference

## Shape

The tool expects a YAML mapping with a single ordered `layers` list:

```yaml
layers:
  - ...
  - ...
```

List order defines the topology:

- layer `0` is the bottom layer
- layer `N-1` is the top layer
- only adjacent layers can be connected

## Layer Fields

Every layer requires:

- `node_count_in_layer`
- `ports_per_node`
- `port_bandwidth_gb_per_port`

Optional:

- `name`

Upward connectivity fields:

- `uplink_cables_per_node_to_each_node_in_next_layer`
- `uplink_cable_bandwidth_gb`

Downward connectivity fields:

- `downlink_cables_per_node_to_each_node_in_previous_layer`
- `downlink_cable_bandwidth_gb`

Boundary rules:

- layer `0` may omit `downlink_*`
- layer `N-1` may omit `uplink_*`
- omitted boundary-direction fields default to zero

## Example

```yaml
layers:
  - name: compute
    node_count_in_layer: 4
    ports_per_node: 2
    port_bandwidth_gb_per_port: 10
    uplink_cables_per_node_to_each_node_in_next_layer: 1
    uplink_cable_bandwidth_gb: 10

  - name: aggregation
    node_count_in_layer: 2
    ports_per_node: 4
    port_bandwidth_gb_per_port: 10
    downlink_cables_per_node_to_each_node_in_previous_layer: 1
    downlink_cable_bandwidth_gb: 10
```

## Validation Rules

- `layers` must be a list with at least 2 entries.
- Every layer must have `node_count_in_layer > 0`.
- `ports_per_node` must be numeric and non-negative.
- `port_bandwidth_gb_per_port` must be numeric and greater than zero.
- `name`, when provided, must be a non-empty string.
- If `uplink_cables_per_node_to_each_node_in_next_layer > 0`, then `uplink_cable_bandwidth_gb` must be greater than zero.
- If `downlink_cables_per_node_to_each_node_in_previous_layer > 0`, then `downlink_cable_bandwidth_gb` must be greater than zero.
- If a link count is zero, its bandwidth must also be zero.
- Adjacent layers must agree exactly on shared connectivity:
  - lower layer `uplink_cables_per_node_to_each_node_in_next_layer ==` upper layer `downlink_cables_per_node_to_each_node_in_previous_layer`
  - lower layer `uplink_cable_bandwidth_gb ==` upper layer `downlink_cable_bandwidth_gb`
- Each cable bandwidth must fit within the port bandwidth of both adjacent layers.
- Each layer must have enough physical ports to satisfy the generator's dense adjacent-layer cabling pattern.

## Behavioral Notes

- Layer names are labels only; topology semantics come from list order.
- If `name` is omitted, it defaults to `layer_<index>`.
- The generator attempts full adjacency between neighboring layers using the configured per-pair cable count.
- Aggregate bandwidth is derived from layer sizes and link settings rather than configured directly.
