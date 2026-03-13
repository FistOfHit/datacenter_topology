import os
import importlib
import logging
import math
import re
import tempfile
from pathlib import Path
from typing import Any

import networkx as nx

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


# Node box text layout.
MAX_NODE_NAME_CHARS = 10
NODE_NAME_FONT_SIZE = 8
NODE_METADATA_FONT_SIZE = 7
PORT_USAGE_VALUE_FONT_SIZE = 7
PORT_USAGE_LABEL_FONT_SIZE = 4.5
PORT_USAGE_VALUE_Y_OFFSET = -0.09
PORT_USAGE_LABEL_Y_OFFSET = -0.145

# Per-node aggregate bandwidth indicator placement.
AGGREGATE_BW_X_OFFSET = -0.95

# Fanout arc geometry around visible link bundles.
FANOUT_UP_ARC_MARGIN_DEGREES = 5
FANOUT_DOWN_ARC_MARGIN_DEGREES = 10
FANOUT_ARC_WIDTH = 1.0
FANOUT_ARC_HEIGHT = 0.34
FANOUT_ARC_RADIUS_PADDING = 0.12
FANOUT_NARROW_ARC_SPAN_THRESHOLD_DEGREES = 40
FANOUT_NARROW_ARC_EXTRA_PADDING = 0.1
FANOUT_LABEL_FONT_SIZE = 8

# Condensed-layer placement when only first/last nodes are shown.
CONDENSED_LEFT_X = -2.0
CONDENSED_RIGHT_X = 2.0
CONDENSED_CENTER_X = 0.0
CONDENSED_PLACEHOLDER_WIDTH = 1.4
CONDENSED_PLACEHOLDER_HEIGHT = 0.22
CONDENSED_COUNT_DIGITS = 4

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
    """Limit displayed node names so they fit within the node box."""
    normalized = re.sub(r"[^a-zA-Z0-9]+", "_", name.strip().lower())
    normalized = re.sub(r"_+", "_", normalized).strip("_")
    return normalized[:max_chars]


def split_node_label(node: str) -> tuple[str, str]:
    """Split a generated node label into display name and numeric suffix."""
    name, node_id = node.rsplit("_", 1)
    return format_node_name(name), node_id


def format_hidden_node_label(hidden_count: int) -> str:
    """Build a fixed-width condensed-layer label for hidden nodes."""
    return f"...({hidden_count:>{CONDENSED_COUNT_DIGITS}} more)..."


def format_bandwidth(bandwidth_gb: float) -> str:
    """Format bandwidth as a data rate in GB/s or TB/s as appropriate."""
    if float(bandwidth_gb).is_integer():
        bandwidth_gb = int(bandwidth_gb)

    if bandwidth_gb >= 1000:
        tb_value = bandwidth_gb / 1000
        if float(tb_value).is_integer():
            tb_value = int(tb_value)
        return f"{tb_value} TB/s"
    return f"{bandwidth_gb} GB/s"


def format_fanout_label(num_cables: int, bandwidth_gb: float) -> str:
    """Format a fanout annotation label."""
    return f"{num_cables} x {format_bandwidth(bandwidth_gb)}"


def get_layer_height(layer_index: int) -> float:
    """Return the y-position for a layer index."""
    return float(layer_index)


def get_layer_color(layer_index: int) -> str:
    """Return a stable color for a layer index."""
    return LAYER_COLOR_PALETTE[layer_index % len(LAYER_COLOR_PALETTE)]


def draw_arrow_symbol(
    ax: plt.Axes,
    arrow_size: float,
    base_x: float,
    base_y: float,
    direction: str = "up",
) -> None:
    """Draw an arrow symbol at the specified base coordinates."""
    multiplier = 1 if direction == "up" else -1
    ax.arrow(
        base_x,
        base_y,
        0,
        arrow_size * multiplier,
        head_width=arrow_size * 0.8,
        head_length=arrow_size * 0.4,
        fc="black",
        ec="black",
        length_includes_head=True,
    )


