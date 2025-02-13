import networkx as nx
import logging


logger = logging.getLogger(__name__)


def add_network_layer(
    network: nx.Graph,
    config: dict,
    layer_type: str,
    bottom_layer_type: str,
    top_layer_type: str,
):
    """
    Add a layer of nodes (servers/switches) to the network.

    Params:
        network: nx.Graph,
        config: dict,
        layer_type: str,
        bottom_layer_type: str,
        top_layer_type: str,
    """
    # Get attributes for this layer
    num_nodes_key = f"num_{layer_type}"
    aggregate_bw_key = f"aggregate_{layer_type}_bandwidth_gb"
    num_ports_key = f"{layer_type}_num_ports"
    port_bw_key = f"{layer_type}_port_bandwidth_gb"

    logger.info(f"Adding {config[num_nodes_key]} {layer_type}s to the network")

    # Add nodes with attributes
    for i in range(config[num_nodes_key]):
        node_name = f"{config[f'{layer_type}_name']}_{i+1}"

        attrs = {
            "type": layer_type,
            "aggregate_bandwidth_gb": config[aggregate_bw_key],
            "total_ports": config[num_ports_key],
            "port_bandwidth_gb": config[port_bw_key],
            "used_bandwidth_gb": 0.0,
            "used_ports_equivalent": 0.0,
            "next_available_port": 1,
        }

        # Calculate aggregate bandwidth for the layer underneath
        attrs["aggregate_bandwidth_down"] = (
            (
                config[f"num_{bottom_layer_type}"]
                * config[f"{bottom_layer_type}_to_{layer_type}_num_cables"]
                * config[f"{bottom_layer_type}_to_{layer_type}_cable_bandwidth_gb"]
            )
            if bottom_layer_type
            else 0
        )

        # Calculate aggregate bandwidth for the layer above
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
    Add connections between layers.

    Params:
        G: nx.Graph
        source_layer: str
        target_layer: str
        config: dict
    """
    source_nodes = [(n, d) for n, d in G.nodes(data=True) if d["type"] == source_layer]
    target_nodes = [(n, d) for n, d in G.nodes(data=True) if d["type"] == target_layer]

    num_cables = config[f"{source_layer}_to_{target_layer}_num_cables"]
    cable_bandwidth_gb = config[f"{source_layer}_to_{target_layer}_cable_bandwidth_gb"]

    for source, source_data in source_nodes:
        for target, target_data in target_nodes:
            source_port_list = []
            target_port_list = []

            for _ in range(num_cables):
                # Check if there is enough bandwidth available
                if (
                    source_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > source_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        f"Attempting to add a {cable_bandwidth_gb}G cable to {source}, but only {source_data['aggregate_bandwidth_gb'] - source_data['used_bandwidth_gb']}G is available"
                    )
                    continue
                if (
                    target_data["used_bandwidth_gb"] + cable_bandwidth_gb
                    > target_data["aggregate_bandwidth_gb"]
                ):
                    logger.warning(
                        f"Attempting to add a {cable_bandwidth_gb}G cable to {target}, but only {target_data['aggregate_bandwidth_gb'] - target_data['used_bandwidth_gb']}G is available"
                    )
                    continue

                # Assign ports
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

            G.add_edge(
                source,
                target,
                source_ports=source_port_list,
                target_ports=target_port_list,
                num_cables=num_cables,
                cable_bandwidth_gb=cable_bandwidth_gb,
            )


def calculate_port_stats(G: nx.Graph):
    """
    Calculate used ports for each node based.

    Params:
        G: nx.Graph
    """
    for node in G.nodes():
        G.nodes[node]["used_ports_equivalent"] = (
            G.nodes[node]["used_bandwidth_gb"] / G.nodes[node]["port_bandwidth_gb"]
        )


def generate_topology(config: dict) -> nx.Graph:
    """
    Generate the network topology based on the given configuration.

    Params:
        config: dict

    Returns:
        nx.Graph
    """
    logger.info("Starting network topology generation")

    G = nx.Graph()

    # Add network layers
    add_network_layer(
        G,
        config,
        "server",
        None,
        "leaf",
    )
    add_network_layer(
        G,
        config,
        "leaf",
        "server",
        "spine" if config["num_spine"] > 0 else None,
    )

    if config["num_spine"] > 0:
        add_network_layer(
            G,
            config,
            "spine",
            "leaf",
            "core" if config["num_core"] > 0 else None,
        )
    if config["num_core"] > 0:
        add_network_layer(
            G,
            config,
            "core",
            "spine",
            None,
        )

    # Add connections between layers
    add_connections(G, "server", "leaf", config)
    add_connections(G, "leaf", "spine", config)
    add_connections(G, "spine", "core", config)

    # Calculate used ports for each node
    calculate_port_stats(G)

    logger.info("Network topology generation completed")

    return G
