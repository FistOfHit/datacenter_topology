from pathlib import Path

import networkx as nx

from topology_generator.render_drawing import (
    AGGREGATE_BANDWIDTH_LEGEND_LABEL,
    AGGREGATE_BANDWIDTH_LEGEND_MARKER,
    TITLE_FONT_SIZE,
    _visible_port_pool_lines,
    build_legend_elements,
    get_fanout_annotation,
)
from topology_generator.render_formatting import (
    LINK_COLOR_PALETTE,
    format_additional_port_pools,
    format_bandwidth,
    format_fanout_label,
    format_group_label,
    format_hidden_group_label,
    format_hidden_node_label,
    format_node_name,
    format_port_pool_summary,
    get_bandwidth_colors,
)
from topology_generator.render_layout import (
    build_layout_profile,
    calculate_group_layer_bandwidth,
    calculate_layer_bandwidth,
    calculate_layout,
    compute_group_lane_layout,
    compute_node_box_geometry,
    get_group_centers,
    get_leftmost_visible_nodes_by_layer,
    select_visible_group_indices,
)
from topology_generator.rendering import build_topology_title, visualize_topology
from topology_generator.topology_generator import generate_topology


def _pool(
    name: str,
    base_lane_bandwidth_gb: float,
    total_lane_units: int,
    supported_modes: list[tuple[float, int]],
) -> dict[str, object]:
    return {
        "name": name,
        "base_lane_bandwidth_gb": base_lane_bandwidth_gb,
        "total_lane_units": total_lane_units,
        "supported_port_modes": [
            {
                "port_bandwidth_gb": port_bandwidth_gb,
                "lane_units": lane_units,
            }
            for port_bandwidth_gb, lane_units in supported_modes
        ],
    }


def _mixed_scope_oob_config(total_nodes: int = 8) -> dict[str, object]:
    return {
        "groupings": [
            {"name": "pod", "members_per_group": 4},
            {"name": "rack", "members_per_group": 2},
        ],
        "gpu_nodes": {
            "total_nodes": total_nodes,
            "fabric_port_pools": {
                "oob": [_pool("fabric", 100, 1, [(100, 1)])],
            },
        },
        "fabrics": [
            {
                "name": "oob",
                "gpu_nodes_placement": "rack",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "rack",
                        "nodes_per_group": 1,
                        "port_pools": [_pool("fabric", 100, 4, [(100, 1), (200, 2)])],
                    },
                    {
                        "name": "spine",
                        "placement": "pod",
                        "nodes_per_group": 1,
                        "port_pools": [_pool("fabric", 100, 4, [(200, 2)])],
                    },
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "leaf",
                        "policy": "same_scope_full_mesh",
                        "port_pool": "fabric",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    },
                    {
                        "from": "leaf",
                        "to": "spine",
                        "policy": "to_ancestor_full_mesh",
                        "port_pool": "fabric",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 200,
                    },
                ],
            }
        ],
    }


def test_format_helpers():
    assert format_bandwidth(400) == "400 GB/s"
    assert format_bandwidth(3200) == "3.2 TB/s"
    assert format_fanout_label(16, 6400) == "16 cables"
    assert format_node_name("GPU server") == "GPU server"
    assert format_node_name("Extremely Long Layer Name") == "Extremely..."
    assert format_hidden_node_label(3) == "..."
    assert format_hidden_group_label(62) == "..."
    assert format_group_label("pod", 4) == "pod_4"
    assert format_port_pool_summary(
        {
            "name": "fabric",
            "used_lane_units": 3,
            "total_lane_units": 8,
            "port_offset": 0,
            "base_lane_bandwidth_gb": 400,
            "supported_port_bandwidths_gb": (400.0,),
        }
    ) == "fabric: 3/8"
    assert format_additional_port_pools(2) == "+2 more pools"


def test_select_visible_group_indices_and_centers():
    profile = build_layout_profile(2)

    assert select_visible_group_indices([1, 2]) == [1, 2]
    assert select_visible_group_indices([1, 2, 3, 4]) == [1, 4]
    assert get_group_centers([2], profile, 1) == {2: 0.0}

    two_group_centers = get_group_centers([1, 2], profile, 2)
    assert two_group_centers[1] < 0 < two_group_centers[2]
    assert abs(two_group_centers[1]) == abs(two_group_centers[2])

    multi_profile = build_layout_profile(6)
    multi_group_centers = get_group_centers([1, 6], multi_profile, 6)
    assert multi_group_centers[1] > two_group_centers[1]
    assert multi_group_centers[6] < two_group_centers[2]
    assert abs(multi_group_centers[1]) == abs(multi_group_centers[6])


