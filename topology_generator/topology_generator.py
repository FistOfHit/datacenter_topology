import networkx as nx
import logging


logger = logging.getLogger(__name__)


def add_network_layer(
    network: nx.Graph,
    config: dict,
    layer_type: str,
    bottom_layer_type: str | None,
    top_layer_type: str | None,
):
    """
    Add a layer of nodes to the network topology.

    Creates and adds nodes of a specific layer type (server, leaf, spine, core)
    to the network graph with appropriate attributes.

    Args:
        network: The NetworkX graph to add nodes to.
        config: Dictionary containing network configuration parameters.
        layer_type: Type of layer to add (server, leaf, spine, core).
        bottom_layer_type: Type of layer below this one (or None if bottom layer).
        top_layer_type: Type of layer above this one (or None if top layer).
    """
    # Configuration keys for this layer
    num_nodes_key = f"num_{layer_type}"
    aggregate_bw_key = f"aggregate_{layer_type}_bandwidth_gb"
    num_ports_key = f"{layer_type}_num_ports"
    port_bw_key = f"{layer_type}_port_bandwidth_gb"

    logger.info(f"Adding {config[num_nodes_key]} {layer_type}s to the network")

    # Add nodes with appropriate attributes
    for i in range(config[num_nodes_key]):
        node_name = f"{config[f'{layer_type}_name']}_{i+1}"

        # Basic node attributes
        attrs = {
            "type": layer_type,
            "aggregate_bandwidth_gb": config[aggregate_bw_key],
            "total_ports": config[num_ports_key],
            "port_bandwidth_gb": config[port_bw_key],
            "used_bandwidth_gb": 0.0,
            "used_ports_equivalent": 0.0,
            "next_available_port": 1,
        }

        # Calculate aggregate bandwidth for connections to the layer underneath
        attrs["aggregate_bandwidth_down"] = (
            (
                config[f"num_{bottom_layer_type}"]
                * config[f"{bottom_layer_type}_to_{layer_type}_num_cables"]
                * config[f"{bottom_layer_type}_to_{layer_type}_cable_bandwidth_gb"]
            )
            if bottom_layer_type
            else 0
        )

        # Calculate aggregate bandwidth for connections to the layer above
        attrs["aggregate_bandwidth_up"] = (
            (
                config[f"num_{top_layer_type}"]
                * config[f"{layer_type}_to_{top_layer_type}_num_cables"]
                * config[f"{layer_type}_to_{top_layer_type}_cable_bandwidth_gb"]
            )
            if top_layer_type
            else 0
        )

        network.add_node(node_name, **attrs)


