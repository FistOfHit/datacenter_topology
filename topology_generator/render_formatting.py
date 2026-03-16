from __future__ import annotations

import networkx as nx

from topology_generator.graph_metadata import (
    PortPoolAttrs,
    cable_bandwidth_gb,
    link_bundle_attrs,
)


MAX_NODE_NAME_CHARS = 12
NODE_NAME_FONT_SIZE = 8
NODE_METADATA_FONT_SIZE = 6.5
PORT_USAGE_VALUE_FONT_SIZE = 6.5
PORT_USAGE_LABEL_FONT_SIZE = PORT_USAGE_VALUE_FONT_SIZE
FANOUT_LABEL_FONT_SIZE = 8
LAYER_COLOR_PALETTE = [
    "#add8e6",
    "#90ee90",
    "#ffcccb",
    "#ffa07a",
    "#f4d35e",
    "#b8c0ff",
]
LINK_COLOR_PALETTE = [
    "#2a9d8f",
    "#e76f51",
    "#264653",
    "#f4a261",
    "#457b9d",
]


def format_node_name(name: str, max_chars: int = MAX_NODE_NAME_CHARS) -> str:
    display_name = name.strip()
    if len(display_name) <= max_chars:
        return display_name
    if max_chars <= 3:
        return display_name[:max_chars]
    return f"{display_name[: max_chars - 3].rstrip()}..."


def format_hidden_node_label(hidden_count: int) -> str:
    _ = hidden_count
    return "..."


def format_hidden_group_label(hidden_count: int) -> str:
    return format_hidden_node_label(hidden_count)


def format_group_label(group_name: str, group_index: int) -> str:
    return f"{group_name}_{group_index}"


def format_bandwidth(bandwidth_gb: float) -> str:
    if float(bandwidth_gb).is_integer():
        bandwidth_gb = int(bandwidth_gb)

    if bandwidth_gb >= 1000:
        tb_value = bandwidth_gb / 1000
        if float(tb_value).is_integer():
            tb_value = int(tb_value)
        return f"{tb_value} TB/s"
    return f"{bandwidth_gb} GB/s"


def format_fanout_label(num_cables: int, total_bandwidth_gb: float) -> str:
    _ = total_bandwidth_gb
    return f"{num_cables} cables"


def format_port_pool_summary(port_pool: PortPoolAttrs) -> str:
    return (
        f"{format_node_name(port_pool['name'], max_chars=8)}: "
        f"{port_pool['used_lane_units']}/{port_pool['total_lane_units']}"
    )


def format_additional_port_pools(hidden_pool_count: int) -> str:
    return f"+{hidden_pool_count} more pools"


def get_layer_height(layer_index: int, layer_spacing: float = 1.0) -> float:
    return float(layer_index) * layer_spacing


def get_layer_color(layer_index: int) -> str:
    return LAYER_COLOR_PALETTE[layer_index % len(LAYER_COLOR_PALETTE)]


def get_bandwidth_colors(graph: nx.Graph) -> dict[float, str]:
    unique_bandwidths = sorted(
        {
            cable_bandwidth_gb(bundle)
            for _, _, data in graph.edges(data=True)
            for bundle in link_bundle_attrs(data)
        }
    )

    bandwidth_colors = {bandwidth: "black" for bandwidth in unique_bandwidths}
    if len(unique_bandwidths) > 1:
        bandwidth_colors = {
            bandwidth: (
                "black"
                if index == 0
                else LINK_COLOR_PALETTE[(index - 1) % len(LINK_COLOR_PALETTE)]
            )
            for index, bandwidth in enumerate(unique_bandwidths)
        }
    return bandwidth_colors
