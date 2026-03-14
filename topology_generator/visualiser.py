from __future__ import annotations

import importlib
import logging
import math
import os
import tempfile
from dataclasses import dataclass
from pathlib import Path
from typing import Any

import networkx as nx
from topology_generator.topology_generator import (
    build_fabric_output_name,
    get_fabric_names,
    get_fabric_view,
    is_multi_fabric_graph,
)

logger = logging.getLogger(__name__)


def _directory_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / ".write_test"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        return True
    except OSError:
        return False


def _resolve_mpl_config_dir() -> Path | None:
    default_dir = Path.home() / ".matplotlib"
    if _directory_is_writable(default_dir):
        return None

    fallback_dir = Path(tempfile.gettempdir()) / "topology_generator_matplotlib"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir


def _should_use_agg_backend() -> bool:
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


def ensure_matplotlib_environment() -> None:
    """Set safe Matplotlib defaults when the user has not provided them."""
    if "MPLCONFIGDIR" not in os.environ:
        fallback_dir = _resolve_mpl_config_dir()
        if fallback_dir is not None:
            os.environ["MPLCONFIGDIR"] = str(fallback_dir)

    if "MPLBACKEND" not in os.environ and _should_use_agg_backend():
        os.environ["MPLBACKEND"] = "Agg"


ensure_matplotlib_environment()
plt = importlib.import_module("matplotlib.pyplot")
Line2D = importlib.import_module("matplotlib.lines").Line2D
patches = importlib.import_module("matplotlib.patches")
Arc = patches.Arc
Patch = patches.Patch
Rectangle = patches.Rectangle


MAX_NODE_NAME_CHARS = 12
NODE_NAME_FONT_SIZE = 8
NODE_METADATA_FONT_SIZE = 6.5
PORT_USAGE_VALUE_FONT_SIZE = 6.5
PORT_USAGE_LABEL_FONT_SIZE = 5
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


@dataclass(frozen=True)
class NodeBoxGeometry:
    width: float
    height: float
    name_y_offset: float
    ordinal_y_offset: float
    ports_value_y_offset: float
    ports_label_y_offset: float
    aggregate_x_offset: float
    aggregate_text_offset: float
    aggregate_arrow_size: float
    aggregate_left_extent: float
    fanout_arc_width: float
    fanout_arc_height: float
    fanout_radius_padding: float
    fanout_narrow_extra_padding: float
    fanout_narrow_span_threshold_deg: float
    fanout_up_margin_deg: float
    fanout_down_margin_deg: float

    @property
    def half_height(self) -> float:
        return self.height / 2


@dataclass(frozen=True)
class LayoutProfile:
    node_box: NodeBoxGeometry
    layer_spacing: float
    grouped_node_offset: float
    global_node_offset: float
    group_side_padding: float
    group_vertical_padding: float
    two_group_inner_gap: float
    hidden_group_lane_width: float
    right_annotation_gap: float
    right_annotation_extent: float
    plot_padding_x: float
    plot_padding_y: float
    figure_width: float
    figure_height_min: float
    figure_height_max: float
    save_padding_inches: float
    placeholder_text_height: float
    placeholder_text_char_width: float

    def grouped_half_span(self) -> float:
        return (
            self.grouped_node_offset
            + (self.node_box.width / 2)
            + self.group_side_padding
            + self.node_box.aggregate_left_extent
        )


@dataclass(frozen=True)
class LayoutResult:
    positions: dict[str, tuple[float, float]]
    visible_nodes: set[str]
    group_bounds: list[tuple[float, float, float, float, str]]
    placeholder_labels: list[tuple[float, float, str]]
    profile: LayoutProfile
    layer_bandwidth_x: float
    layer_heights: dict[int, float]


def compute_node_box_geometry() -> NodeBoxGeometry:
    return NodeBoxGeometry(
        width=2.05,
        height=1.34,
        name_y_offset=0.42,
        ordinal_y_offset=0.16,
        ports_value_y_offset=-0.20,
        ports_label_y_offset=-0.45,
        aggregate_x_offset=-2.95,
        aggregate_text_offset=0.18,
        aggregate_arrow_size=0.18,
        aggregate_left_extent=3.95,
        fanout_arc_width=2.75,
        fanout_arc_height=1.12,
        fanout_radius_padding=0.26,
        fanout_narrow_extra_padding=0.16,
        fanout_narrow_span_threshold_deg=40.0,
        fanout_up_margin_deg=12.0,
        fanout_down_margin_deg=18.0,
    )