def test_compute_group_lane_layout_reserves_hidden_group_middle_lane():
    profile = build_layout_profile(6)
    centers, hidden_placeholder_x = compute_group_lane_layout(6, [1, 6], profile)

    assert centers[1] < 0
    assert centers[6] > 0
    assert hidden_placeholder_x == 0.0


def test_node_box_geometry_fits_pool_summary_stack():
    geometry = compute_node_box_geometry()

    assert geometry.name_y_offset < geometry.half_height
    assert abs(geometry.ports_label_y_offset) < geometry.half_height
    assert geometry.width > 1.9
    assert geometry.height > 1.4
    assert geometry.aggregate_x_offset == -2.35
    assert geometry.aggregate_left_extent == 3.35


def test_build_topology_title_formats_single_and_multi_fabric_titles():
    assert build_topology_title() == "Network Topology"
    assert build_topology_title("backend") == "backend topology"


def test_build_legend_elements_includes_aggregate_bandwidth_entry(two_pod_dense_config):
    legend_elements = build_legend_elements(generate_topology(two_pod_dense_config))
    labels = [legend_handle.get_label() for legend_handle in legend_elements]
    aggregate_legend_handle = next(
        legend_handle
        for legend_handle in legend_elements
        if legend_handle.get_label() == AGGREGATE_BANDWIDTH_LEGEND_LABEL
    )

    assert "Cable count" in labels
    assert AGGREGATE_BANDWIDTH_LEGEND_LABEL in labels
    assert aggregate_legend_handle.get_marker() == AGGREGATE_BANDWIDTH_LEGEND_MARKER
    assert TITLE_FONT_SIZE == 16


def test_get_fanout_annotation_uses_total_cable_count():
    graph = nx.Graph()
    graph.add_node("pod_1_compute_1", layer_index=0)
    graph.add_node("pod_1_leaf_1", layer_index=1)
    graph.add_node("pod_1_leaf_2", layer_index=1)
    graph.add_node("pod_1_leaf_3", layer_index=1)
    graph.add_edge("pod_1_compute_1", "pod_1_leaf_1", num_cables=4, cable_bandwidth_gb=400)
    graph.add_edge("pod_1_compute_1", "pod_1_leaf_2", num_cables=4, cable_bandwidth_gb=400)
    graph.add_edge("pod_1_compute_1", "pod_1_leaf_3", num_cables=4, cable_bandwidth_gb=400)

    positions = {
        "pod_1_compute_1": (0.0, 0.0),
        "pod_1_leaf_1": (-2.0, 1.55),
        "pod_1_leaf_2": (0.0, 1.55),
        "pod_1_leaf_3": (2.0, 1.55),
    }
    visible_nodes = {"pod_1_compute_1", "pod_1_leaf_1", "pod_1_leaf_3"}

    annotation = get_fanout_annotation(
        graph,
        positions,
        visible_nodes,
        "pod_1_compute_1",
        "up",
        compute_node_box_geometry(),
    )

    assert annotation is not None
    assert annotation["label"] == "12 cables"
    assert annotation["label_pos"][1] > annotation["center"][1]


def test_leftmost_visible_node_is_used_for_each_layer():
    graph = nx.Graph()
    graph.add_node("pod_1_compute_1", layer_index=0)
    graph.add_node("pod_6_compute_32", layer_index=0)
    graph.add_node("spine_1", layer_index=1)
    graph.add_node("spine_8", layer_index=1)

    positions = {
        "pod_1_compute_1": (-3.0, 0.0),
        "pod_6_compute_32": (3.0, 0.0),
        "spine_1": (-0.9, 1.55),
        "spine_8": (0.9, 1.55),
    }
    visible_nodes = set(positions)

    assert get_leftmost_visible_nodes_by_layer(graph, positions, visible_nodes) == {
        0: "pod_1_compute_1",
        1: "spine_1",
    }


def test_get_bandwidth_colors_is_deterministic():
    graph = nx.Graph()
    graph.add_node("node1", layer_index=0)
    graph.add_node("node2", layer_index=1)
    graph.add_node("node3", layer_index=2)
    graph.add_edge("node1", "node2", cable_bandwidth_gb=400)
    graph.add_edge("node2", "node3", cable_bandwidth_gb=800)

    assert get_bandwidth_colors(graph) == {
        400: "black",
        800: LINK_COLOR_PALETTE[0],
    }


