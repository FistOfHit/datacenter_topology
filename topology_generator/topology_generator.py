import logging
import re
from collections.abc import Mapping

import networkx as nx

from topology_generator.config_schema import (
    TopologyConfig,
    ensure_topology_config,
)

logger = logging.getLogger(__name__)


def normalize_node_name(name: str) -> str:
    """
    Normalize device names to lower snake case for node identifiers.

    Args:
        name: Raw device name from configuration.

    Returns:
        Normalized node-safe name.
    """
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized)
    return normalized.strip("_")


def add_network_layer(
    network: nx.Graph,
    config: Mapping[str, object] | TopologyConfig,
    layer_index: int,
) -> list[str]:
    """
    Add a layer of nodes to the network topology.

    Args:
        network: The NetworkX graph to add nodes to.
        config: Topology configuration.
        layer_index: Ordered layer index.

    Returns:
        The node ids created for the layer.
    """
    topology_config = ensure_topology_config(config)
    layer_config = topology_config.layer(layer_index)
    logger.info(f"Adding {layer_config.node_count_in_layer} nodes to layer {layer_index}")

    node_names: list[str] = []
    node_base_name = normalize_node_name(layer_config.name)
    if not node_base_name:
        node_base_name = f"layer_{layer_index}"

    for ordinal in range(layer_config.node_count_in_layer):
        node_name = f"{node_base_name}_{ordinal + 1}"
        attrs = {
            "layer_index": layer_index,
            "layer_name": layer_config.name,
            "aggregate_bandwidth_gb": (
                topology_config.derived_down_bandwidth_per_node(layer_index)
                + topology_config.derived_up_bandwidth_per_node(layer_index)
            ),
            "aggregate_bandwidth_down": topology_config.derived_down_bandwidth_per_node(
                layer_index
            ),
            "aggregate_bandwidth_up": topology_config.derived_up_bandwidth_per_node(
                layer_index
            ),
            "total_ports": layer_config.ports_per_node,
            "port_bandwidth_gb": layer_config.port_bandwidth_gb_per_port,
            "used_bandwidth_gb": 0.0,
            "used_ports_equivalent": 0.0,
            "next_available_port": 1,
        }
        network.add_node(node_name, **attrs)
        node_names.append(node_name)

    return node_names


def add_connections(
    graph: nx.Graph,
    lower_layer_index: int,
    upper_layer_index: int,
    config: Mapping[str, object] | TopologyConfig,
    layer_nodes: dict[int, list[str]] | None = None,
) -> None:
    """
    Add connections between two adjacent layers in the topology.
    """
    topology_config = ensure_topology_config(config)
    lower_layer = topology_config.layer(lower_layer_index)
    num_cables = lower_layer.uplink_cables_per_node_to_each_node_in_next_layer
    cable_bandwidth_gb = lower_layer.uplink_cable_bandwidth_gb

    if num_cables == 0:
        logger.info(
            "Skipping connections between layer %s and layer %s because "
            "uplink_cables_per_node_to_each_node_in_next_layer is zero",
            lower_layer_index,
            upper_layer_index,
        )
        return

    layer_nodes = layer_nodes or {}
    lower_node_names = layer_nodes.get(
        lower_layer_index,
        [
            node
            for node, data in graph.nodes(data=True)
            if data["layer_index"] == lower_layer_index
        ],
    )
    upper_node_names = layer_nodes.get(
        upper_layer_index,
        [
            node
            for node, data in graph.nodes(data=True)
            if data["layer_index"] == upper_layer_index
        ],
    )
    lower_nodes = [(name, graph.nodes[name]) for name in lower_node_names]
    upper_nodes = [(name, graph.nodes[name]) for name in upper_node_names]

    for lower_node, lower_data in lower_nodes:
        for upper_node, upper_data in upper_nodes:
            lower_ports: list[int] = []
            upper_ports: list[int] = []

            for _ in range(num_cables):
                if (
                    lower_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > lower_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        "Attempting to add a %sGB/s cable to %s, but only %sGB/s is available",
                        cable_bandwidth_gb,
                        lower_node,
                        lower_data["aggregate_bandwidth_gb"]
                        - lower_data["used_bandwidth_gb"],
                    )
                    continue

                if (
                    upper_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > upper_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        "Attempting to add a %sGB/s cable to %s, but only %sGB/s is available",
                        cable_bandwidth_gb,
                        upper_node,
                        upper_data["aggregate_bandwidth_gb"]
                        - upper_data["used_bandwidth_gb"],
                    )
                    continue

                lower_port = lower_data["next_available_port"]
                upper_port = upper_data["next_available_port"]
                lower_ports.append(lower_port)
                upper_ports.append(upper_port)

                lower_data["next_available_port"] += 1
                upper_data["next_available_port"] += 1
                lower_data["used_bandwidth_gb"] += cable_bandwidth_gb
                upper_data["used_bandwidth_gb"] += cable_bandwidth_gb

            if lower_ports:
                graph.add_edge(
                    lower_node,
                    upper_node,
                    source_ports=lower_ports,
                    target_ports=upper_ports,
                    num_cables=len(lower_ports),
                    cable_bandwidth_gb=cable_bandwidth_gb,
                )


def calculate_port_stats(graph: nx.Graph) -> None:
    """
    Calculate port utilization statistics for all nodes in the network.
    """
    for node, data in graph.nodes(data=True):
        port_bandwidth = data["port_bandwidth_gb"]
        used_bandwidth = data["used_bandwidth_gb"]

        if port_bandwidth > 0:
            data["used_ports_equivalent"] = used_bandwidth / port_bandwidth
            logger.debug(
                "Node %s: %sGB/s bandwidth used (%s ports equivalent)",
                node,
                used_bandwidth,
                f"{data['used_ports_equivalent']:.1f}",
            )
        else:
            data["used_ports_equivalent"] = 0
            logger.warning("Node %s has zero port bandwidth configured", node)


def generate_topology(config: Mapping[str, object] | TopologyConfig) -> nx.Graph:
    """
    Generate a network topology based on the provided configuration.
    """
    topology_config = ensure_topology_config(config)
    logger.info("Starting network topology generation")

    graph = nx.Graph()
    layer_nodes: dict[int, list[str]] = {}

    for layer in topology_config.layers:
        layer_nodes[layer.index] = add_network_layer(graph, topology_config, layer.index)

    for lower_index in range(len(topology_config.layers) - 1):
        add_connections(
            graph,
            lower_index,
            lower_index + 1,
            topology_config,
            layer_nodes=layer_nodes,
        )

    calculate_port_stats(graph)
    logger.info("Network topology generation completed")
    return graph
