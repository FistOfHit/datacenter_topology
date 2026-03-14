from pathlib import Path
import re
from typing import TypedDict, cast

import networkx as nx
import pandas as pd

from topology_generator.topology_generator import (
    get_fabric_names,
    get_fabric_view,
    is_multi_fabric_graph,
)


PORT_MAPPING_COLUMNS = [
    "source_serial_number",
    "source_group",
    "source_node_id",
    "source_node_port",
    "source_lane_units",
    "target_node_port",
    "target_lane_units",
    "target_node_id",
    "target_group",
    "target_serial_number",
    "cable_bandwidth_gb",
    "cable_number",
]
MULTI_FABRIC_PORT_MAPPING_COLUMNS = ["fabric", *PORT_MAPPING_COLUMNS]


class OrientedEdgeAllocation(TypedDict):
    source_node_id: str
    target_node_id: str
    source_ports: list[int]
    target_ports: list[int]
    source_lane_units: int
    target_lane_units: int


def extract_port_mapping_rows(graph: nx.Graph) -> list[dict[str, object]]:
    """Extract stable, per-cable mapping rows from the topology graph."""
    if not is_multi_fabric_graph(graph):
        return _extract_single_fabric_rows(graph)

    rows: list[dict[str, object]] = []
    cable_counter = 1
    for fabric_name in get_fabric_names(graph):
        fabric_rows = _extract_single_fabric_rows(get_fabric_view(graph, fabric_name))
        for row in fabric_rows:
            rows.append(
                {
                    "fabric": fabric_name,
                    **row,
                    "cable_number": cable_counter,
                }
            )
            cable_counter += 1
    return rows


def create_port_mapping(graph: nx.Graph) -> pd.DataFrame:
    """Create a port mapping from the network topology graph."""
    columns = (
        MULTI_FABRIC_PORT_MAPPING_COLUMNS
        if is_multi_fabric_graph(graph)
        else PORT_MAPPING_COLUMNS
    )
    return pd.DataFrame(extract_port_mapping_rows(graph), columns=columns)


def save_to_excel(
    df: pd.DataFrame, output_path: str, filename: str = "port_mapping.xlsx"
) -> None:
    """Save the port mapping to an Excel file."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_dir / filename, index=False)


def _extract_single_fabric_rows(graph: nx.Graph) -> list[dict[str, object]]:
    rows: list[dict[str, object]] = []
    cable_counter = 1

    sorted_edges = sorted(
        graph.edges(data=True),
        key=lambda edge: _edge_sort_key(graph, edge[0], edge[1]),
    )

    for source_node_id, target_node_id, attrs in sorted_edges:
        oriented = _orient_edge_allocation(
            graph,
            source_node_id,
            target_node_id,
            attrs,
        )
        source_node_id = oriented["source_node_id"]
        target_node_id = oriented["target_node_id"]
        source_ports = oriented["source_ports"]
        target_ports = oriented["target_ports"]
        source_lane_units = oriented["source_lane_units"]
        target_lane_units = oriented["target_lane_units"]

        _validate_edge_allocation(
            source_node_id,
            target_node_id,
            source_ports,
            target_ports,
            _require_int(attrs, "num_cables"),
        )

        for source_port, target_port in zip(source_ports, target_ports):
            rows.append(
                {
                    "source_serial_number": None,
                    "source_group": _node_group_label(graph, source_node_id),
                    "source_node_id": source_node_id,
                    "source_node_port": source_port,
                    "source_lane_units": source_lane_units,
                    "target_node_port": target_port,
                    "target_lane_units": target_lane_units,
                    "target_node_id": target_node_id,
                    "target_group": _node_group_label(graph, target_node_id),
                    "target_serial_number": None,
                    "cable_bandwidth_gb": attrs.get("cable_bandwidth_gb"),
                    "cable_number": cable_counter,
                }
            )
            cable_counter += 1

    return rows


def _edge_sort_key(
    graph: nx.Graph,
    source: str,
    target: str,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    lower_node, upper_node = sorted(
        (source, target),
        key=lambda node: _node_sort_key(graph, node),
    )
    return (
        _node_sort_key(graph, lower_node),
        _node_sort_key(graph, upper_node),
    )


def _should_swap_edge_orientation(graph: nx.Graph, source: str, target: str) -> bool:
    return graph.nodes[source]["layer_index"] > graph.nodes[target]["layer_index"]


def _orient_edge_allocation(
    graph: nx.Graph,
    source: str,
    target: str,
    attrs: dict[str, object],
) -> OrientedEdgeAllocation:
    source_ports = _require_int_list(attrs, "source_ports")
    target_ports = _require_int_list(attrs, "target_ports")
    source_lane_units = _require_int(attrs, "source_lane_units_per_cable")
    target_lane_units = _require_int(attrs, "target_lane_units_per_cable")

    if _should_swap_edge_orientation(graph, source, target):
        return {
            "source_node_id": target,
            "target_node_id": source,
            "source_ports": target_ports,
            "target_ports": source_ports,
            "source_lane_units": target_lane_units,
            "target_lane_units": source_lane_units,
        }

    return {
        "source_node_id": source,
        "target_node_id": target,
        "source_ports": source_ports,
        "target_ports": target_ports,
        "source_lane_units": source_lane_units,
        "target_lane_units": target_lane_units,
    }


def _validate_edge_allocation(
    source_node_id: str,
    target_node_id: str,
    source_ports: list[int],
    target_ports: list[int],
    num_cables: int,
) -> None:
    if len(source_ports) != len(target_ports):
        raise ValueError(
            f"Edge allocation mismatch for {source_node_id!r} -> {target_node_id!r}: "
            f"{len(source_ports)} source allocations vs {len(target_ports)} target allocations."
        )
    if len(source_ports) != num_cables:
        raise ValueError(
            f"Edge allocation mismatch for {source_node_id!r} -> {target_node_id!r}: "
            f"num_cables={num_cables} but allocations contain {len(source_ports)} entries."
        )


def _node_group_label(graph: nx.Graph, node_id: str) -> str:
    return str(graph.nodes[node_id].get("group_label") or "global")


def _node_sort_key(graph: nx.Graph, node_id: str) -> tuple[object, ...]:
    attrs = graph.nodes[node_id]
    group_order = attrs.get("group_order")
    node_ordinal = attrs.get("node_ordinal", 0)
    return (
        attrs["layer_index"],
        1 if group_order is None else 0,
        group_order or 0,
        node_ordinal,
        _natural_sort_key(node_id),
    )


def _require_int_list(attrs: dict[str, object], key: str) -> list[int]:
    value = attrs.get(key)
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"Edge attribute {key!r} must be a list of integers.")
    return cast(list[int], value)


def _require_int(attrs: dict[str, object], key: str) -> int:
    value = attrs.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Edge attribute {key!r} must be an integer.")
    return value


def _natural_sort_key(value: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part for part in parts)