def build_layout_profile(total_group_count: int) -> LayoutProfile:
    _ = total_group_count
    return LayoutProfile(
        node_box=compute_node_box_geometry(),
        layer_spacing=4.0,
        grouped_node_offset=3.45,
        global_node_offset=2.45,
        group_side_padding=1.45,
        group_vertical_padding=1.18,
        two_group_inner_gap=2.7,
        hidden_group_lane_width=5.1,
        right_annotation_gap=0.55,
        right_annotation_extent=2.7,
        plot_padding_x=0.46,
        plot_padding_y=0.68,
        figure_width=18.0,
        figure_height_min=10.5,
        figure_height_max=15.5,
        save_padding_inches=0.14,
        placeholder_text_height=0.24,
        placeholder_text_char_width=0.08,
    )


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


def get_layer_height(layer_index: int, layer_spacing: float = 1.0) -> float:
    return float(layer_index) * layer_spacing


def get_layer_color(layer_index: int) -> str:
    return LAYER_COLOR_PALETTE[layer_index % len(LAYER_COLOR_PALETTE)]


def get_sorted_node_items(graph: nx.Graph) -> list[tuple[str, dict[str, Any]]]:
    return sorted(graph.nodes(data=True), key=_node_sort_key)


def select_visible_group_indices(group_indices: list[int]) -> list[int]:
    if len(group_indices) <= 2:
        return group_indices
    return [group_indices[0], group_indices[-1]]


def get_group_centers(
    visible_group_indices: list[int],
    profile: LayoutProfile,
    total_group_count: int,
) -> dict[int, float]:
    if not visible_group_indices:
        return {}
    if len(visible_group_indices) == 1:
        return {visible_group_indices[0]: 0.0}

    if total_group_count <= 2:
        center_distance = (2 * profile.grouped_half_span()) + profile.two_group_inner_gap
    else:
        center_distance = (
            (2 * profile.grouped_node_offset)
            + (2 * profile.node_box.width)
            + profile.hidden_group_lane_width
        )

    return {
        visible_group_indices[0]: -(center_distance / 2),
        visible_group_indices[-1]: center_distance / 2,
    }


def compute_group_lane_layout(
    total_group_count: int,
    visible_group_indices: list[int],
    profile: LayoutProfile,
) -> tuple[dict[int, float], float | None]:
    group_centers = get_group_centers(visible_group_indices, profile, total_group_count)
    hidden_placeholder_x = 0.0 if total_group_count > len(visible_group_indices) else None
    return group_centers, hidden_placeholder_x


