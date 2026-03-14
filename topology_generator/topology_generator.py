import logging
from collections.abc import Mapping
from typing import Any

import networkx as nx

from topology_generator.config_schema import (
    TopologyConfig,
    ensure_topology_config,
    normalize_identifier,
)
from topology_generator.expander import ExpandedNode, ExpandedTopology, expand_topology
from topology_generator.validator import NodeUsage, validate_expanded_topology

logger = logging.getLogger(__name__)


class ContiguousLaneAllocator:
    """Allocate the lowest available contiguous lane span for each cable."""

    def __init__(self, total_lane_units: int):
        self._occupied = [False] * total_lane_units

    def allocate(self, lane_units: int) -> int:
        if lane_units <= 0:
            raise ValueError("lane_units must be greater than zero.")

        total_lane_units = len(self._occupied)
        for start_index in range(total_lane_units - lane_units + 1):
            if all(
                not self._occupied[index]
                for index in range(start_index, start_index + lane_units)
            ):
                for index in range(start_index, start_index + lane_units):
                    self._occupied[index] = True
                return start_index + 1
        raise ValueError(
            f"Unable to allocate {lane_units} contiguous lane units from "
            f"{total_lane_units} available units."
        )


def generate_topology(config: Mapping[str, object] | TopologyConfig) -> nx.Graph:
    """Generate a network topology graph from validated YAML config."""
    topology_config = ensure_topology_config(config)
    logger.info("Starting network topology generation")

    expanded_topology = expand_topology(topology_config)
    usage_by_node = validate_expanded_topology(expanded_topology)

    graph = nx.Graph()
    graph.graph["is_multi_fabric"] = topology_config.is_multi_fabric
    graph.graph["fabric_names"] = topology_config.fabric_names
    _add_expanded_nodes(graph, expanded_topology, usage_by_node)
    _add_expanded_links(graph, expanded_topology)

    logger.info("Network topology generation completed")
    return graph


def is_multi_fabric_graph(graph: nx.Graph) -> bool:
    return bool(graph.graph.get("is_multi_fabric"))


def get_fabric_names(graph: nx.Graph) -> tuple[str, ...]:
    return tuple(graph.graph.get("fabric_names", ()))


def get_fabric_view(graph: nx.Graph, fabric_name: str) -> nx.Graph:
    if not is_multi_fabric_graph(graph):
        return graph.copy()
    known_fabrics = get_fabric_names(graph)
    if fabric_name not in known_fabrics:
        raise KeyError(
            f"Unknown fabric {fabric_name!r}; available fabrics are {known_fabrics!r}."
        )

    fabric_view = nx.Graph()
    fabric_view.graph.update(graph.graph)
    fabric_view.graph["is_multi_fabric"] = False
    fabric_view.graph["fabric_names"] = ()
    fabric_view.graph["fabric_name"] = fabric_name

    for node_id, attrs in graph.nodes(data=True):
        if attrs.get("is_shared_gpu_node"):
            fabric_metrics = attrs.get("fabric_metrics", {})
            if fabric_name not in fabric_metrics:
                continue
            flattened_attrs = {
                key: value
                for key, value in attrs.items()
                if key != "fabric_metrics"
            }
            flattened_attrs.update(fabric_metrics[fabric_name])
            flattened_attrs["fabric"] = fabric_name
            fabric_view.add_node(node_id, **flattened_attrs)
            continue

        if attrs.get("fabric") == fabric_name:
            fabric_view.add_node(node_id, **attrs)

    for source, target, attrs in graph.edges(data=True):
        if attrs.get("fabric") != fabric_name:
            continue
        if source not in fabric_view or target not in fabric_view:
            continue
        fabric_view.add_edge(source, target, **attrs)

    return fabric_view


def build_fabric_output_name(fabric_name: str) -> str:
    """Build a filesystem-safe output suffix for a fabric name."""
    normalized_name = normalize_identifier(fabric_name)
    if not normalized_name:
        raise ValueError(f"Fabric name {fabric_name!r} cannot be normalized for output.")
    return normalized_name


