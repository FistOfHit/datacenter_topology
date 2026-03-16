from __future__ import annotations

from dataclasses import dataclass, field

from topology_generator.config_identifiers import normalize_identifier
from topology_generator.expander import ExpandedTopology


@dataclass(frozen=True)
class NodeUsage:
    required_lane_units_by_pool: dict[str, int] = field(default_factory=dict)
    bandwidth_up_gb: float = 0.0
    bandwidth_down_gb: float = 0.0

    @property
    def required_lane_units(self) -> int:
        return sum(self.required_lane_units_by_pool.values())

    @property
    def total_bandwidth_gb(self) -> float:
        return self.bandwidth_up_gb + self.bandwidth_down_gb

    def required_lane_units_for_pool(self, pool_name: str) -> int:
        return self.required_lane_units_by_pool.get(normalize_identifier(pool_name), 0)


class TopologyValidationError(ValueError):
    """Raised when expanded topology intent exceeds node capabilities."""

    def __init__(self, errors: list[str]):
        self.errors = tuple(sorted(set(errors)))
        super().__init__("\n".join(self.errors))


def build_node_usage(expanded_topology: ExpandedTopology) -> dict[str, NodeUsage]:
    usage = {node.node_id: NodeUsage() for node in expanded_topology.nodes}

    for link in expanded_topology.links:
        bundle_bandwidth = link.num_cables * link.cable_bandwidth_gb
        normalized_pool_name = normalize_identifier(link.port_pool)

        source_usage = usage[link.source_node_id]
        source_pool_usage = dict(source_usage.required_lane_units_by_pool)
        source_pool_usage[normalized_pool_name] = source_pool_usage.get(normalized_pool_name, 0) + (
            link.num_cables * link.source_lane_units_per_cable
        )
        usage[link.source_node_id] = NodeUsage(
            required_lane_units_by_pool=source_pool_usage,
            bandwidth_up_gb=source_usage.bandwidth_up_gb + bundle_bandwidth,
            bandwidth_down_gb=source_usage.bandwidth_down_gb,
        )

        target_usage = usage[link.target_node_id]
        target_pool_usage = dict(target_usage.required_lane_units_by_pool)
        target_pool_usage[normalized_pool_name] = target_pool_usage.get(normalized_pool_name, 0) + (
            link.num_cables * link.target_lane_units_per_cable
        )
        usage[link.target_node_id] = NodeUsage(
            required_lane_units_by_pool=target_pool_usage,
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
        if (
            source_node.lane_units_for_pool_bandwidth(link.port_pool, link.cable_bandwidth_gb)
            is None
        ):
            errors.append(
                f"{source_node.node_id} does not support {link.cable_bandwidth_gb:g} GB/s cables "
                f"in port pool {link.port_pool!r}"
            )
        if (
            target_node.lane_units_for_pool_bandwidth(link.port_pool, link.cable_bandwidth_gb)
            is None
        ):
            errors.append(
                f"{target_node.node_id} does not support {link.cable_bandwidth_gb:g} GB/s cables "
                f"in port pool {link.port_pool!r}"
            )

    for node_id, node in node_lookup.items():
        node_usage = usage[node_id]
        for port_pool in node.port_pools:
            required_lane_units = node_usage.required_lane_units_for_pool(port_pool.name)
            if required_lane_units <= port_pool.total_lane_units:
                continue
            errors.append(
                f"{node_id} port pool {port_pool.name!r} requires {required_lane_units} "
                f"lane units but has {port_pool.total_lane_units}"
            )

    if errors:
        raise TopologyValidationError(errors)

    return usage
