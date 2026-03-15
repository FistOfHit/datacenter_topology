from __future__ import annotations

from typing import Any

import networkx as nx

from topology_generator.graph_metadata import cable_bandwidth_gb, cable_count, node_attrs, node_sort_key
from topology_generator.render_formatting import (
    format_bandwidth,
    format_hidden_group_label,
    format_hidden_node_label,
)
from topology_generator.render_types import (
    LayoutProfile,
    LayoutResult,
    NodeBoxGeometry,
    RenderSummary,
)


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


def build_render_summary(graph: nx.Graph) -> RenderSummary:
    sorted_node_items = sorted(graph.nodes(data=True), key=_node_sort_key)

    grouped_layer_nodes: dict[int, dict[int, list[str]]] = {}
    global_layer_nodes: dict[int, list[str]] = {}
    all_nodes_by_layer: dict[int, list[str]] = {}
    for node, data in sorted_node_items:
        layer_index = data["layer_index"]
        all_nodes_by_layer.setdefault(layer_index, []).append(node)

        group_index = data.get("group_index")
        if group_index is None:
            global_layer_nodes.setdefault(layer_index, []).append(node)
            continue

        grouped_layer_nodes.setdefault(layer_index, {}).setdefault(group_index, []).append(
            node
        )

    layer_bandwidths: dict[tuple[int, int], float] = {}
    group_layer_bandwidths: dict[tuple[int, int, int], float] = {}
    for source, target, attrs in graph.edges(data=True):
        source_data = node_attrs(graph, source)
        target_data = node_attrs(graph, target)
        source_layer_index = source_data["layer_index"]
        target_layer_index = target_data["layer_index"]
        lower_layer_index = min(source_layer_index, target_layer_index)
        upper_layer_index = max(source_layer_index, target_layer_index)
        bundle_bandwidth = cable_bandwidth_gb(attrs) * cable_count(attrs)
        layer_key = (lower_layer_index, upper_layer_index)
        layer_bandwidths[layer_key] = layer_bandwidths.get(layer_key, 0.0) + bundle_bandwidth

        source_group_index = source_data.get("group_index")
        target_group_index = target_data.get("group_index")
        if (
            source_group_index is not None
            and source_group_index == target_group_index
        ):
            group_key = (
                int(source_group_index),
                lower_layer_index,
                upper_layer_index,
            )
            group_layer_bandwidths[group_key] = (
                group_layer_bandwidths.get(group_key, 0.0) + bundle_bandwidth
            )

    return RenderSummary(
        sorted_node_items=sorted_node_items,
        grouped_layer_nodes=grouped_layer_nodes,
        global_layer_nodes=global_layer_nodes,
        all_nodes_by_layer=all_nodes_by_layer,
        layer_bandwidths=layer_bandwidths,
        group_layer_bandwidths=group_layer_bandwidths,
    )


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


def calculate_layer_bandwidth(
    graph: nx.Graph,
    lower_layer_nodes: list[str],
    upper_layer_nodes: list[str],
) -> float:
    if not lower_layer_nodes or not upper_layer_nodes:
        return 0.0

    total_bandwidth = 0.0
    lower_set = set(lower_layer_nodes)
    upper_set = set(upper_layer_nodes)

    for source, target, attrs in graph.edges(data=True):
        if {source, target} <= (lower_set | upper_set) and (
            (source in lower_set and target in upper_set)
            or (source in upper_set and target in lower_set)
        ):
            total_bandwidth += cable_bandwidth_gb(attrs) * cable_count(attrs)

    return total_bandwidth


def layer_bandwidth_from_summary(
    render_summary: RenderSummary,
    lower_layer_index: int,
    upper_layer_index: int,
) -> float:
    return render_summary.layer_bandwidths.get((lower_layer_index, upper_layer_index), 0.0)


def get_leftmost_visible_nodes_by_layer(
    graph: nx.Graph,
    pos: dict[str, tuple[float, float]],
    visible_nodes: set[str],
) -> dict[int, str]:
    leftmost_nodes: dict[int, str] = {}
    for node in visible_nodes:
        layer_index = node_attrs(graph, node)["layer_index"]
        if (
            layer_index not in leftmost_nodes
            or pos[node][0] < pos[leftmost_nodes[layer_index]][0]
        ):
            leftmost_nodes[layer_index] = node
    return leftmost_nodes