def _add_expanded_nodes(
    graph: nx.Graph,
    expanded_topology: ExpandedTopology,
    usage_by_node: dict[str, NodeUsage],
) -> None:
    for node in expanded_topology.nodes:
        usage = usage_by_node[node.node_id]
        node_attrs = _build_node_attrs(node, usage)

        if not node.is_shared_gpu_node:
            graph.add_node(node.graph_node_id, **node_attrs)
            continue

        if node.graph_node_id not in graph:
            graph.add_node(
                node.graph_node_id,
                layer_index=node.layer_index,
                layer_name=node.layer_name,
                placement=node.placement,
                group_name=None,
                group_index=None,
                group_label=None,
                node_ordinal=node.physical_node_ordinal,
                physical_node_ordinal=node.physical_node_ordinal,
                group_order=None,
                is_shared_gpu_node=True,
                fabric_metrics={},
            )

        fabric_metrics = dict(graph.nodes[node.graph_node_id]["fabric_metrics"])
        fabric_metrics[node.fabric_name] = node_attrs
        graph.nodes[node.graph_node_id]["fabric_metrics"] = fabric_metrics


def _build_node_attrs(node: ExpandedNode, usage: NodeUsage) -> dict[str, Any]:
    return {
        "layer_index": node.layer_index,
        "layer_name": node.layer_name,
        "placement": node.placement,
        "group_name": node.group_name,
        "group_index": node.group_index,
        "group_label": node.group_label,
        "group_order": node.group_index,
        "node_ordinal": node.node_ordinal,
        "physical_node_ordinal": node.physical_node_ordinal,
        "aggregate_bandwidth_gb": usage.total_bandwidth_gb,
        "aggregate_bandwidth_down": usage.bandwidth_down_gb,
        "aggregate_bandwidth_up": usage.bandwidth_up_gb,
        "total_lane_units": node.total_lane_units,
        "base_lane_bandwidth_gb": node.base_lane_bandwidth_gb,
        "supported_port_bandwidths_gb": node.supported_port_bandwidths_gb,
        "used_bandwidth_gb": usage.total_bandwidth_gb,
        "used_lane_units": usage.required_lane_units,
        "fabric": node.fabric_name,
        "is_shared_gpu_node": node.is_shared_gpu_node,
    }


def _add_expanded_links(graph: nx.Graph, expanded_topology: ExpandedTopology) -> None:
    node_lookup = {node.node_id: node for node in expanded_topology.nodes}
    allocators: dict[tuple[str, str | None], ContiguousLaneAllocator] = {}
    for node in expanded_topology.nodes:
        allocator_key = _allocator_key(node)
        if allocator_key not in allocators:
            allocators[allocator_key] = ContiguousLaneAllocator(node.total_lane_units)

    for link in expanded_topology.links:
        source_node = node_lookup[link.source_node_id]
        target_node = node_lookup[link.target_node_id]
        source_ports = [
            allocators[_allocator_key(source_node)].allocate(
                link.source_lane_units_per_cable
            )
            for _ in range(link.num_cables)
        ]
        target_ports = [
            allocators[_allocator_key(target_node)].allocate(
                link.target_lane_units_per_cable
            )
            for _ in range(link.num_cables)
        ]

        graph.add_edge(
            link.source_graph_node_id,
            link.target_graph_node_id,
            source_ports=source_ports,
            target_ports=target_ports,
            num_cables=link.num_cables,
            cable_bandwidth_gb=link.cable_bandwidth_gb,
            source_lane_units_per_cable=link.source_lane_units_per_cable,
            target_lane_units_per_cable=link.target_lane_units_per_cable,
            fabric=link.fabric_name,
        )


def _allocator_key(node: ExpandedNode) -> tuple[str, str | None]:
    if node.is_shared_gpu_node:
        return node.graph_node_id, node.fabric_name
    return node.graph_node_id, None