def add_bandwidth_indicators(
    ax: plt.Axes,
    pos: dict[str, tuple[float, float]],
    node: str,
    node_data: dict[str, Any],
    node_half_height: float = 0.15,
) -> None:
    """Add bandwidth arrows and values to a node."""
    x, y = pos[node]
    symbol_x = x + AGGREGATE_BW_X_OFFSET
    arrow_size = 0.04
    text_offset = 0.08
    adjustment = node_half_height - 0.05

    for direction, multiplier in {"up": 1, "down": -1}.items():
        aggregate_bandwidth = node_data.get(f"aggregate_bandwidth_{direction}", 0)
        if aggregate_bandwidth <= 0:
            continue

        symbol_y = y + adjustment * multiplier
        draw_arrow_symbol(
            ax,
            arrow_size,
            symbol_x,
            symbol_y - (arrow_size / 2) * multiplier,
            direction,
        )
        plt.text(
            symbol_x + text_offset,
            symbol_y,
            format_bandwidth(aggregate_bandwidth),
            ha="left",
            va="center",
            fontsize=8,
        )


def add_layer_bandwidth_arrow(
    ax: plt.Axes,
    y1: float,
    y2: float,
    bandwidth_gb: float,
    x_pos: float = 2.7,
) -> None:
    """Add a double-ended arrow showing total inter-layer bandwidth."""
    arrow_properties = dict(
        head_width=0.1,
        head_length=0.1,
        fc="black",
        ec="black",
        length_includes_head=True,
    )

    midpoint_y = (y1 + y2) / 2
    arrow_length = (y2 - y1) / 4
    ax.arrow(x_pos, midpoint_y, 0, arrow_length, **arrow_properties)
    ax.arrow(x_pos, midpoint_y, 0, -arrow_length, **arrow_properties)
    plt.text(
        x_pos + 0.15,
        midpoint_y,
        format_bandwidth(bandwidth_gb),
        ha="left",
        va="center",
        fontsize=8,
        color="black",
        bbox=dict(facecolor="white", edgecolor="none", alpha=0.8),
    )


def calculate_layer_bandwidth(
    graph: nx.Graph,
    lower_layer_nodes: list[str],
    upper_layer_nodes: list[str],
) -> float:
    """Calculate total bandwidth between two adjacent rendered layers."""
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
    """Normalize an edge angle into the relevant upper or lower hemisphere."""
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
    node_half_height: float = 0.15,
) -> dict[str, Any] | None:
    """Build the geometry and label data for a node's fanout annotation."""
    x, y = pos[node]
    y_multiplier = 1 if direction == "up" else -1
    anchor_y = y + (node_half_height * y_multiplier)
    node_layer_index = graph.nodes[node]["layer_index"]

    total_cables = 0
    bandwidths: set[float] = set()
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
        bandwidths.add(float(edge_data.get("cable_bandwidth_gb", 0)))

        if neighbor not in visible_nodes:
            continue

        neighbor_x, raw_neighbor_y = pos[neighbor]
        neighbor_anchor_y = raw_neighbor_y - (node_half_height * y_multiplier)
        angle = math.degrees(math.atan2(neighbor_anchor_y - anchor_y, neighbor_x - x))
        visible_angles.append(_normalize_fanout_angle(angle, direction))

    if total_cables <= 0 or len(visible_angles) < 2 or len(bandwidths) != 1:
        return None

    if direction == "up":
        theta1 = min(visible_angles) - FANOUT_UP_ARC_MARGIN_DEGREES
        theta2 = max(visible_angles) + FANOUT_UP_ARC_MARGIN_DEGREES
    else:
        theta1 = min(visible_angles) - FANOUT_DOWN_ARC_MARGIN_DEGREES
        theta2 = max(visible_angles) + FANOUT_DOWN_ARC_MARGIN_DEGREES

    label_padding = FANOUT_ARC_RADIUS_PADDING
    if (theta2 - theta1) <= FANOUT_NARROW_ARC_SPAN_THRESHOLD_DEGREES:
        label_padding += FANOUT_NARROW_ARC_EXTRA_PADDING

    mid_angle = math.radians((theta1 + theta2) / 2)
    arc_mid_x = x + (FANOUT_ARC_WIDTH / 2) * math.cos(mid_angle)
    arc_mid_y = anchor_y + (FANOUT_ARC_HEIGHT / 2) * math.sin(mid_angle)
    label_x = arc_mid_x + label_padding * math.cos(mid_angle)
    label_y = arc_mid_y + label_padding * math.sin(mid_angle)

    return {
        "center": (x, anchor_y),
        "width": FANOUT_ARC_WIDTH,
        "height": FANOUT_ARC_HEIGHT,
        "theta1": theta1,
        "theta2": theta2,
        "label": format_fanout_label(total_cables, next(iter(bandwidths))),
        "label_pos": (label_x, label_y),
    }