def calculate_layout(
    graph: nx.Graph,
    render_summary: RenderSummary | None = None,
) -> LayoutResult:
    if render_summary is None:
        render_summary = build_render_summary(graph)
    return _calculate_layout_from_summary(graph, render_summary)


def _calculate_layout_from_summary(
    graph: nx.Graph,
    render_summary: RenderSummary,
) -> LayoutResult:
    positions: dict[str, tuple[float, float]] = {}
    visible_nodes: set[str] = set()
    placeholder_labels: list[tuple[float, float, str]] = []
    sorted_nodes = render_summary.sorted_node_items

    grouped_layers = render_summary.grouped_layer_nodes
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
    layer_heights = _compute_layer_heights(sorted_nodes, profile)
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
            if node_attrs(graph, node).get("group_index") is not None
        ),
        default=0.0,
    )

    for layer_index, nodes in render_summary.global_layer_nodes.items():
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
        positions.update(assign_node_positions(visible_layer_nodes, 0.0, y, node_offset))
        visible_nodes.update(visible_layer_nodes)
        if hidden_count > 0:
            placeholder_labels.append((0.0, y, format_hidden_node_label(hidden_count)))

    group_bounds = compute_group_container_bounds(
        graph,
        positions,
        grouped_layer_indices,
        visible_group_indices,
        profile,
        layer_heights=layer_heights,
        render_summary=render_summary,
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
    return build_render_summary(graph).grouped_layer_nodes


def get_global_layer_nodes(graph: nx.Graph) -> dict[int, list[str]]:
    return build_render_summary(graph).global_layer_nodes


def get_all_nodes_by_layer(graph: nx.Graph) -> dict[int, list[str]]:
    return build_render_summary(graph).all_nodes_by_layer


def compute_layer_heights(graph: nx.Graph, profile: LayoutProfile) -> dict[int, float]:
    return _compute_layer_heights(build_render_summary(graph).sorted_node_items, profile)


def _compute_layer_heights(
    sorted_nodes: list[tuple[str, dict[str, Any]]],
    profile: LayoutProfile,
) -> dict[int, float]:
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


def _node_sort_key(item: tuple[str, dict[str, Any]]) -> tuple[object, ...]:
    node, data = item
    return node_sort_key(node, data)


def compute_group_container_bounds(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    grouped_layer_indices: list[int],
    visible_group_indices: list[int],
    profile: LayoutProfile,
    layer_heights: dict[int, float] | None = None,
    render_summary: RenderSummary | None = None,
) -> list[tuple[float, float, float, float, str]]:
    if not grouped_layer_indices or not visible_group_indices:
        return []

    bounds: list[tuple[float, float, float, float, str]] = []
    if layer_heights is None:
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
                node_data = node_attrs(graph, node)
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
                bandwidth = _group_layer_bandwidth(
                    graph,
                    lower_index,
                    upper_index,
                    group_index,
                    render_summary,
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
                str(node_attrs(graph, group_nodes[0]).get("group_label") or f"group_{group_index}"),
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
    return _group_layer_bandwidth(graph, lower_layer_index, upper_layer_index, group_index)


def _group_layer_bandwidth(
    graph: nx.Graph,
    lower_layer_index: int,
    upper_layer_index: int,
    group_index: int,
    render_summary: RenderSummary | None = None,
) -> float:
    if render_summary is None:
        render_summary = build_render_summary(graph)
    return _group_layer_bandwidth_from_summary(
        render_summary,
        lower_layer_index,
        upper_layer_index,
        group_index,
    )


def _group_layer_bandwidth_from_summary(
    render_summary: RenderSummary,
    lower_layer_index: int,
    upper_layer_index: int,
    group_index: int,
) -> float:
    return render_summary.group_layer_bandwidths.get(
        (group_index, lower_layer_index, upper_layer_index),
        0.0,
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
        if node_attrs(graph, node).get("group_index") == group_index
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
