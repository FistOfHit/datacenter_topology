from __future__ import annotations

import logging
import math
from os import PathLike
from pathlib import Path
from typing import Any, Mapping, cast

import networkx as nx

from topology_generator.graph_metadata import (
    FanoutAnnotation,
    LinkBundleAttrs,
    cable_bandwidth_gb,
    edge_attrs,
    link_bundle_attrs,
    node_attrs,
    port_pool_attrs,
    total_edge_bandwidth_gb,
    total_edge_cable_count,
)
from topology_generator.render_environment import load_matplotlib
from topology_generator.render_formatting import (
    FANOUT_LABEL_FONT_SIZE,
    NODE_METADATA_FONT_SIZE,
    NODE_NAME_FONT_SIZE,
    PORT_USAGE_LABEL_FONT_SIZE,
    PORT_USAGE_VALUE_FONT_SIZE,
    format_additional_port_pools,
    format_bandwidth,
    format_fanout_label,
    format_node_name,
    format_port_pool_summary,
    get_bandwidth_colors,
    get_layer_color,
)
from topology_generator.render_layout import (
    build_figure_size,
    build_render_summary,
    calculate_plot_limits,
    compute_group_bandwidth_arrow_x,
    estimate_text_width,
    get_leftmost_visible_nodes_by_layer,
    layer_bandwidth_from_summary,
)
from topology_generator.render_types import LayoutResult, NodeBoxGeometry, RenderSummary

logger = logging.getLogger(__name__)

AGGREGATE_BANDWIDTH_LEGEND_LABEL = "per node agg uplink/downlink BW"
AGGREGATE_BANDWIDTH_LEGEND_MARKER = "$↑/↓$"
TITLE_FONT_SIZE = 16


def _mpl():
    return load_matplotlib()


