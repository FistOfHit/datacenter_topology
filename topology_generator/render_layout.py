from __future__ import annotations

from dataclasses import replace
from typing import Any, cast

import networkx as nx

from topology_generator.graph_metadata import (
    node_attrs,
    node_sort_key,
    total_edge_bandwidth_gb,
)
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
        height=1.46,
        name_y_offset=0.47,
        ordinal_y_offset=0.18,
        ports_value_y_offset=-0.14,
        ports_label_y_offset=-0.42,
        aggregate_x_offset=-2.35,
        aggregate_text_offset=0.18,
        aggregate_arrow_size=0.18,
        aggregate_left_extent=3.35,
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
        bundle_bandwidth = total_edge_bandwidth_gb(attrs)
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
            total_bandwidth += total_edge_bandwidth_gb(attrs)

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
    if _has_multi_scope_layout(graph):
        return _calculate_multi_scope_layout(graph, render_summary)
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


def _has_multi_scope_layout(graph: nx.Graph) -> bool:
    scope_depths = {
        len(cast(tuple[tuple[str, int], ...], data.get("scope_key", ())))
        for _, data in graph.nodes(data=True)
        if data.get("scope_key")
    }
    placement_scopes = {
        str(scope_name)
        for _, data in graph.nodes(data=True)
        if (scope_name := data.get("placement_scope")) not in (None, "global")
    }
    return bool(scope_depths) and (max(scope_depths, default=0) > 1 or len(placement_scopes) > 1)