def add_connections(
    G: nx.Graph,
    source_layer: str,
    target_layer: str,
    config: dict,
):
    """
    Add network connections between two layers in the topology.

    Creates edges between nodes in the source layer and nodes in the target layer,
    assigning appropriate port numbers and tracking bandwidth usage.

    Args:
        G: The NetworkX graph to add connections to.
        source_layer: The type of the source layer (e.g., "server", "leaf").
        target_layer: The type of the target layer (e.g., "leaf", "spine").
        config: Dictionary containing network configuration parameters.
    """
    # Skip if either layer doesn't exist in the configuration
    if (
        config.get(f"num_{source_layer}", 0) == 0
        or config.get(f"num_{target_layer}", 0) == 0
    ):
        logger.info(
            f"Skipping connections between {source_layer} and {target_layer} - layers not present"
        )
        return

    # Get all nodes for each layer
    source_nodes = [(n, d) for n, d in G.nodes(data=True) if d["type"] == source_layer]
    target_nodes = [(n, d) for n, d in G.nodes(data=True) if d["type"] == target_layer]

    # Get connection parameters from config
    num_cables = config[f"{source_layer}_to_{target_layer}_num_cables"]
    cable_bandwidth_gb = config[f"{source_layer}_to_{target_layer}_cable_bandwidth_gb"]

    for source, source_data in source_nodes:
        for target, target_data in target_nodes:
            source_port_list = []
            target_port_list = []

            for _ in range(num_cables):
                # Check if source has enough bandwidth available
                if (
                    source_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > source_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        f"Attempting to add a {cable_bandwidth_gb}G cable to {source}, "
                        f"but only {source_data['aggregate_bandwidth_gb'] - source_data['used_bandwidth_gb']}G "
                        f"is available"
                    )
                    continue

                # Check if target has enough bandwidth available
                if (
                    target_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > target_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        f"Attempting to add a {cable_bandwidth_gb}G cable to {target}, "
                        f"but only {target_data['aggregate_bandwidth_gb'] - target_data['used_bandwidth_gb']}G "
                        f"is available"
                    )
                    continue

                # Assign ports for this connection
                source_port = source_data["next_available_port"]
                target_port = target_data["next_available_port"]

                source_port_list.append(source_port)
                target_port_list.append(target_port)

                # Update the next available port
                source_data["next_available_port"] += 1
                target_data["next_available_port"] += 1

                # Update the used bandwidth
                source_data["used_bandwidth_gb"] += cable_bandwidth_gb
                target_data["used_bandwidth_gb"] += cable_bandwidth_gb

            # Only add an edge if at least one cable was successfully connected
            if source_port_list:
                G.add_edge(
                    source,
                    target,
                    source_ports=source_port_list,
                    target_ports=target_port_list,
                    num_cables=len(source_port_list),
                    cable_bandwidth_gb=cable_bandwidth_gb,
                )


def calculate_port_stats(G: nx.Graph):
    """
    Calculate port utilization statistics for all nodes in the network.

    Computes the equivalent number of ports used based on the bandwidth
    consumed and the port bandwidth capacity for each node.

    Args:
        G: The NetworkX graph containing the network topology.
    """
    for node, data in G.nodes(data=True):
        # Calculate equivalent ports used based on bandwidth utilization
        port_bandwidth = data["port_bandwidth_gb"]
        used_bandwidth = data["used_bandwidth_gb"]

        if port_bandwidth > 0:
            data["used_ports_equivalent"] = used_bandwidth / port_bandwidth
            logger.debug(
                f"Node {node}: {used_bandwidth}G bandwidth used "
                f"({data['used_ports_equivalent']:.1f} ports equivalent)"
            )
        else:
            data["used_ports_equivalent"] = 0
            logger.warning(f"Node {node} has zero port bandwidth configured")


def generate_topology(config: dict) -> nx.Graph:
    """
    Generate a network topology based on the provided configuration.

    This function creates a network graph with multiple layers (server, leaf, spine, core)
    and establishes connections between these layers according to the configuration.

    Args:
        config: Dictionary containing network configuration parameters.

    Returns:
        nx.Graph: A NetworkX graph representing the complete network topology.
    """
    logger.info("Starting network topology generation")

    # Initialize the network graph
    G = nx.Graph()

    # Add network layers from bottom to top
    add_network_layer(
        G,
        config,
        "server",
        None,  # Servers are the bottom layer
        "leaf",
    )

    add_network_layer(
        G,
        config,
        "leaf",
        "server",
        "spine" if config["num_spine"] > 0 else None,
    )

    # Add spine layer if specified in config
    if config["num_spine"] > 0:
        add_network_layer(
            G,
            config,
            "spine",
            "leaf",
            "core" if config["num_core"] > 0 else None,
        )

    # Add core layer if specified in config
    if config["num_core"] > 0:
        add_network_layer(
            G,
            config,
            "core",
            "spine",
            None,  # Core is the top layer
        )

    # Add connections between layers
    add_connections(G, "server", "leaf", config)
    add_connections(G, "leaf", "spine", config)
    add_connections(G, "spine", "core", config)

    # Calculate port statistics for each node
    calculate_port_stats(G)

    logger.info("Network topology generation completed")

    return G