def test_calculate_layer_bandwidth_sums_all_links_between_adjacent_layers():
    graph = nx.Graph()
    graph.add_node("pod_1_compute_1", layer_index=0)
    graph.add_node("pod_1_compute_2", layer_index=0)
    graph.add_node("pod_1_leaf_1", layer_index=1)
    graph.add_node("spine_1", layer_index=2)
    graph.add_edge("pod_1_compute_1", "pod_1_leaf_1", num_cables=2, cable_bandwidth_gb=400)
    graph.add_edge("pod_1_compute_2", "pod_1_leaf_1", num_cables=1, cable_bandwidth_gb=400)
    graph.add_edge("pod_1_leaf_1", "spine_1", num_cables=1, cable_bandwidth_gb=800)

    assert (
        calculate_layer_bandwidth(
            graph,
            ["pod_1_compute_1", "pod_1_compute_2"],
            ["pod_1_leaf_1"],
        )
        == 1200
    )


def test_calculate_group_layer_bandwidth_counts_only_matching_group_pairs():
    graph = nx.Graph()
    graph.add_node("pod_1_leaf_1", layer_index=1, group_index=1)
    graph.add_node("pod_1_spine_1", layer_index=2, group_index=1)
    graph.add_node("pod_2_leaf_1", layer_index=1, group_index=2)
    graph.add_node("pod_2_spine_1", layer_index=2, group_index=2)
    graph.add_node("core_1", layer_index=2, group_index=None)
    graph.add_edge("pod_1_leaf_1", "pod_1_spine_1", num_cables=2, cable_bandwidth_gb=800)
    graph.add_edge("pod_2_leaf_1", "pod_2_spine_1", num_cables=1, cable_bandwidth_gb=800)
    graph.add_edge("pod_1_leaf_1", "core_1", num_cables=1, cable_bandwidth_gb=800)

    assert calculate_group_layer_bandwidth(graph, 1, 2, 1) == 1600
    assert calculate_group_layer_bandwidth(graph, 1, 2, 2) == 800


def test_visible_port_pool_lines_handle_one_two_and_many_pools():
    one_pool = {
        "port_pools": (
            {
                "name": "fabric",
                "used_lane_units": 3,
                "total_lane_units": 8,
                "port_offset": 0,
                "base_lane_bandwidth_gb": 400,
                "supported_port_bandwidths_gb": (400.0,),
            },
        )
    }
    two_pools = {
        "port_pools": (
            {
                "name": "fabric",
                "used_lane_units": 3,
                "total_lane_units": 8,
                "port_offset": 0,
                "base_lane_bandwidth_gb": 400,
                "supported_port_bandwidths_gb": (400.0,),
            },
            {
                "name": "mgmt",
                "used_lane_units": 1,
                "total_lane_units": 4,
                "port_offset": 8,
                "base_lane_bandwidth_gb": 100,
                "supported_port_bandwidths_gb": (100.0,),
            },
        )
    }
    many_pools = {
        "port_pools": (
            two_pools["port_pools"][0],
            two_pools["port_pools"][1],
            {
                "name": "storage",
                "used_lane_units": 2,
                "total_lane_units": 2,
                "port_offset": 12,
                "base_lane_bandwidth_gb": 200,
                "supported_port_bandwidths_gb": (200.0,),
            },
        )
    }

    assert _visible_port_pool_lines(one_pool) == ["fabric: 3/8"]
    assert _visible_port_pool_lines(two_pools) == ["fabric: 3/8", "mgmt: 1/4"]
    assert _visible_port_pool_lines(many_pools) == ["fabric: 3/8", "+2 more pools"]


def test_multi_pod_layout_adds_centered_hidden_pod_placeholder(multi_pod_dense_config):
    layout = calculate_layout(generate_topology(multi_pod_dense_config))
    left_bound, right_bound = sorted(layout.group_bounds, key=lambda bound: bound[0])

    inner_gap = right_bound[0] - (left_bound[0] + left_bound[2])
    assert inner_gap >= 2.3
    assert any(text == "..." and x == 0.0 for x, _, text in layout.placeholder_labels)


def test_visualize_topology_writes_single_and_multi_fabric_outputs(
    tmp_path: Path,
    sample_config,
):
    graph = generate_topology(sample_config)

    visualize_topology(graph, tmp_path)

    assert (tmp_path / "topology.png").exists()


def test_visualize_topology_writes_multi_scope_outputs(tmp_path: Path):
    graph = generate_topology(_mixed_scope_oob_config())

    visualize_topology(graph, tmp_path)

    assert (tmp_path / "topology_oob.png").exists()