def get_leftmost_visible_nodes_by_layer(
    graph: nx.Graph,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
) -> dict[int, str]:
    """Select a single visible node per layer to anchor fanout annotations."""
    leftmost_nodes: dict[int, str] = {}
    for node in visible_nodes:
        layer_index = graph.nodes[node]["layer_index"]
        if layer_index not in leftmost_nodes or pos[node][0] < pos[leftmost_nodes[layer_index]][0]:
            leftmost_nodes[layer_index] = node
    return leftmost_nodes


def draw_layer_bandwidth_indicators(
    graph: nx.Graph,
    ax: plt.Axes,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
) -> None:
    """Draw aggregate bandwidth indicators once per layer on the leftmost visible node."""
    for node in get_leftmost_visible_nodes_by_layer(graph, pos, visible_nodes).values():
        add_bandwidth_indicators(ax, pos, node, graph.nodes[node])


def draw_fanout_annotations(
    graph: nx.Graph,
    ax: plt.Axes,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    node_half_height: float = 0.15,
) -> None:
    """Draw arc-based cable bundle annotations at visible node fanouts."""
    for node in get_leftmost_visible_nodes_by_layer(graph, pos, visible_nodes).values():
        for direction in ("up", "down"):
            annotation = get_fanout_annotation(
                graph,
                pos,
                visible_nodes,
                node,
                direction,
                node_half_height=node_half_height,
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
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.9, pad=0.2),
            )


def calculate_node_positions(
    layer_index: int,
    nodes: list[str],
) -> dict[str, tuple[float, float]]:
    """Calculate the positions of nodes in a layer."""
    positions: dict[str, tuple[float, float]] = {}
    min_spacing = 1.2
    y_position = get_layer_height(layer_index)

    if len(nodes) > 2:
        positions[nodes[0]] = (CONDENSED_LEFT_X, y_position)
        positions[nodes[-1]] = (CONDENSED_RIGHT_X, y_position)
    else:
        total_width = (len(nodes) - 1) * min_spacing
        start_x = -total_width / 2
        for index, node in enumerate(nodes):
            positions[node] = (float(start_x + (index * min_spacing)), y_position)

    return positions


def draw_condensed_layer(
    graph: nx.Graph,
    ax: plt.Axes,
    positions: dict[str, tuple[float, float]],
    layer_index: int,
    color: str,
) -> tuple[set[str], list[str]]:
    """Draw condensed nodes for a layer."""
    node_size = 2500
    node_names = [
        node
        for node, data in graph.nodes(data=True)
        if data["layer_index"] == layer_index
    ]
    visible_nodes: set[str] = set()
    nodes_to_draw = [node_names[0], node_names[-1]] if len(node_names) > 2 else node_names
    visible_nodes.update(nodes_to_draw)

    nx.draw_networkx_nodes(
        graph,
        positions,
        nodelist=nodes_to_draw,
        node_color=color,
        node_size=node_size,
        node_shape="s",
        edgecolors="black",
    )

    for node in nodes_to_draw:
        used_ports_equivalent = graph.nodes[node]["used_ports_equivalent"]
        total_ports = graph.nodes[node]["total_ports"]
        name, node_id = split_node_label(node)

        for index, line in enumerate((name, node_id)):
            ax.text(
                positions[node][0],
                positions[node][1] + 0.05 - (index * 0.07),
                line,
                fontsize=NODE_NAME_FONT_SIZE if index == 0 else NODE_METADATA_FONT_SIZE,
                ha="center",
                va="center",
            )

        ax.text(
            positions[node][0],
            positions[node][1] + PORT_USAGE_VALUE_Y_OFFSET,
            f"{used_ports_equivalent:.0f}/{total_ports}",
            fontsize=PORT_USAGE_VALUE_FONT_SIZE,
            ha="center",
            va="center",
        )
        ax.text(
            positions[node][0],
            positions[node][1] + PORT_USAGE_LABEL_Y_OFFSET,
            "ports used",
            fontsize=PORT_USAGE_LABEL_FONT_SIZE,
            ha="center",
            va="center",
        )

    if len(node_names) > 2:
        center_y = get_layer_height(layer_index)
        ax.add_patch(
            Rectangle(
                (
                    CONDENSED_CENTER_X - (CONDENSED_PLACEHOLDER_WIDTH / 2),
                    center_y - (CONDENSED_PLACEHOLDER_HEIGHT / 2),
                ),
                CONDENSED_PLACEHOLDER_WIDTH,
                CONDENSED_PLACEHOLDER_HEIGHT,
                facecolor="white",
                edgecolor="none",
                zorder=0,
            )
        )
        ax.text(
            CONDENSED_CENTER_X,
            center_y,
            format_hidden_node_label(len(node_names) - 2),
            horizontalalignment="center",
            verticalalignment="center",
            fontfamily="monospace",
            fontsize=8,
        )

    return visible_nodes, node_names