def get_bandwidth_colors(graph: nx.Graph) -> dict[float, str]:
    unique_bandwidths = sorted(
        {
            data.get("cable_bandwidth_gb")
            for _, _, data in graph.edges(data=True)
            if data.get("cable_bandwidth_gb") is not None
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


def draw_arrow_symbol(
    ax: Any,
    arrow_size: float,
    base_x: float,
    base_y: float,
    direction: str = "up",
) -> None:
    multiplier = 1 if direction == "up" else -1
    ax.arrow(
        base_x,
        base_y,
        0,
        arrow_size * multiplier,
        head_width=arrow_size * 0.8,
        head_length=arrow_size * 0.45,
        fc="black",
        ec="black",
        length_includes_head=True,
        zorder=3,
    )


def add_bandwidth_indicators(
    ax: Any,
    pos: dict[str, tuple[float, float]],
    node: str,
    node_data: dict[str, Any],
    geometry: NodeBoxGeometry,
) -> None:
    x, y = pos[node]
    symbol_x = x + geometry.aggregate_x_offset
    adjustment = geometry.half_height - 0.08

    for direction, multiplier in {"up": 1, "down": -1}.items():
        aggregate_bandwidth = node_data.get(f"aggregate_bandwidth_{direction}", 0)
        if aggregate_bandwidth <= 0:
            continue

        symbol_y = y + adjustment * multiplier
        draw_arrow_symbol(
            ax,
            geometry.aggregate_arrow_size,
            symbol_x,
            symbol_y - (geometry.aggregate_arrow_size / 2) * multiplier,
            direction,
        )
        plt.text(
            symbol_x - geometry.aggregate_text_offset,
            symbol_y,
            format_bandwidth(aggregate_bandwidth),
            ha="right",
            va="center",
            fontsize=8,
            zorder=3,
        )


def add_layer_bandwidth_arrow(
    ax: Any,
    y1: float,
    y2: float,
    bandwidth_gb: float,
    x_pos: float,
) -> None:
    label_offset_x = 0.22
    arrow_properties = dict(
        head_width=0.1,
        head_length=0.1,
        fc="black",
        ec="black",
        length_includes_head=True,
        zorder=2,
    )

    midpoint_y = (y1 + y2) / 2
    arrow_length = 0.68
    ax.arrow(x_pos, midpoint_y, 0, arrow_length, **arrow_properties)
    ax.arrow(x_pos, midpoint_y, 0, -arrow_length, **arrow_properties)
    plt.text(
        x_pos + label_offset_x,
        midpoint_y,
        format_bandwidth(bandwidth_gb),
        ha="left",
        va="center",
        fontsize=8,
        color="black",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.85),
        zorder=3,
    )


def calculate_layer_bandwidth(
    graph: nx.Graph,
    lower_layer_nodes: list[str],
    upper_layer_nodes: list[str],
) -> float:
    total_bandwidth = 0.0
    lower_set = set(lower_layer_nodes)
    upper_set = set(upper_layer_nodes)

    for source, target, attrs in graph.edges(data=True):
        if {source, target} <= (lower_set | upper_set) and (
            (source in lower_set and target in upper_set)
            or (source in upper_set and target in lower_set)
        ):
            total_bandwidth += attrs.get("cable_bandwidth_gb", 0) * attrs.get(
                "num_cables", 0
            )

    return total_bandwidth


def _normalize_fanout_angle(angle: float, direction: str) -> float:
    if direction == "up":
        return max(5.0, min(175.0, angle))

    if angle < 0:
        angle += 360
    return max(185.0, min(355.0, angle))


def get_fanout_annotation(
    graph: nx.Graph,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    node: str,
    direction: str,
    geometry: NodeBoxGeometry,
) -> dict[str, Any] | None:
    x, y = pos[node]
    y_multiplier = 1 if direction == "up" else -1
    anchor_y = y + (geometry.half_height * y_multiplier)
    node_layer_index = graph.nodes[node]["layer_index"]

    total_cables = 0
    total_bandwidth_gb = 0.0
    visible_angles: list[float] = []

    for neighbor in graph.neighbors(node):
        neighbor_layer_index = graph.nodes[neighbor]["layer_index"]
        if direction == "up" and neighbor_layer_index <= node_layer_index:
            continue
        if direction == "down" and neighbor_layer_index >= node_layer_index:
            continue

        edge_data = graph.edges[node, neighbor]
        num_cables = edge_data.get("num_cables", 0)
        if num_cables <= 0:
            continue

        total_cables += num_cables
        total_bandwidth_gb += num_cables * float(edge_data.get("cable_bandwidth_gb", 0))

        if neighbor not in visible_nodes:
            continue

        neighbor_x, raw_neighbor_y = pos[neighbor]
        neighbor_anchor_y = raw_neighbor_y - (geometry.half_height * y_multiplier)
        angle = math.degrees(math.atan2(neighbor_anchor_y - anchor_y, neighbor_x - x))
        visible_angles.append(_normalize_fanout_angle(angle, direction))

    if total_cables <= 0 or total_bandwidth_gb <= 0 or len(visible_angles) < 2:
        return None

    if direction == "up":
        theta1 = min(visible_angles) - 6.0
        theta2 = max(visible_angles) + 6.0
    else:
        theta1 = min(visible_angles) - 8.0
        theta2 = max(visible_angles) + 8.0

    label_padding = geometry.fanout_radius_padding + 0.28
    if (theta2 - theta1) <= geometry.fanout_narrow_span_threshold_deg:
        label_padding += geometry.fanout_narrow_extra_padding

    mid_angle = math.radians((theta1 + theta2) / 2)
    arc_mid_x = x + (geometry.fanout_arc_width / 2) * math.cos(mid_angle)
    arc_mid_y = anchor_y + (geometry.fanout_arc_height / 2) * math.sin(mid_angle)
    label_x = arc_mid_x + label_padding * math.cos(mid_angle)
    label_y = arc_mid_y + label_padding * math.sin(mid_angle)
    label_y += 0.08 if direction == "up" else -0.08

    return {
        "center": (x, anchor_y),
        "width": geometry.fanout_arc_width,
        "height": geometry.fanout_arc_height,
        "theta1": theta1,
        "theta2": theta2,
        "label": format_fanout_label(total_cables, total_bandwidth_gb),
        "label_pos": (label_x, label_y),
    }


def get_leftmost_visible_nodes_by_layer(
    graph: nx.Graph,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
) -> dict[int, str]:
    leftmost_nodes: dict[int, str] = {}
    for node in visible_nodes:
        layer_index = graph.nodes[node]["layer_index"]
        if (
            layer_index not in leftmost_nodes
            or pos[node][0] < pos[leftmost_nodes[layer_index]][0]
        ):
            leftmost_nodes[layer_index] = node
    return leftmost_nodes


def draw_layer_bandwidth_indicators(
    graph: nx.Graph,
    ax: Any,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    for node in get_leftmost_visible_nodes_by_layer(graph, pos, visible_nodes).values():
        add_bandwidth_indicators(ax, pos, node, graph.nodes[node], geometry)


def draw_fanout_annotations(
    graph: nx.Graph,
    ax: Any,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    for node in get_leftmost_visible_nodes_by_layer(graph, pos, visible_nodes).values():
        for direction in ("up", "down"):
            annotation = get_fanout_annotation(
                graph,
                pos,
                visible_nodes,
                node,
                direction,
                geometry,
            )
            if not annotation:
                continue

            arc = Arc(
                annotation["center"],
                annotation["width"],
                annotation["height"],
                theta1=annotation["theta1"],
                theta2=annotation["theta2"],
                linewidth=1.5,
                color="black",
                zorder=3,
            )
            ax.add_patch(arc)
            ax.text(
                annotation["label_pos"][0],
                annotation["label_pos"][1],
                annotation["label"],
                fontsize=FANOUT_LABEL_FONT_SIZE,
                ha="center",
                va="center",
                zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.2),
            )


def visualize_topology(graph: nx.Graph, output_dir: str | None = None) -> None:
    if is_multi_fabric_graph(graph):
        for fabric_name in get_fabric_names(graph):
            _visualize_single_topology(
                get_fabric_view(graph, fabric_name),
                output_dir,
                filename=f"topology_{build_fabric_output_name(fabric_name)}.png",
                title=f"Network Topology ({fabric_name})",
            )
        return

    _visualize_single_topology(graph, output_dir)


def _visualize_single_topology(
    graph: nx.Graph,
    output_dir: str | None = None,
    filename: str = "topology.png",
    title: str = "Network Topology",
) -> None:
    logger.info("Starting topology visualization")

    layout = calculate_layout(graph)
    x_limits, y_limits = calculate_plot_limits(layout)
    figure_width, figure_height = build_figure_size(x_limits, y_limits, layout.profile)
    _, ax = plt.subplots(figsize=(figure_width, figure_height))
    bandwidth_colors = get_bandwidth_colors(graph)
    geometry = layout.profile.node_box

    for left, bottom, width, height, label in layout.group_bounds:
        ax.add_patch(
            Rectangle(
                (left, bottom),
                width,
                height,
                facecolor="none",
                edgecolor="#666666",
                linestyle="--",
                linewidth=1.0,
                zorder=0,
            )
        )
        ax.text(
            left + (width / 2),
            bottom - 0.28,
            label,
            ha="center",
            va="top",
            fontsize=9,
            fontweight="bold",
        )

    for x, y, text in layout.placeholder_labels:
        ax.text(
            x,
            y,
            text,
            ha="center",
            va="center",
            fontsize=13,
            fontweight="bold",
            fontfamily="monospace",
            zorder=1,
            bbox=dict(facecolor="white", edgecolor="none", alpha=0.85, pad=0.2),
        )

    for source, target in graph.edges():
        if source not in layout.visible_nodes or target not in layout.visible_nodes:
            continue

        x1, y1 = layout.positions[source]
        x2, y2 = layout.positions[target]
        bandwidth = graph.edges[source, target].get("cable_bandwidth_gb", 0)
        num_cables = graph.edges[source, target].get("num_cables", 1)
        color = bandwidth_colors[bandwidth]

        if y1 < y2:
            y1 += geometry.half_height
            y2 -= geometry.half_height
        else:
            y1 -= geometry.half_height
            y2 += geometry.half_height

        plt.plot([x1, x2], [y1, y2], "-", color=color, linewidth=2, zorder=1)

        if num_cables > 1:
            plt.text(
                (x1 + x2) / 2,
                (y1 + y2) / 2,
                str(num_cables),
                horizontalalignment="center",
                verticalalignment="center",
                bbox=dict(
                    facecolor="white",
                    edgecolor="black",
                    alpha=1,
                    boxstyle="circle",
                ),
                zorder=2,
                fontsize=8,
            )

    draw_visible_nodes(graph, ax, layout.positions, layout.visible_nodes, geometry)
    draw_layer_bandwidth_indicators(
        graph,
        ax,
        layout.positions,
        layout.visible_nodes,
        geometry,
    )
    draw_fanout_annotations(
        graph,
        ax,
        layout.positions,
        layout.visible_nodes,
        geometry,
    )

    all_nodes_by_layer = get_all_nodes_by_layer(graph)
    layer_indices = sorted(all_nodes_by_layer)
    for lower_index, upper_index in zip(layer_indices[:-1], layer_indices[1:]):
        layer_bandwidth = calculate_layer_bandwidth(
            graph,
            all_nodes_by_layer[lower_index],
            all_nodes_by_layer[upper_index],
        )
        if layer_bandwidth > 0:
            add_layer_bandwidth_arrow(
                ax,
                layout.layer_heights[lower_index],
                layout.layer_heights[upper_index],
                layer_bandwidth,
                layout.layer_bandwidth_x,
            )

    draw_group_bandwidth_arrows(graph, ax, layout)

    legend_elements = [
        Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="w",
            markeredgecolor="black",
            markersize=10,
            label="Cable count",
        )
    ]
    for bandwidth, color in bandwidth_colors.items():
        legend_elements.append(
            Patch(
                facecolor=color,
                label=format_bandwidth(float(bandwidth)),
            )
        )

    ax.legend(handles=legend_elements, loc="upper left", bbox_to_anchor=(0.01, 0.99))

    plt.xlim(*x_limits)
    plt.ylim(*y_limits)
    plt.title(title)
    plt.axis("off")

    if output_dir:
        output_path = f"{output_dir}/{filename}"
        plt.savefig(
            output_path,
            bbox_inches="tight",
            dpi=300,
            pad_inches=layout.profile.save_padding_inches,
        )
        logger.info("Saved topology visualization to %s", output_path)
    else:
        plt.show()

    plt.close()


def calculate_layout(graph: nx.Graph) -> LayoutResult:
    positions: dict[str, tuple[float, float]] = {}
    visible_nodes: set[str] = set()
    placeholder_labels: list[tuple[float, float, str]] = []
    sorted_nodes = get_sorted_node_items(graph)

    grouped_layers = get_grouped_layer_nodes(graph)
    grouped_layer_indices = sorted(grouped_layers)
    group_indices = sorted(
        {
            data["group_index"]
            for _, data in sorted_nodes
            if data.get("group_index") is not None
        }
    )
    total_group_count = len(group_indices)
    profile = build_layout_profile(total_group_count)
    layer_heights = compute_layer_heights(graph, profile)
    visible_group_indices = select_visible_group_indices(group_indices)
    group_centers, hidden_placeholder_x = compute_group_lane_layout(
        total_group_count,
        visible_group_indices,
        profile,
    )

    for layer_index, group_nodes in grouped_layers.items():
        y = layer_heights[layer_index]
        for group_index in visible_group_indices:
            nodes = group_nodes.get(group_index, [])
            if not nodes:
                continue
            visible_group_nodes, hidden_count = select_visible_nodes(nodes)
            positions.update(
                assign_node_positions(
                    visible_group_nodes,
                    group_centers[group_index],
                    y,
                    profile.grouped_node_offset,
                )
            )
            visible_nodes.update(visible_group_nodes)
            if hidden_count > 0:
                placeholder_labels.append(
                    (group_centers[group_index], y, format_hidden_node_label(hidden_count))
                )

    grouped_content_half_span = max(
        (
            abs(x) + (profile.node_box.width / 2)
            for node, (x, _) in positions.items()
            if graph.nodes[node].get("group_index") is not None
        ),
        default=0.0,
    )

    for layer_index, nodes in get_global_layer_nodes(graph).items():
        y = layer_heights[layer_index]
        visible_layer_nodes, hidden_count = select_visible_nodes(nodes)
        node_offset = profile.global_node_offset
        if hidden_count > 0:
            placeholder_half_width = estimate_text_half_width(
                format_hidden_node_label(hidden_count),
                profile,
            )
            node_offset = max(
                node_offset,
                placeholder_half_width + (profile.node_box.width / 2) + 0.4,
            )
            if grouped_content_half_span > 0:
                node_offset = max(
                    node_offset,
                    grouped_content_half_span - (profile.node_box.width * 2.0),
                )
        positions.update(
            assign_node_positions(
                visible_layer_nodes,
                0.0,
                y,
                node_offset,
            )
        )
        visible_nodes.update(visible_layer_nodes)
        if hidden_count > 0:
            placeholder_labels.append((0.0, y, format_hidden_node_label(hidden_count)))

    group_bounds = compute_group_container_bounds(
        graph,
        positions,
        grouped_layer_indices,
        visible_group_indices,
        profile,
    )

    if hidden_placeholder_x is not None and grouped_layer_indices:
        grouped_min_y = layer_heights[min(grouped_layer_indices)]
        grouped_max_y = layer_heights[max(grouped_layer_indices)]
        placeholder_labels.append(
            (
                hidden_placeholder_x,
                (grouped_min_y + grouped_max_y) / 2,
                format_hidden_group_label(total_group_count - len(visible_group_indices)),
            )
        )

    layer_bandwidth_x = compute_annotation_columns(positions, group_bounds, profile)
    return LayoutResult(
        positions=positions,
        visible_nodes=visible_nodes,
        group_bounds=group_bounds,
        placeholder_labels=placeholder_labels,
        profile=profile,
        layer_bandwidth_x=layer_bandwidth_x,
        layer_heights=layer_heights,
    )


def get_grouped_layer_nodes(graph: nx.Graph) -> dict[int, dict[int, list[str]]]:
    grouped_layers: dict[int, dict[int, list[str]]] = {}
    for node, data in get_sorted_node_items(graph):
        group_index = data.get("group_index")
        if group_index is None:
            continue
        grouped_layers.setdefault(data["layer_index"], {}).setdefault(group_index, []).append(node)
    return grouped_layers


def get_global_layer_nodes(graph: nx.Graph) -> dict[int, list[str]]:
    global_layers: dict[int, list[str]] = {}
    for node, data in get_sorted_node_items(graph):
        if data.get("group_index") is not None:
            continue
        global_layers.setdefault(data["layer_index"], []).append(node)
    return global_layers


def get_all_nodes_by_layer(graph: nx.Graph) -> dict[int, list[str]]:
    layers: dict[int, list[str]] = {}
    for node, data in get_sorted_node_items(graph):
        layers.setdefault(data["layer_index"], []).append(node)
    return layers


def compute_layer_heights(graph: nx.Graph, profile: LayoutProfile) -> dict[int, float]:
    sorted_nodes = get_sorted_node_items(graph)
    layer_indices = sorted({data["layer_index"] for _, data in sorted_nodes})
    grouped_layers = {
        data["layer_index"]
        for _, data in sorted_nodes
        if data.get("group_index") is not None
    }

    heights: dict[int, float] = {}
    current_y = 0.0
    previous_layer_index: int | None = None
    for layer_index in layer_indices:
        if previous_layer_index is not None:
            current_y += profile.layer_spacing
            if previous_layer_index in grouped_layers and layer_index not in grouped_layers:
                current_y += profile.layer_spacing * 0.1
        heights[layer_index] = current_y
        previous_layer_index = layer_index

    return heights


def _node_sort_key(item: tuple[str, dict[str, Any]]) -> tuple[int, int, int, str]:
    node, data = item
    return (
        data["layer_index"],
        data.get("group_order") or data.get("group_index") or 0,
        data.get("node_ordinal", 0),
        node,
    )


def compute_group_container_bounds(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    grouped_layer_indices: list[int],
    visible_group_indices: list[int],
    profile: LayoutProfile,
) -> list[tuple[float, float, float, float, str]]:
    if not grouped_layer_indices or not visible_group_indices:
        return []

    bounds: list[tuple[float, float, float, float, str]] = []
    layer_heights = compute_layer_heights(graph, profile)
    min_layer_y = layer_heights[min(grouped_layer_indices)]
    max_layer_y = layer_heights[max(grouped_layer_indices)]
    bottom = min_layer_y - profile.node_box.half_height - profile.group_vertical_padding
    top = max_layer_y + profile.node_box.half_height + profile.group_vertical_padding
    visible_nodes = set(positions)
    leftmost_nodes_by_layer = get_leftmost_visible_nodes_by_layer(graph, positions, visible_nodes)
    leftmost_visible_group = min(visible_group_indices)
    rightmost_visible_group = max(visible_group_indices)
    outer_padding = profile.group_side_padding * 0.8
    inner_padding = profile.group_side_padding * 0.4

    for group_index in visible_group_indices:
        group_nodes = [
            node
            for node, data in graph.nodes(data=True)
            if data.get("group_index") == group_index and node in positions
        ]
        left = min(positions[node][0] - (profile.node_box.width / 2) for node in group_nodes)
        right = max(positions[node][0] + (profile.node_box.width / 2) for node in group_nodes)

        if group_index == leftmost_visible_group:
            for node in leftmost_nodes_by_layer.values():
                node_data = graph.nodes[node]
                if node_data.get("group_index") != group_index:
                    continue
                if node_data["layer_index"] not in grouped_layer_indices:
                    continue
                symbol_x = positions[node][0] + profile.node_box.aggregate_x_offset
                max_bandwidth = max(
                    float(node_data.get("aggregate_bandwidth_up", 0)),
                    float(node_data.get("aggregate_bandwidth_down", 0)),
                )
                if max_bandwidth > 0:
                    label = format_bandwidth(max_bandwidth)
                    left = min(
                        left,
                        symbol_x
                        - profile.node_box.aggregate_text_offset
                        - estimate_text_width(label, profile),
                    )
                else:
                    left = min(left, symbol_x)

        if group_index == rightmost_visible_group:
            x_pos = compute_group_bandwidth_arrow_x(graph, positions, profile, group_index)
            for lower_index, upper_index in zip(grouped_layer_indices[:-1], grouped_layer_indices[1:]):
                bandwidth = calculate_group_layer_bandwidth(
                    graph,
                    lower_index,
                    upper_index,
                    group_index,
                )
                if bandwidth <= 0:
                    continue
                right = max(
                    right,
                    x_pos + 0.22 + estimate_text_width(format_bandwidth(bandwidth), profile),
                )

        if group_index == leftmost_visible_group:
            left -= outer_padding
            right += inner_padding
        elif group_index == rightmost_visible_group:
            left -= inner_padding
            right += outer_padding
        else:
            left -= outer_padding
            right += outer_padding
        bounds.append(
            (
                left,
                bottom,
                right - left,
                top - bottom,
                str(graph.nodes[group_nodes[0]].get("group_label") or f"group_{group_index}"),
            )
        )

    return bounds


def select_visible_nodes(nodes: list[str]) -> tuple[list[str], int]:
    if len(nodes) <= 2:
        return nodes, 0
    return [nodes[0], nodes[-1]], len(nodes) - 2


def assign_node_positions(
    nodes: list[str],
    center_x: float,
    y: float,
    node_offset: float,
) -> dict[str, tuple[float, float]]:
    if not nodes:
        return {}
    if len(nodes) == 1:
        return {nodes[0]: (center_x, y)}
    return {
        nodes[0]: (center_x - node_offset, y),
        nodes[-1]: (center_x + node_offset, y),
    }


def draw_visible_nodes(
    graph: nx.Graph,
    ax: Any,
    positions: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    for node in sorted(
        visible_nodes,
        key=lambda item: (graph.nodes[item]["layer_index"], positions[item][0]),
    ):
        x, y = positions[node]
        data = graph.nodes[node]
        ax.add_patch(
            Rectangle(
                (x - (geometry.width / 2), y - (geometry.height / 2)),
                geometry.width,
                geometry.height,
                facecolor=get_layer_color(data["layer_index"]),
                edgecolor="black",
                zorder=2,
            )
        )
        ax.text(
            x,
            y + geometry.name_y_offset,
            format_node_name(data["layer_name"]),
            fontsize=NODE_NAME_FONT_SIZE,
            ha="center",
            va="center",
            zorder=3,
        )
        ax.text(
            x,
            y + geometry.ordinal_y_offset,
            str(data["node_ordinal"]),
            fontsize=NODE_METADATA_FONT_SIZE,
            ha="center",
            va="center",
            zorder=3,
        )
        ax.text(
            x,
            y + geometry.ports_value_y_offset,
            f"{data['used_lane_units']}/{data['total_lane_units']}",
            fontsize=PORT_USAGE_VALUE_FONT_SIZE,
            ha="center",
            va="center",
            zorder=3,
        )
        ax.text(
            x,
            y + geometry.ports_label_y_offset,
            "lanes used",
            fontsize=PORT_USAGE_LABEL_FONT_SIZE,
            ha="center",
            va="center",
            zorder=3,
        )


def compute_annotation_columns(
    positions: dict[str, tuple[float, float]],
    group_bounds: list[tuple[float, float, float, float, str]],
    profile: LayoutProfile,
) -> float:
    content_right = max(
        [x for x, _ in positions.values()]
        + [left + width for left, _, width, _, _ in group_bounds]
        + [0.0]
    )
    return content_right + profile.right_annotation_gap


def calculate_group_layer_bandwidth(
    graph: nx.Graph,
    lower_layer_index: int,
    upper_layer_index: int,
    group_index: int,
) -> float:
    total_bandwidth = 0.0
    for source, target, attrs in graph.edges(data=True):
        source_data = graph.nodes[source]
        target_data = graph.nodes[target]
        if source_data["layer_index"] == lower_layer_index and target_data["layer_index"] == upper_layer_index:
            lower_node = source
            upper_node = target
        elif source_data["layer_index"] == upper_layer_index and target_data["layer_index"] == lower_layer_index:
            lower_node = target
            upper_node = source
        else:
            continue

        if (
            graph.nodes[lower_node].get("group_index") == group_index
            and graph.nodes[upper_node].get("group_index") == group_index
        ):
            total_bandwidth += attrs.get("cable_bandwidth_gb", 0) * attrs.get("num_cables", 0)
    return total_bandwidth


def draw_group_bandwidth_arrows(
    graph: nx.Graph,
    ax: Any,
    layout: LayoutResult,
) -> None:
    if not layout.group_bounds:
        return

    group_indexes = {
        graph.nodes[node].get("group_index")
        for node in layout.positions
        if graph.nodes[node].get("group_index") is not None
    }
    if not group_indexes:
        return

    group_index = max(
        group_indexes,
        key=lambda index: compute_group_bandwidth_arrow_x(
            graph,
            layout.positions,
            layout.profile,
            index,
        ),
    )

    grouped_layers = sorted(
        {
            data["layer_index"]
            for _, data in graph.nodes(data=True)
            if data.get("group_index") is not None
        }
    )
    if len(grouped_layers) < 2:
        return

    x_pos = compute_group_bandwidth_arrow_x(graph, layout.positions, layout.profile, group_index)
    for lower_index, upper_index in zip(grouped_layers[:-1], grouped_layers[1:]):
        bandwidth = calculate_group_layer_bandwidth(
            graph,
            lower_index,
            upper_index,
            group_index,
        )
        if bandwidth <= 0:
            continue
        add_layer_bandwidth_arrow(
            ax,
            layout.layer_heights[lower_index],
            layout.layer_heights[upper_index],
            bandwidth,
            x_pos,
        )


def compute_group_bandwidth_arrow_x(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    profile: LayoutProfile,
    group_index: int,
) -> float:
    visible_group_node_right = max(
        x + (profile.node_box.width / 2)
        for node, (x, _) in positions.items()
        if graph.nodes[node].get("group_index") == group_index
    )
    return visible_group_node_right + 0.18


def calculate_plot_limits(
    layout: LayoutResult,
) -> tuple[tuple[float, float], tuple[float, float]]:
    x_values = [x for x, _ in layout.positions.values()]
    y_values = [y for _, y in layout.positions.values()]

    for left, bottom, width, height, label in layout.group_bounds:
        x_values.extend([left, left + width])
        y_values.extend([bottom - 0.55, bottom, bottom + height])
        x_values.extend(
            [
                left + (width / 2) - estimate_text_half_width(label, layout.profile),
                left + (width / 2) + estimate_text_half_width(label, layout.profile),
            ]
        )

    for x, y, text in layout.placeholder_labels:
        half_width = estimate_text_half_width(text, layout.profile)
        x_values.extend([x - half_width, x + half_width])
        y_values.extend(
            [
                y - layout.profile.placeholder_text_height,
                y + layout.profile.placeholder_text_height,
            ]
        )

    x_values.append(layout.layer_bandwidth_x + layout.profile.right_annotation_extent)
    y_values.extend(
        [
            min(y_values, default=0.0) - 0.25,
            max(y_values, default=0.0) + 0.6,
        ]
    )

    if not x_values or not y_values:
        return (-3.0, 3.5), (-0.5, 1.5)

    return (
        (
            min(x_values) - layout.profile.plot_padding_x,
            max(x_values) + layout.profile.plot_padding_x,
        ),
        (
            min(y_values) - layout.profile.plot_padding_y,
            max(y_values) + layout.profile.plot_padding_y,
        ),
    )


def estimate_text_half_width(text: str, profile: LayoutProfile) -> float:
    return max(0.6, len(text) * profile.placeholder_text_char_width)


def estimate_text_width(text: str, profile: LayoutProfile) -> float:
    return estimate_text_half_width(text, profile) * 2


def build_figure_size(
    x_limits: tuple[float, float],
    y_limits: tuple[float, float],
    profile: LayoutProfile,
) -> tuple[float, float]:
    width_span = max(1.0, x_limits[1] - x_limits[0])
    height_span = max(1.0, y_limits[1] - y_limits[0])
    figure_height = profile.figure_width * (height_span / width_span)
    figure_height = min(profile.figure_height_max, max(profile.figure_height_min, figure_height))
    return profile.figure_width, figure_height
