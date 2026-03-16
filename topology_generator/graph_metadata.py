from __future__ import annotations

import re
from typing import Any, TypedDict, cast

import networkx as nx


class GraphAttrs(TypedDict, total=False):
    is_multi_fabric: bool
    fabric_names: tuple[str, ...]
    fabric_name: str


class NodeAttrs(TypedDict, total=False):
    layer_index: int
    layer_name: str
    placement: str
    placement_scope: str | None
    scope_names: tuple[str, ...]
    scope_indexes: tuple[int, ...]
    scope_labels: tuple[str, ...]
    scope_key: tuple[tuple[str, int], ...]
    group_name: str | None
    group_index: int | None
    group_label: str | None
    group_order: int | None
    node_ordinal: int
    physical_node_ordinal: int
    aggregate_bandwidth_gb: float
    aggregate_bandwidth_down: float
    aggregate_bandwidth_up: float
    total_lane_units: int
    base_lane_bandwidth_gb: float
    supported_port_bandwidths_gb: tuple[float, ...]
    used_bandwidth_gb: float
    used_lane_units: int
    fabric: str | None
    is_shared_gpu_node: bool
    fabric_metrics: dict[str, "NodeAttrs"]


class EdgeAttrs(TypedDict, total=False):
    source_ports: list[int]
    target_ports: list[int]
    num_cables: int
    cable_bandwidth_gb: float
    source_lane_units_per_cable: int
    target_lane_units_per_cable: int
    fabric: str | None


class FanoutAnnotation(TypedDict):
    center: tuple[float, float]
    width: float
    height: float
    theta1: float
    theta2: float
    label: str
    label_pos: tuple[float, float]


class OrientedEdgeAllocation(TypedDict):
    source_node_id: str
    target_node_id: str
    source_ports: list[int]
    target_ports: list[int]
    source_lane_units: int
    target_lane_units: int


def graph_attrs(graph: nx.Graph) -> GraphAttrs:
    return cast(GraphAttrs, graph.graph)


def node_attrs(graph: nx.Graph, node_id: str) -> NodeAttrs:
    return cast(NodeAttrs, graph.nodes[node_id])


def edge_attrs(graph: nx.Graph, source: str, target: str) -> EdgeAttrs:
    return cast(EdgeAttrs, graph.edges[source, target])


def flatten_node_attrs_for_fabric(
    attrs: dict[str, Any],
    fabric_name: str | None,
) -> NodeAttrs | None:
    if fabric_name is None:
        return cast(NodeAttrs, attrs)

    if attrs.get("is_shared_gpu_node"):
        fabric_metrics = attrs.get("fabric_metrics")
        if not isinstance(fabric_metrics, dict) or fabric_name not in fabric_metrics:
            return None
        flattened_attrs = {
            key: value for key, value in attrs.items() if key != "fabric_metrics"
        }
        flattened_attrs.update(cast(dict[str, object], fabric_metrics[fabric_name]))
        flattened_attrs["fabric"] = fabric_name
        return cast(NodeAttrs, flattened_attrs)

    if attrs.get("fabric") == fabric_name:
        return cast(NodeAttrs, attrs)

    return None


def is_multi_fabric_graph(graph: nx.Graph) -> bool:
    return bool(graph_attrs(graph).get("is_multi_fabric"))


def fabric_names(graph: nx.Graph) -> tuple[str, ...]:
    return tuple(graph_attrs(graph).get("fabric_names", ()))


def fabric_name_for_edge(attrs: EdgeAttrs | dict[str, object]) -> str | None:
    fabric = attrs.get("fabric")
    return fabric if isinstance(fabric, str) else None


def node_group_label(attrs: NodeAttrs | dict[str, object]) -> str:
    label = attrs.get("group_label")
    return str(label or "global")


def cable_bandwidth_gb(attrs: EdgeAttrs | dict[str, object]) -> float:
    value = attrs.get("cable_bandwidth_gb", 0.0)
    if not isinstance(value, (int, float)):
        raise ValueError("Edge attribute 'cable_bandwidth_gb' must be numeric.")
    return float(value)


def cable_count(attrs: EdgeAttrs | dict[str, object]) -> int:
    value = attrs.get("num_cables", 0)
    if not isinstance(value, int):
        raise ValueError("Edge attribute 'num_cables' must be an integer.")
    return value


def natural_sort_key(value: str) -> tuple[object, ...]:
    parts = re.split(r"(\d+)", value)
    return tuple(int(part) if part.isdigit() else part for part in parts)


def node_sort_key(
    node_id: str,
    attrs: NodeAttrs | dict[str, object],
    natural_key: tuple[object, ...] | None = None,
) -> tuple[object, ...]:
    if natural_key is None:
        natural_key = natural_sort_key(node_id)
    scope_indexes = attrs.get("scope_indexes")
    normalized_scope_indexes = (
        tuple(scope_indexes)
        if isinstance(scope_indexes, tuple)
        else ()
    )
    node_ordinal = attrs.get("node_ordinal", 0)
    return (
        attrs["layer_index"],
        1 if not normalized_scope_indexes else 0,
        normalized_scope_indexes,
        node_ordinal,
        natural_key,
    )
