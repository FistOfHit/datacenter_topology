from __future__ import annotations

from dataclasses import dataclass

from topology_generator.expander import ExpandedTopology


@dataclass(frozen=True)
class NodeUsage:
    required_lane_units: int = 0
    bandwidth_up_gb: float = 0.0
    bandwidth_down_gb: float = 0.0

    @property
    def total_bandwidth_gb(self) -> float:
        return self.bandwidth_up_gb + self.bandwidth_down_gb


class TopologyValidationError(ValueError):
    """Raised when expanded topology intent exceeds node capabilities."""

    def __init__(self, errors: list[str]):
        self.errors = tuple(sorted(set(errors)))
        super().__init__("\n".join(self.errors))


def build_node_usage(expanded_topology: ExpandedTopology) -> dict[str, NodeUsage]:
    usage = {node.node_id: NodeUsage() for node in expanded_topology.nodes}

    for link in expanded_topology.links:
        bundle_bandwidth = link.num_cables * link.cable_bandwidth_gb
        source_usage = usage[link.source_node_id]
        usage[link.source_node_id] = NodeUsage(
            required_lane_units=source_usage.required_lane_units
            + (link.num_cables * link.source_lane_units_per_cable),
            bandwidth_up_gb=source_usage.bandwidth_up_gb + bundle_bandwidth,
            bandwidth_down_gb=source_usage.bandwidth_down_gb,
        )

        target_usage = usage[link.target_node_id]
        usage[link.target_node_id] = NodeUsage(
            required_lane_units=target_usage.required_lane_units
            + (link.num_cables * link.target_lane_units_per_cable),
            bandwidth_up_gb=target_usage.bandwidth_up_gb,
            bandwidth_down_gb=target_usage.bandwidth_down_gb + bundle_bandwidth,
        )

    return usage


def validate_expanded_topology(expanded_topology: ExpandedTopology) -> dict[str, NodeUsage]:
    node_lookup = {node.node_id: node for node in expanded_topology.nodes}
    usage = build_node_usage(expanded_topology)
    errors: list[str] = []

    for link in expanded_topology.links:
        source_node = node_lookup[link.source_node_id]
        target_node = node_lookup[link.target_node_id]
        if source_node.lane_units_for_bandwidth(link.cable_bandwidth_gb) is None:
            errors.append(
                f"{source_node.node_id} does not support {link.cable_bandwidth_gb:g} GB/s cables"
            )
        if target_node.lane_units_for_bandwidth(link.cable_bandwidth_gb) is None:
            errors.append(
                f"{target_node.node_id} does not support {link.cable_bandwidth_gb:g} GB/s cables"
            )

    for node_id, node in node_lookup.items():
        required_lane_units = usage[node_id].required_lane_units
        if required_lane_units > node.total_lane_units:
            errors.append(
                f"{node_id} requires {required_lane_units} lane units but has "
                f"{node.total_lane_units}"
            )

    if errors:
        raise TopologyValidationError(errors)

    return usage