def get_bandwidth_colors(graph: nx.Graph) -> dict[float, str]:
    """Get stable link colors for each unique cable bandwidth."""
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


def get_nodes_by_layer(graph: nx.Graph) -> dict[int, list[str]]:
    """Cache node names per layer in insertion order."""
    nodes_by_layer: dict[int, list[str]] = {}
    for node, data in graph.nodes(data=True):
        nodes_by_layer.setdefault(data["layer_index"], []).append(node)
    return dict(sorted(nodes_by_layer.items()))


def calculate_plot_limits(
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
) -> tuple[tuple[float, float], tuple[float, float]]:
    """Calculate plot limits from the rendered nodes."""
    if not visible_nodes:
        return (-3.0, 3.5), (-0.5, 1.5)

    x_values = [pos[node][0] for node in visible_nodes]
    y_values = [pos[node][1] for node in visible_nodes]
    return (
        (min(x_values) - 1.0, max(x_values) + 1.5),
        (min(y_values) - 0.5, max(y_values) + 0.75),
    )


def visualize_topology(graph: nx.Graph, output_dir: str | None = None) -> None:
    """Visualize the network topology graph with colored edges by bandwidth."""
    logger.info("Starting topology visualization")

    _, ax = plt.subplots(figsize=(12, 8))
    nodes_by_layer = get_nodes_by_layer(graph)
    layer_positions: dict[str, tuple[float, float]] = {}

    for layer_index, nodes in nodes_by_layer.items():
        layer_positions.update(calculate_node_positions(layer_index, nodes))

    visible_nodes: set[str] = set()
    layer_node_names: dict[int, list[str]] = {}
    for layer_index, nodes in nodes_by_layer.items():
        visible_set, node_names = draw_condensed_layer(
            graph,
            ax,
            layer_positions,
            layer_index,
            get_layer_color(layer_index),
        )
        visible_nodes.update(visible_set)
        layer_node_names[layer_index] = node_names

    visible_edges = [
        (source, target)
        for source, target in graph.edges()
        if source in visible_nodes and target in visible_nodes
    ]
    node_half_height = 0.15
    bandwidth_colors = get_bandwidth_colors(graph)

    for source, target in visible_edges:
        x1, y1 = layer_positions[source]
        x2, y2 = layer_positions[target]
        bandwidth = graph.edges[source, target].get("cable_bandwidth_gb", 0)
        num_cables = graph.edges[source, target].get("num_cables", 1)
        color = bandwidth_colors[bandwidth]

        if y1 < y2:
            y1 += node_half_height
            y2 -= node_half_height
        else:
            y1 -= node_half_height
            y2 += node_half_height

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

    draw_layer_bandwidth_indicators(graph, ax, layer_positions, visible_nodes)
    draw_fanout_annotations(
        graph,
        ax,
        layer_positions,
        visible_nodes,
        node_half_height=node_half_height,
    )

    layer_indices = sorted(layer_node_names)
    for lower_index, upper_index in zip(layer_indices[:-1], layer_indices[1:]):
        layer_bandwidth = calculate_layer_bandwidth(
            graph,
            layer_node_names[lower_index],
            layer_node_names[upper_index],
        )
        if layer_bandwidth > 0:
            add_layer_bandwidth_arrow(
                ax,
                get_layer_height(lower_index),
                get_layer_height(upper_index),
                layer_bandwidth,
            )

    if len(bandwidth_colors) > 1:
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

        ax.legend(handles=legend_elements, loc="upper left", bbox_to_anchor=(0.02, 0.98))

    x_limits, y_limits = calculate_plot_limits(layer_positions, visible_nodes)
    plt.xlim(*x_limits)
    plt.ylim(*y_limits)
    plt.title("Network Topology")
    plt.axis("off")

    if output_dir:
        output_path = f"{output_dir}/topology.png"
        plt.savefig(output_path, bbox_inches="tight", dpi=300, pad_inches=0.5)
        logger.info("Saved topology visualization to %s", output_path)
    else:
        plt.show()