def build_legend_elements(graph: nx.Graph) -> list[Any]:
    mpl = _mpl()
    legend_elements = [
        mpl.Line2D(
            [0],
            [0],
            marker="o",
            color="w",
            markerfacecolor="w",
            markeredgecolor="black",
            markersize=10,
            label="Cable count",
        ),
        mpl.Line2D(
            [0],
            [0],
            color="black",
            linestyle="None",
            marker=AGGREGATE_BANDWIDTH_LEGEND_MARKER,
            markersize=12,
            label=AGGREGATE_BANDWIDTH_LEGEND_LABEL,
        ),
    ]
    for bandwidth, color in get_bandwidth_colors(graph).items():
        legend_elements.append(
            mpl.Patch(
                facecolor=color,
                label=format_bandwidth(float(bandwidth)),
            )
        )
    return legend_elements


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
    node_data: Mapping[str, Any],
    geometry: NodeBoxGeometry,
) -> None:
    mpl = _mpl()
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
        mpl.plt.text(
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
    mpl = _mpl()
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
    mpl.plt.text(
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
) -> FanoutAnnotation | None:
    x, y = pos[node]
    y_multiplier = 1 if direction == "up" else -1
    anchor_y = y + (geometry.half_height * y_multiplier)
    node_layer_index = node_attrs(graph, node)["layer_index"]

    total_cables = 0
    total_bandwidth_gb = 0.0
    visible_angles: list[float] = []

    for neighbor in graph.neighbors(node):
        neighbor_layer_index = node_attrs(graph, neighbor)["layer_index"]
        if direction == "up" and neighbor_layer_index <= node_layer_index:
            continue
        if direction == "down" and neighbor_layer_index >= node_layer_index:
            continue

        metadata = edge_attrs(graph, node, neighbor)
        num_cables = total_edge_cable_count(metadata)
        if num_cables <= 0:
            continue

        total_cables += num_cables
        total_bandwidth_gb += total_edge_bandwidth_gb(metadata)

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

    label_padding = geometry.fanout_radius_padding + 0.34

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


def draw_layer_bandwidth_indicators(
    graph: nx.Graph,
    ax: Any,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    for node in get_leftmost_visible_nodes_by_layer(graph, pos, visible_nodes).values():
        add_bandwidth_indicators(ax, pos, node, node_attrs(graph, node), geometry)


def draw_fanout_annotations(
    graph: nx.Graph,
    ax: Any,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    mpl = _mpl()
    occupied_label_boxes: list[tuple[float, float, float, float]] = []
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
            label_x, label_y, label_box = _resolve_fanout_label_position(
                annotation,
                occupied_label_boxes,
            )
            occupied_label_boxes.append(label_box)

            arc = mpl.Arc(
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
                label_x,
                label_y,
                annotation["label"],
                fontsize=FANOUT_LABEL_FONT_SIZE,
                ha="center",
                va="center",
                zorder=4,
                bbox=dict(facecolor="white", edgecolor="none", alpha=0.92, pad=0.2),
            )


def draw_visible_nodes(
    graph: nx.Graph,
    ax: Any,
    positions: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    geometry: NodeBoxGeometry,
) -> None:
    mpl = _mpl()
    for node in sorted(
        visible_nodes,
        key=lambda item: (node_attrs(graph, item)["layer_index"], positions[item][0]),
    ):
        x, y = positions[node]
        data = node_attrs(graph, node)
        ax.add_patch(
            mpl.Rectangle(
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
        pool_lines = _visible_port_pool_lines(data)
        if pool_lines:
            ax.text(
                x,
                y + geometry.ports_value_y_offset,
                pool_lines[0],
                fontsize=PORT_USAGE_VALUE_FONT_SIZE,
                ha="center",
                va="center",
                zorder=3,
            )
        if len(pool_lines) > 1:
            ax.text(
                x,
                y + geometry.ports_label_y_offset,
                pool_lines[1],
                fontsize=PORT_USAGE_LABEL_FONT_SIZE,
                ha="center",
                va="center",
                zorder=3,
            )


def _visible_port_pool_lines(data: Mapping[str, Any]) -> list[str]:
    pools = list(port_pool_attrs(cast(dict[str, object], data)))
    if not pools:
        return []
    if len(pools) == 1:
        return [format_port_pool_summary(pools[0])]
    if len(pools) == 2:
        return [
            format_port_pool_summary(pools[0]),
            format_port_pool_summary(pools[1]),
        ]
    return [
        format_port_pool_summary(pools[0]),
        format_additional_port_pools(len(pools) - 1),
    ]


def draw_group_bandwidth_arrows(
    graph: nx.Graph,
    ax: Any,
    layout: LayoutResult,
    render_summary: RenderSummary | None = None,
) -> None:
    if any(len(data.get("scope_key", ())) > 1 for _, data in graph.nodes(data=True)):
        _draw_multi_scope_bandwidth_arrows(graph, ax, layout)
        return
    if not layout.group_bounds:
        return

    group_indexes = {
        cast(int, node_attrs(graph, node).get("group_index"))
        for node in layout.positions
        if node_attrs(graph, node).get("group_index") is not None
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
        if render_summary is None:
            render_summary = build_render_summary(graph)
        bandwidth = render_summary.group_layer_bandwidths.get(
            (group_index, lower_index, upper_index),
            0.0,
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


def _draw_multi_scope_bandwidth_arrows(
    graph: nx.Graph,
    ax: Any,
    layout: LayoutResult,
) -> None:
    geometry = layout.profile.node_box
    bandwidths_by_scope_and_layer: dict[tuple[tuple[tuple[str, int], ...], int, int], float] = {}

    for source, target, attrs in graph.edges(data=True):
        source_data = node_attrs(graph, source)
        target_data = node_attrs(graph, target)
        lower_layer_index = min(source_data["layer_index"], target_data["layer_index"])
        upper_layer_index = max(source_data["layer_index"], target_data["layer_index"])
        shared_scope_key = _shared_scope_key(
            source_data.get("scope_key", ()),
            target_data.get("scope_key", ()),
        )
        if not shared_scope_key:
            continue
        key = (shared_scope_key, lower_layer_index, upper_layer_index)
        bandwidths_by_scope_and_layer[key] = (
            bandwidths_by_scope_and_layer.get(key, 0.0)
            + total_edge_bandwidth_gb(attrs)
        )

    for (scope_key, lower_layer_index, upper_layer_index), bandwidth in sorted(
        bandwidths_by_scope_and_layer.items(),
        key=lambda item: (len(item[0][0]), item[0][1], item[0][2], item[0][0]),
    ):
        scope_bound = _find_scope_bound(layout, graph, scope_key)
        descendant_nodes = [
            node
            for node in layout.visible_nodes
            if _scope_is_prefix(node_attrs(graph, node).get("scope_key", ()), scope_key)
            and node_attrs(graph, node)["layer_index"] in (lower_layer_index, upper_layer_index)
        ]
        if not descendant_nodes:
            continue
        base_x = (
            max(layout.positions[node][0] + (geometry.width / 2) for node in descendant_nodes)
            + 0.18
        )
        if scope_bound is not None:
            scope_right = scope_bound[0] + scope_bound[2]
            label_width = estimate_text_width(format_bandwidth(bandwidth), layout.profile)
            x_pos = min(
                scope_right - 0.45 - 0.22 - label_width,
                scope_right - 0.9,
            )
            x_pos = max(base_x, x_pos)
        else:
            x_pos = base_x
        add_layer_bandwidth_arrow(
            ax,
            layout.layer_heights[lower_layer_index],
            layout.layer_heights[upper_layer_index],
            bandwidth,
            x_pos,
        )


def _shared_scope_key(
    left_scope_key: tuple[tuple[str, int], ...],
    right_scope_key: tuple[tuple[str, int], ...],
) -> tuple[tuple[str, int], ...]:
    shared_parts: list[tuple[str, int]] = []
    for left_part, right_part in zip(left_scope_key, right_scope_key):
        if left_part != right_part:
            break
        shared_parts.append(left_part)
    return tuple(shared_parts)


def _scope_is_prefix(
    candidate_scope_key: tuple[tuple[str, int], ...],
    prefix_scope_key: tuple[tuple[str, int], ...],
) -> bool:
    return candidate_scope_key[: len(prefix_scope_key)] == prefix_scope_key


def _find_scope_bound(
    layout: LayoutResult,
    graph: nx.Graph,
    scope_key: tuple[tuple[str, int], ...],
) -> tuple[float, float, float, float, str] | None:
    if not scope_key:
        return None
    descendant_nodes = [
        node
        for node in layout.visible_nodes
        if _scope_is_prefix(node_attrs(graph, node).get("scope_key", ()), scope_key)
    ]
    if not descendant_nodes:
        return None
    scope_center_x = sum(layout.positions[node][0] for node in descendant_nodes) / len(descendant_nodes)
    label = f"{scope_key[-1][0]}_{scope_key[-1][1]}"
    candidate_bounds = [bound for bound in layout.group_bounds if bound[4] == label]
    if not candidate_bounds:
        return None
    if len(candidate_bounds) == 1:
        return candidate_bounds[0]

    return min(
        candidate_bounds,
        key=lambda bound: abs((bound[0] + (bound[2] / 2)) - scope_center_x),
    )


def _resolve_fanout_label_position(
    annotation: FanoutAnnotation,
    occupied_boxes: list[tuple[float, float, float, float]],
) -> tuple[float, float, tuple[float, float, float, float]]:
    label_x, label_y = annotation["label_pos"]
    center_x, center_y = annotation["center"]
    vector_x = label_x - center_x
    vector_y = label_y - center_y
    vector_length = max(0.001, math.hypot(vector_x, vector_y))
    unit_x = vector_x / vector_length
    unit_y = vector_y / vector_length
    label_half_width = max(0.62, len(annotation["label"]) * 0.085)
    label_half_height = 0.18

    for _ in range(8):
        candidate_box = (
            label_x - label_half_width,
            label_x + label_half_width,
            label_y - label_half_height,
            label_y + label_half_height,
        )
        if not any(_boxes_overlap(candidate_box, occupied_box) for occupied_box in occupied_boxes):
            return label_x, label_y, candidate_box
        label_x += unit_x * 0.34
        label_y += unit_y * 0.22

    return (
        label_x,
        label_y,
        (
            label_x - label_half_width,
            label_x + label_half_width,
            label_y - label_half_height,
            label_y + label_half_height,
        ),
    )


def _boxes_overlap(
    left_box: tuple[float, float, float, float],
    right_box: tuple[float, float, float, float],
    padding: float = 0.06,
) -> bool:
    left_left, left_right, left_bottom, left_top = left_box
    right_left, right_right, right_bottom, right_top = right_box
    return not (
        left_right + padding < right_left
        or right_right + padding < left_left
        or left_top + padding < right_bottom
        or right_top + padding < left_bottom
    )


def visualize_single_topology(
    graph: nx.Graph,
    layout: LayoutResult,
    output_dir: str | PathLike[str] | None = None,
    filename: str = "topology.png",
    title: str = "Network Topology",
    render_summary: RenderSummary | None = None,
) -> None:
    logger.info("Starting topology visualization")

    if render_summary is None:
        render_summary = build_render_summary(graph)
    mpl = _mpl()
    x_limits, y_limits = calculate_plot_limits(layout)
    figure_width, figure_height = build_figure_size(x_limits, y_limits, layout.profile)
    _, ax = mpl.plt.subplots(figsize=(figure_width, figure_height))
    bandwidth_colors = get_bandwidth_colors(graph)
    geometry = layout.profile.node_box

    for left, bottom, width, height, label in layout.group_bounds:
        ax.add_patch(
            mpl.Rectangle(
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
        if y1 < y2:
            y1 += geometry.half_height
            y2 -= geometry.half_height
        else:
            y1 -= geometry.half_height
            y2 += geometry.half_height

        metadata = edge_attrs(graph, source, target)
        bundles = list(link_bundle_attrs(metadata))
        for bundle_index, bundle in enumerate(bundles):
            _draw_link_bundle(
                mpl,
                bandwidth_colors,
                x1,
                y1,
                x2,
                y2,
                bundle,
                bundle_index,
                len(bundles),
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

    layer_indices = sorted(render_summary.all_nodes_by_layer)
    for lower_index, upper_index in zip(layer_indices[:-1], layer_indices[1:]):
        layer_bandwidth = layer_bandwidth_from_summary(
            render_summary,
            lower_index,
            upper_index,
        )
        if layer_bandwidth > 0:
            add_layer_bandwidth_arrow(
                ax,
                layout.layer_heights[lower_index],
                layout.layer_heights[upper_index],
                layer_bandwidth,
                layout.layer_bandwidth_x,
            )

    draw_group_bandwidth_arrows(graph, ax, layout, render_summary)
    ax.legend(
        handles=build_legend_elements(graph),
        loc="upper left",
        bbox_to_anchor=(0.01, 0.99),
    )

    mpl.plt.xlim(*x_limits)
    mpl.plt.ylim(*y_limits)
    mpl.plt.title(title, fontsize=TITLE_FONT_SIZE)
    mpl.plt.axis("off")

    if output_dir:
        output_path = Path(output_dir) / filename
        mpl.plt.savefig(
            output_path,
            bbox_inches="tight",
            dpi=300,
            pad_inches=layout.profile.save_padding_inches,
        )
        logger.info("Saved topology visualization to %s", output_path)
    else:
        mpl.plt.show()

    mpl.plt.close()


def _draw_link_bundle(
    mpl: Any,
    bandwidth_colors: dict[float, str],
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    bundle: LinkBundleAttrs,
    bundle_index: int,
    bundle_count: int,
) -> None:
    start_x, start_y, end_x, end_y = _offset_line_segment(
        x1,
        y1,
        x2,
        y2,
        _bundle_line_offset(bundle_index, bundle_count),
    )
    bandwidth = cable_bandwidth_gb(bundle)
    num_cables = bundle.get("num_cables", 0) or 1
    color = bandwidth_colors[bandwidth]

    mpl.plt.plot(
        [start_x, end_x],
        [start_y, end_y],
        "-",
        color=color,
        linewidth=2,
        zorder=1,
    )

    if num_cables > 1:
        mpl.plt.text(
            (start_x + end_x) / 2,
            (start_y + end_y) / 2,
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


def _bundle_line_offset(bundle_index: int, bundle_count: int) -> float:
    if bundle_count <= 1:
        return 0.0
    spacing = 0.12
    return (bundle_index - ((bundle_count - 1) / 2)) * spacing


def _offset_line_segment(
    x1: float,
    y1: float,
    x2: float,
    y2: float,
    offset: float,
) -> tuple[float, float, float, float]:
    if offset == 0:
        return x1, y1, x2, y2
    delta_x = x2 - x1
    delta_y = y2 - y1
    length = math.hypot(delta_x, delta_y)
    if length == 0:
        return x1, y1, x2, y2
    offset_x = -delta_y / length * offset
    offset_y = delta_x / length * offset
    return x1 + offset_x, y1 + offset_y, x2 + offset_x, y2 + offset_y
