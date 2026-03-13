import os

import networkx as nx
import pandas as pd


PORT_MAPPING_COLUMNS = [
    "source_serial_number",
    "source_node_id",
    "source_node_port",
    "target_node_port",
    "target_node_id",
    "target_serial_number",
    "cable_number",
]


def extract_port_mapping_rows(graph: nx.Graph) -> list[dict[str, object]]:
    """Extract stable, per-cable mapping rows from the topology graph."""
    rows: list[dict[str, object]] = []
    cable_counter = 1

    sorted_edges = sorted(
        graph.edges(data=True),
        key=lambda edge: _edge_sort_key(graph, edge[0], edge[1]),
    )

    for source_node_id, target_node_id, attrs in sorted_edges:
        source_ports, target_ports = _orient_edge_ports(
            graph,
            source_node_id,
            target_node_id,
            attrs.get("source_ports", []),
            attrs.get("target_ports", []),
        )

        if _should_swap_edge_orientation(graph, source_node_id, target_node_id):
            source_node_id, target_node_id = target_node_id, source_node_id

        for source_port, target_port in zip(source_ports, target_ports):
            rows.append(
                {
                    "source_serial_number": None,
                    "source_node_id": source_node_id,
                    "source_node_port": source_port,
                    "target_node_port": target_port,
                    "target_node_id": target_node_id,
                    "target_serial_number": None,
                    "cable_number": cable_counter,
                }
            )
            cable_counter += 1

    return rows


def create_port_mapping(graph: nx.Graph) -> pd.DataFrame:
    """Create a port mapping from the network topology graph."""
    return pd.DataFrame(extract_port_mapping_rows(graph), columns=PORT_MAPPING_COLUMNS)


def save_to_excel(
    df: pd.DataFrame, output_path: str, filename: str = "port_mapping.xlsx"
) -> None:
    """Save the port mapping to an Excel file."""
    os.makedirs(output_path, exist_ok=True)
    df.to_excel(os.path.join(output_path, filename), index=False)


def _edge_sort_key(graph: nx.Graph, source: str, target: str) -> tuple[int, str, int, str]:
    lower_node, upper_node = sorted(
        (source, target),
        key=lambda node: (graph.nodes[node]["layer_index"], node),
    )
    return (
        graph.nodes[lower_node]["layer_index"],
        lower_node,
        graph.nodes[upper_node]["layer_index"],
        upper_node,
    )


def _should_swap_edge_orientation(graph: nx.Graph, source: str, target: str) -> bool:
    return graph.nodes[source]["layer_index"] > graph.nodes[target]["layer_index"]


def _orient_edge_ports(
    graph: nx.Graph,
    source: str,
    target: str,
    source_ports: list[int],
    target_ports: list[int],
) -> tuple[list[int], list[int]]:
    if _should_swap_edge_orientation(graph, source, target):
        return target_ports, source_ports
    return source_ports, target_ports