def _calculate_multi_scope_layout(
    graph: nx.Graph,
    render_summary: RenderSummary,
) -> LayoutResult:
    positions: dict[str, tuple[float, float]] = {}
    visible_nodes: set[str] = set()
    placeholder_labels: list[tuple[float, float, str]] = []
    sorted_nodes = render_summary.sorted_node_items

    scope_nodes_by_layer: dict[tuple[tuple[tuple[str, int], ...], int], list[str]] = {}
    all_scope_keys: set[tuple[tuple[str, int], ...]] = set()
    for node, data in sorted_nodes:
        scope_key = cast(tuple[tuple[str, int], ...], data.get("scope_key", ()))
        if not scope_key:
            continue
        all_scope_keys.add(scope_key)
        scope_nodes_by_layer.setdefault((scope_key, data["layer_index"]), []).append(node)

    top_scope_keys = sorted({scope_key[:1] for scope_key in all_scope_keys}, key=_scope_sort_key)
    profile = replace(
        build_layout_profile(len(top_scope_keys)),
        figure_width=36.0,
    )
    layer_heights = _compute_layer_heights(sorted_nodes, profile)

    all_children_by_parent: dict[tuple[tuple[str, int], ...] | None, list[tuple[tuple[str, int], ...]]] = {}
    for scope_key in sorted(all_scope_keys, key=_scope_sort_key):
        parent_key = scope_key[:-1] or None
        all_children_by_parent.setdefault(parent_key, []).append(scope_key)
    for parent_key in list(all_children_by_parent):
        all_children_by_parent[parent_key] = sorted(
            all_children_by_parent[parent_key],
            key=_scope_sort_key,
        )

    visible_children_by_parent: dict[
        tuple[tuple[str, int], ...] | None,
        list[tuple[tuple[str, int], ...]],
    ] = {}

    def populate_visible_scope_tree(
        parent_key: tuple[tuple[str, int], ...] | None,
    ) -> None:
        child_keys = all_children_by_parent.get(parent_key, [])
        if not child_keys:
            return
        visible_children = _select_visible_scope_keys(child_keys)
        visible_children_by_parent[parent_key] = visible_children
        for child_key in visible_children:
            populate_visible_scope_tree(child_key)

    populate_visible_scope_tree(None)

    container_centers: dict[tuple[tuple[str, int], ...], float] = {}

    def assign_container_centers(
        parent_key: tuple[tuple[str, int], ...] | None,
        center_x: float,
    ) -> None:
        child_keys = visible_children_by_parent.get(parent_key, [])
        if not child_keys:
            return
        total_child_count = len(all_children_by_parent.get(parent_key, child_keys))
        if len(child_keys) == 1:
            container_centers[child_keys[0]] = center_x
        else:
            center_distance = _multi_scope_center_distance(
                profile,
                total_child_count,
                parent_depth=0 if parent_key is None else len(parent_key),
            )
            container_centers[child_keys[0]] = center_x - (center_distance / 2)
            container_centers[child_keys[-1]] = center_x + (center_distance / 2)
        for child_key in child_keys:
            assign_container_centers(child_key, container_centers[child_key])

    assign_container_centers(None, 0.0)

    visible_scope_keys = set(container_centers)
    grouped_layer_indices = sorted(
        {
            data["layer_index"]
            for _, data in sorted_nodes
            if data.get("scope_key")
        }
    )

    for scope_key in sorted(visible_scope_keys, key=lambda key: (_scope_depth(key), _scope_sort_key(key))):
        center_x = container_centers[scope_key]
        layer_indexes = sorted(
            layer_index
            for candidate_scope_key, layer_index in scope_nodes_by_layer
            if candidate_scope_key == scope_key
        )
        for layer_index in layer_indexes:
            nodes = scope_nodes_by_layer[(scope_key, layer_index)]
            visible_scope_nodes, hidden_count = select_visible_nodes(nodes)
            y = layer_heights[layer_index]
            positions.update(
                assign_node_positions(
                    visible_scope_nodes,
                    center_x,
                    y,
                    profile.grouped_node_offset,
                )
            )
            visible_nodes.update(visible_scope_nodes)
            if hidden_count > 0:
                placeholder_labels.append((center_x, y, format_hidden_node_label(hidden_count)))

    grouped_content_half_span = max(
        (
            abs(x) + (profile.node_box.width / 2)
            for node, (x, _) in positions.items()
            if node_attrs(graph, node).get("scope_key")
        ),
        default=0.0,
    )
    scope_bandwidths = _multi_scope_bandwidths_by_scope_and_layer(graph)
    scope_required_right = _multi_scope_scope_required_right(
        graph,
        positions,
        visible_nodes,
        scope_bandwidths,
        profile,
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

    group_bounds: list[tuple[float, float, float, float, str]] = []
    scope_bounds_by_key: dict[
        tuple[tuple[str, int], ...],
        tuple[float, float, float, float, str],
    ] = {}
    for scope_key in sorted(visible_scope_keys, key=lambda key: (_scope_depth(key), _scope_sort_key(key))):
        descendant_nodes = [
            node
            for node in visible_nodes
            if _scope_is_prefix(
                node_attrs(graph, node).get("scope_key", ()),
                scope_key,
            )
        ]
        if not descendant_nodes:
            continue
        scope_depth = _scope_depth(scope_key)
        left = min(positions[node][0] - (profile.node_box.width / 2) for node in descendant_nodes)
        right = max(positions[node][0] + (profile.node_box.width / 2) for node in descendant_nodes)
        aggregate_left = _aggregate_indicator_left_extent(
            graph,
            positions,
            descendant_nodes,
            profile,
        )
        if aggregate_left is not None:
            left = min(left, aggregate_left)
        horizontal_padding = _scope_horizontal_padding(profile, scope_depth)
        left -= horizontal_padding
        right += horizontal_padding
        right = max(right, scope_required_right.get(scope_key, right))
        min_y = min(layer_heights[node_attrs(graph, node)["layer_index"]] for node in descendant_nodes)
        max_y = max(layer_heights[node_attrs(graph, node)["layer_index"]] for node in descendant_nodes)
        bottom = (
            min_y
            - profile.node_box.half_height
            - profile.group_vertical_padding
            + ((scope_depth - 1) * 0.72)
        )
        top = max_y + profile.node_box.half_height + profile.group_vertical_padding
        label = _scope_box_label(scope_key)
        bound = (left, bottom, right - left, top - bottom, label)
        group_bounds.append(bound)
        scope_bounds_by_key[scope_key] = bound

    _expand_parent_scope_bounds_for_internal_arrow_lanes(
        scope_bounds_by_key,
        visible_children_by_parent,
        scope_bandwidths,
        profile,
    )
    group_bounds = [scope_bounds_by_key[scope_key] for scope_key in scope_bounds_by_key]

    for parent_key, visible_children in visible_children_by_parent.items():
        total_child_count = len(all_children_by_parent.get(parent_key, visible_children))
        hidden_count = total_child_count - len(visible_children)
        if hidden_count <= 0 or not grouped_layer_indices:
            continue
        if parent_key is None:
            descendant_nodes = [node for node in visible_nodes if node_attrs(graph, node).get("scope_key")]
        else:
            descendant_nodes = [
                node
                for node in visible_nodes
                if _scope_is_prefix(
                    node_attrs(graph, node).get("scope_key", ()),
                    parent_key,
                )
            ]
        if not descendant_nodes:
            continue
        placeholder_x = _hidden_scope_placeholder_x(
            visible_children,
            scope_bounds_by_key,
            container_centers[parent_key] if parent_key is not None else 0.0,
        )
        min_y = min(layer_heights[node_attrs(graph, node)["layer_index"]] for node in descendant_nodes)
        max_y = max(layer_heights[node_attrs(graph, node)["layer_index"]] for node in descendant_nodes)
        placeholder_labels.append(
            (
                placeholder_x,
                ((min_y + max_y) / 2) + (0.26 if parent_key is None else 0.14),
                format_hidden_group_label(hidden_count),
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


def _scope_sort_key(scope_key: tuple[tuple[str, int], ...]) -> tuple[int, ...]:
    return tuple(index for _, index in scope_key)


def _scope_depth(scope_key: tuple[tuple[str, int], ...]) -> int:
    return len(scope_key)


def _scope_is_prefix(
    candidate_scope_key: tuple[tuple[str, int], ...],
    prefix_scope_key: tuple[tuple[str, int], ...],
) -> bool:
    return candidate_scope_key[: len(prefix_scope_key)] == prefix_scope_key


def _aggregate_indicator_left_extent(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    nodes: list[str],
    profile: LayoutProfile,
) -> float | None:
    leftmost_nodes_by_layer: dict[int, str] = {}
    for node in nodes:
        layer_index = node_attrs(graph, node)["layer_index"]
        if (
            layer_index not in leftmost_nodes_by_layer
            or positions[node][0] < positions[leftmost_nodes_by_layer[layer_index]][0]
        ):
            leftmost_nodes_by_layer[layer_index] = node

    left_extent: float | None = None
    for node in leftmost_nodes_by_layer.values():
        attrs = node_attrs(graph, node)
        max_bandwidth = max(
            float(attrs.get("aggregate_bandwidth_up", 0.0)),
            float(attrs.get("aggregate_bandwidth_down", 0.0)),
        )
        if max_bandwidth <= 0:
            continue
        symbol_x = positions[node][0] + profile.node_box.aggregate_x_offset
        label = format_bandwidth(max_bandwidth)
        candidate_left = (
            symbol_x
            - profile.node_box.aggregate_text_offset
            - estimate_text_width(label, profile)
        )
        left_extent = candidate_left if left_extent is None else min(left_extent, candidate_left)
    return left_extent


def _scope_box_label(scope_key: tuple[tuple[str, int], ...]) -> str:
    scope_name, scope_index = scope_key[-1]
    return f"{scope_name}_{scope_index}"


def _hidden_scope_placeholder_x(
    visible_children: list[tuple[tuple[str, int], ...]],
    scope_bounds_by_key: dict[
        tuple[tuple[str, int], ...],
        tuple[float, float, float, float, str],
    ],
    fallback_x: float,
) -> float:
    if len(visible_children) < 2:
        return fallback_x
    left_bound = scope_bounds_by_key.get(visible_children[0])
    right_bound = scope_bounds_by_key.get(visible_children[-1])
    if left_bound is None or right_bound is None:
        return fallback_x
    left_gap_edge = left_bound[0] + left_bound[2]
    right_gap_edge = right_bound[0]
    return (left_gap_edge + right_gap_edge) / 2


def _scope_horizontal_padding(profile: LayoutProfile, scope_depth: int) -> float:
    if scope_depth == 1:
        return profile.group_side_padding * 1.9
    return profile.group_side_padding * 0.95


def _multi_scope_center_distance(
    profile: LayoutProfile,
    total_child_count: int,
    parent_depth: int,
) -> float:
    if total_child_count <= 2:
        base_distance = (2 * profile.grouped_half_span()) + profile.two_group_inner_gap
    else:
        base_distance = (
            (2 * profile.grouped_node_offset)
            + (2 * profile.node_box.width)
            + profile.hidden_group_lane_width
        )

    if parent_depth == 0:
        return base_distance * 3.1
    if parent_depth == 1:
        return base_distance * 1.8
    return base_distance * 1.2


def _multi_scope_bandwidths_by_scope_and_layer(
    graph: nx.Graph,
) -> dict[tuple[tuple[tuple[str, int], ...], int, int], float]:
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

    return bandwidths_by_scope_and_layer


def _multi_scope_scope_required_right(
    graph: nx.Graph,
    positions: dict[str, tuple[float, float]],
    visible_nodes: set[str],
    bandwidths_by_scope_and_layer: dict[tuple[tuple[tuple[str, int], ...], int, int], float],
    profile: LayoutProfile,
) -> dict[tuple[tuple[str, int], ...], float]:
    required_right_by_scope: dict[tuple[tuple[str, int], ...], float] = {}

    for (scope_key, lower_layer_index, upper_layer_index), bandwidth in bandwidths_by_scope_and_layer.items():
        descendant_nodes = [
            node
            for node in visible_nodes
            if _scope_is_prefix(node_attrs(graph, node).get("scope_key", ()), scope_key)
            and node_attrs(graph, node)["layer_index"] in (lower_layer_index, upper_layer_index)
        ]
        if not descendant_nodes:
            continue
        label_width = estimate_text_width(format_bandwidth(bandwidth), profile)
        base_x = max(
            positions[node][0] + (profile.node_box.width / 2)
            for node in descendant_nodes
        ) + 0.18
        required_right = base_x + 0.22 + label_width + 0.45
        existing_required_right = required_right_by_scope.get(scope_key)
        required_right_by_scope[scope_key] = (
            required_right
            if existing_required_right is None
            else max(existing_required_right, required_right)
        )
    return required_right_by_scope


def _expand_parent_scope_bounds_for_internal_arrow_lanes(
    scope_bounds_by_key: dict[
        tuple[tuple[str, int], ...],
        tuple[float, float, float, float, str],
    ],
    visible_children_by_parent: dict[
        tuple[tuple[str, int], ...] | None,
        list[tuple[tuple[str, int], ...]],
    ],
    bandwidths_by_scope_and_layer: dict[tuple[tuple[tuple[str, int], ...], int, int], float],
    profile: LayoutProfile,
) -> None:
    scope_max_label_width: dict[tuple[tuple[str, int], ...], float] = {}
    for (scope_key, _, _), bandwidth in bandwidths_by_scope_and_layer.items():
        scope_max_label_width[scope_key] = max(
            scope_max_label_width.get(scope_key, 0.0),
            estimate_text_width(format_bandwidth(bandwidth), profile),
        )

    for parent_key in sorted(scope_bounds_by_key, key=len, reverse=True):
        visible_children = visible_children_by_parent.get(parent_key, [])
        if not visible_children:
            continue
        child_right = max(
            scope_bounds_by_key[child_key][0] + scope_bounds_by_key[child_key][2]
            for child_key in visible_children
            if child_key in scope_bounds_by_key
        )
        label_width = scope_max_label_width.get(parent_key, 0.0)
        required_parent_right = child_right + 0.85 + 0.22 + label_width + 0.45
        left, bottom, width, height, label = scope_bounds_by_key[parent_key]
        current_right = left + width
        if current_right >= required_parent_right:
            continue
        scope_bounds_by_key[parent_key] = (
            left,
            bottom,
            required_parent_right - left,
            height,
            label,
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


def _select_visible_scope_keys(
    scope_keys: list[tuple[tuple[str, int], ...]],
) -> list[tuple[tuple[str, int], ...]]:
    if len(scope_keys) <= 2:
        return scope_keys
    return [scope_keys[0], scope_keys[-1]]


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
