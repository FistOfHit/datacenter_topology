from os import PathLike
from pathlib import Path
from collections.abc import Mapping
from dataclasses import dataclass
from typing import cast

import networkx as nx
import pandas as pd

from topology_generator.graph_metadata import (
    EdgeAttrs,
    LinkBundleAttrs,
    NodeAttrs,
    OrientedEdgeAllocation,
    cable_bandwidth_gb,
    fabric_name_for_edge,
    flatten_node_attrs_for_fabric,
    is_multi_fabric_graph,
    link_bundle_attrs,
    natural_sort_key,
    node_group_label,
    node_sort_key,
)
from topology_generator.topology_generator import (
    get_fabric_names,
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


@dataclass(frozen=True)
class PortMappingContext:
    fabric_name: str | None
    node_attrs_by_id: dict[str, NodeAttrs]
    node_sort_keys: dict[str, tuple[object, ...]]


def extract_port_mapping_rows(graph: nx.Graph) -> list[dict[str, object]]:
    """Extract stable, per-cable mapping rows from the topology graph."""
    if not is_multi_fabric_graph(graph):
        context = _build_port_mapping_context(graph)
        single_fabric_rows, _ = _extract_rows_for_context(
            context,
            list(graph.edges(data=True)),
            cable_counter=1,
        )
        return single_fabric_rows

    rows: list[dict[str, object]] = []
    cable_counter = 1
    edges_by_fabric: dict[str, list[tuple[str, str, dict[str, object]]]] = {
        fabric_name: [] for fabric_name in get_fabric_names(graph)
    }
    for source_node_id, target_node_id, attrs in graph.edges(data=True):
        fabric_name = fabric_name_for_edge(cast(EdgeAttrs, attrs))
        if fabric_name is None:
            continue
        edges_by_fabric[fabric_name].append((source_node_id, target_node_id, attrs))

    for fabric_name in get_fabric_names(graph):
        context = _build_port_mapping_context(graph, fabric_name)
        fabric_rows, cable_counter = _extract_rows_for_context(
            context,
            edges_by_fabric[fabric_name],
            cable_counter,
        )
        rows.extend(fabric_rows)
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
    df: pd.DataFrame,
    output_path: str | PathLike[str],
    filename: str = "port_mapping.xlsx",
) -> None:
    """Save the port mapping to an Excel file."""
    output_dir = Path(output_path)
    output_dir.mkdir(parents=True, exist_ok=True)
    df.to_excel(output_dir / filename, index=False)


def _extract_rows_for_context(
    context: PortMappingContext,
    edges: list[tuple[str, str, dict[str, object]]],
    cable_counter: int,
) -> tuple[list[dict[str, object]], int]:
    rows: list[dict[str, object]] = []
    edge_bundles: list[tuple[str, str, LinkBundleAttrs, int]] = []
    for source_node_id, target_node_id, attrs in edges:
        for bundle_index, bundle in enumerate(link_bundle_attrs(cast(EdgeAttrs, attrs))):
            edge_bundles.append((source_node_id, target_node_id, bundle, bundle_index))

    sorted_edge_bundles = sorted(
        edge_bundles,
        key=lambda edge_bundle: (
            _edge_sort_key(context, edge_bundle[0], edge_bundle[1]),
            edge_bundle[3],
        ),
    )

    for source_node_id, target_node_id, bundle_attrs, _ in sorted_edge_bundles:
        oriented = _orient_edge_allocation(
            context,
            source_node_id,
            target_node_id,
            bundle_attrs,
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
            _require_int(bundle_attrs, "num_cables"),
        )

        for source_port, target_port in zip(source_ports, target_ports):
            rows.append(
                {
                    **(
                        {"fabric": context.fabric_name}
                        if context.fabric_name is not None
                        else {}
                    ),
                    "source_serial_number": None,
                    "source_group": _node_group_label(context, source_node_id),
                    "source_node_id": source_node_id,
                    "source_node_port": source_port,
                    "source_lane_units": source_lane_units,
                    "target_node_port": target_port,
                    "target_lane_units": target_lane_units,
                    "target_node_id": target_node_id,
                    "target_group": _node_group_label(context, target_node_id),
                    "target_serial_number": None,
                    "cable_bandwidth_gb": cable_bandwidth_gb(bundle_attrs),
                    "cable_number": cable_counter,
                }
            )
            cable_counter += 1

    return rows, cable_counter


def _build_port_mapping_context(
    graph: nx.Graph,
    fabric_name: str | None = None,
) -> PortMappingContext:
    node_attrs_by_id = {
        node_id: attrs
        for node_id, raw_attrs in graph.nodes(data=True)
        if (attrs := flatten_node_attrs_for_fabric(raw_attrs, fabric_name)) is not None
    }
    natural_sort_keys = {node_id: natural_sort_key(node_id) for node_id in node_attrs_by_id}
    node_sort_keys = {
        node_id: node_sort_key(
            node_id,
            node_attrs_by_id[node_id],
            natural_sort_keys[node_id],
        )
        for node_id in node_attrs_by_id
    }
    return PortMappingContext(
        fabric_name=fabric_name,
        node_attrs_by_id=node_attrs_by_id,
        node_sort_keys=node_sort_keys,
    )


def _edge_sort_key(
    context: PortMappingContext,
    source: str,
    target: str,
) -> tuple[tuple[object, ...], tuple[object, ...]]:
    lower_node, upper_node = sorted(
        (source, target),
        key=context.node_sort_keys.__getitem__,
    )
    return (
        context.node_sort_keys[lower_node],
        context.node_sort_keys[upper_node],
    )


def _should_swap_edge_orientation(
    context: PortMappingContext,
    source: str,
    target: str,
) -> bool:
    return _node_attrs(context, source)["layer_index"] > _node_attrs(context, target)[
        "layer_index"
    ]


def _orient_edge_allocation(
    context: PortMappingContext,
    source: str,
    target: str,
    attrs: Mapping[str, object],
) -> OrientedEdgeAllocation:
    source_ports = _require_int_list(attrs, "source_ports")
    target_ports = _require_int_list(attrs, "target_ports")
    source_lane_units = _require_int(attrs, "source_lane_units_per_cable")
    target_lane_units = _require_int(attrs, "target_lane_units_per_cable")

    if _should_swap_edge_orientation(context, source, target):
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


def _node_attrs(context: PortMappingContext, node_id: str) -> NodeAttrs:
    return context.node_attrs_by_id[node_id]


def _node_group_label(context: PortMappingContext, node_id: str) -> str:
    return node_group_label(_node_attrs(context, node_id))


def _require_int_list(attrs: Mapping[str, object], key: str) -> list[int]:
    value = attrs.get(key)
    if not isinstance(value, list) or not all(isinstance(item, int) for item in value):
        raise ValueError(f"Edge attribute {key!r} must be a list of integers.")
    return cast(list[int], value)


def _require_int(attrs: Mapping[str, object], key: str) -> int:
    value = attrs.get(key)
    if not isinstance(value, int):
        raise ValueError(f"Edge attribute {key!r} must be an integer.")
    return value
