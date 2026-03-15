import importlib
from pathlib import Path
from types import SimpleNamespace

import matplotlib.image as mpimg
import networkx as nx

import topology_generator.render_environment as render_environment
from topology_generator.topology_generator import generate_topology
from topology_generator.render_drawing import get_fanout_annotation
from topology_generator.render_environment import ensure_matplotlib_environment
from topology_generator.render_formatting import (
    LINK_COLOR_PALETTE,
    format_bandwidth,
    format_fanout_label,
    format_group_label,
    format_hidden_group_label,
    format_hidden_node_label,
    format_node_name,
    get_bandwidth_colors,
)
from topology_generator.render_layout import (
    build_layout_profile,
    build_render_summary,
    calculate_group_layer_bandwidth,
    calculate_layout,
    calculate_layer_bandwidth,
    calculate_plot_limits,
    compute_annotation_columns,
    compute_group_bandwidth_arrow_x,
    compute_group_lane_layout,
    compute_node_box_geometry,
    get_group_centers,
    get_leftmost_visible_nodes_by_layer,
    select_visible_group_indices,
)
from topology_generator.rendering import visualize_topology


def test_format_bandwidth():
    assert format_bandwidth(400) == "400 GB/s"
    assert format_bandwidth(3200) == "3.2 TB/s"


def test_format_fanout_label():
    assert format_fanout_label(16, 6400) == "16 cables"


def test_format_labels():
    assert format_node_name("GPU server") == "GPU server"
    assert format_node_name("Extremely Long Layer Name") == "Extremely..."
    assert format_hidden_node_label(3) == "..."
    assert format_hidden_group_label(62) == "..."
    assert format_group_label("pod", 4) == "pod_4"


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


def test_node_box_geometry_fits_text_stack():
    geometry = compute_node_box_geometry()

    assert geometry.name_y_offset < geometry.half_height
    assert abs(geometry.ports_label_y_offset) < geometry.half_height
    assert geometry.width > 1.9
    assert geometry.height > 1.2


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


def test_calculate_layer_bandwidth_respects_requested_node_subsets():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0)
    graph.add_node("compute_2", layer_index=0)
    graph.add_node("leaf_1", layer_index=1)
    graph.add_node("leaf_2", layer_index=1)
    graph.add_edge("compute_1", "leaf_1", num_cables=1, cable_bandwidth_gb=100)
    graph.add_edge("compute_2", "leaf_2", num_cables=1, cable_bandwidth_gb=200)

    assert calculate_layer_bandwidth(graph, ["compute_1"], ["leaf_1"]) == 100


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


def test_two_pod_layout_uses_tighter_middle_gap(two_pod_dense_config):
    layout = calculate_layout(generate_topology(two_pod_dense_config))
    left_bound, right_bound = sorted(layout.group_bounds, key=lambda bound: bound[0])

    inner_gap = right_bound[0] - (left_bound[0] + left_bound[2])
    assert 6.0 <= inner_gap <= 13.0
    assert not any(text == "...(0 more)..." for _, _, text in layout.placeholder_labels)


def test_multi_pod_layout_adds_centered_hidden_pod_placeholder(multi_pod_dense_config):
    layout = calculate_layout(generate_topology(multi_pod_dense_config))
    left_bound, right_bound = sorted(layout.group_bounds, key=lambda bound: bound[0])

    inner_gap = right_bound[0] - (left_bound[0] + left_bound[2])
    assert inner_gap >= 2.3
    assert any(text == "..." and x == 0.0 for x, _, text in layout.placeholder_labels)
    assert any(text == "..." for _, _, text in layout.placeholder_labels)


def test_hidden_global_layers_span_visible_diagram_width(multi_pod_dense_config):
    graph = generate_topology(multi_pod_dense_config)
    layout = calculate_layout(graph)

    hidden_global_nodes = [
        node
        for node in layout.visible_nodes
        if graph.nodes[node].get("group_index") is None
        and graph.nodes[node]["layer_name"] == "spine"
    ]
    hidden_global_xs = [layout.positions[node][0] for node in hidden_global_nodes]

    assert len(hidden_global_xs) == 2
    assert max(abs(x) for x in hidden_global_xs) > (layout.profile.global_node_offset + 2.0)


def test_layout_keeps_hidden_node_placeholders_centered_in_pod(two_pod_dense_config):
    graph = generate_topology(two_pod_dense_config)
    layout = calculate_layout(graph)
    compute_placeholders = [
        x
        for x, y, text in layout.placeholder_labels
        if text == "..." and y == 0.0
    ]

    assert compute_placeholders
    for group_index in (1, 2):
        visible_group_nodes = [
            node
            for node, (x, y) in layout.positions.items()
            if graph.nodes[node].get("group_index") == group_index
            and graph.nodes[node]["layer_index"] == 0
            and y == 0.0
        ]
        visible_xs = sorted(layout.positions[node][0] for node in visible_group_nodes)
        midpoint = sum(visible_xs) / len(visible_xs)
        assert any(abs(midpoint - x) < 1e-9 for x in compute_placeholders)


def test_annotation_column_is_inside_tight_plot_limits(multi_pod_dense_config):
    layout = calculate_layout(generate_topology(multi_pod_dense_config))
    x_limits, _ = calculate_plot_limits(layout)

    assert layout.layer_bandwidth_x < x_limits[1]
    assert layout.layer_bandwidth_x + layout.profile.right_annotation_extent <= x_limits[1]


def test_group_bandwidth_arrow_stays_inside_pod_and_near_rightmost_node(
    multi_pod_dense_config,
):
    graph = generate_topology(multi_pod_dense_config)
    layout = calculate_layout(graph)
    rightmost_bound = max(layout.group_bounds, key=lambda bound: bound[0] + bound[2])
    group_index = int(rightmost_bound[4].rsplit("_", 1)[1])

    arrow_x = compute_group_bandwidth_arrow_x(
        graph,
        layout.positions,
        layout.profile,
        group_index,
    )
    rightmost_node_x = max(
        x + (layout.profile.node_box.width / 2)
        for node, (x, _) in layout.positions.items()
        if graph.nodes[node].get("group_index") == group_index
    )
    pod_right_edge = rightmost_bound[0] + rightmost_bound[2]

    assert rightmost_node_x < arrow_x < pod_right_edge
    assert (arrow_x - rightmost_node_x) <= 0.45
    assert (pod_right_edge - arrow_x) >= 0.45


def test_compute_annotation_column_tracks_content_width(two_pod_dense_config):
    layout = calculate_layout(generate_topology(two_pod_dense_config))
    annotation_x = compute_annotation_columns(
        layout.positions,
        layout.group_bounds,
        layout.profile,
    )

    assert annotation_x == layout.layer_bandwidth_x


def test_calculate_plot_limits_expand_just_past_content(two_pod_dense_config):
    layout = calculate_layout(generate_topology(two_pod_dense_config))
    x_limits, y_limits = calculate_plot_limits(layout)

    assert x_limits[0] < min(x for x, _ in layout.positions.values())
    assert x_limits[1] > layout.layer_bandwidth_x
    assert y_limits[0] < min(y for _, y in layout.positions.values())
    assert y_limits[1] > max(y for _, y in layout.positions.values())


def test_visualize_topology_writes_output(tmp_path, two_pod_dense_config):
    visualize_topology(generate_topology(two_pod_dense_config), str(tmp_path))

    assert (tmp_path / "topology.png").exists()


def test_visual_density_for_two_pod_example(tmp_path, two_pod_dense_config):
    image_path = render_example(tmp_path / "two_pod", two_pod_dense_config)
    width_fraction, height_fraction, margins = image_content_metrics(image_path)

    assert width_fraction > 0.5
    assert height_fraction > 0.55
    assert margins["right"] < 0.2
    assert margins["top"] < 0.18


def test_visual_density_for_multi_pod_example(tmp_path, multi_pod_dense_config):
    image_path = render_example(tmp_path / "multi_pod", multi_pod_dense_config)
    width_fraction, height_fraction, margins = image_content_metrics(image_path)

    assert width_fraction > 0.52
    assert height_fraction > 0.58
    assert margins["right"] < 0.2
    assert margins["top"] < 0.18


def test_ensure_matplotlib_environment_sets_safe_fallbacks(tmp_path, monkeypatch):
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("MPLBACKEND", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(render_environment, "_directory_is_writable", lambda path: False)
    monkeypatch.setattr(render_environment.tempfile, "gettempdir", lambda: str(tmp_path))

    ensure_matplotlib_environment()

    assert render_environment.os.environ["MPLCONFIGDIR"] == str(
        tmp_path / "topology_generator_matplotlib"
    )
    assert render_environment.os.environ["MPLBACKEND"] == "Agg"


def test_render_environment_import_has_no_side_effects(monkeypatch):
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("MPLBACKEND", raising=False)

    importlib.reload(render_environment)

    assert "MPLCONFIGDIR" not in render_environment.os.environ
    assert "MPLBACKEND" not in render_environment.os.environ


def test_load_matplotlib_is_lazy_and_cached(monkeypatch):
    calls: list[str] = []

    def fake_import_module(name: str):
        calls.append(name)
        if name == "matplotlib.pyplot":
            return "plt-module"
        if name == "matplotlib.lines":
            return SimpleNamespace(Line2D="line2d")
        if name == "matplotlib.patches":
            return SimpleNamespace(Patch="patch", Arc="arc", Rectangle="rectangle")
        raise AssertionError(f"Unexpected import: {name}")

    render_environment.load_matplotlib.cache_clear()
    monkeypatch.setattr(
        render_environment,
        "ensure_matplotlib_environment",
        lambda: calls.append("ensure"),
    )
    monkeypatch.setattr(
        render_environment.importlib,
        "import_module",
        fake_import_module,
    )

    first = render_environment.load_matplotlib()
    second = render_environment.load_matplotlib()

    assert calls == [
        "ensure",
        "matplotlib.pyplot",
        "matplotlib.lines",
        "matplotlib.patches",
    ]
    assert first is second
    assert first.plt == "plt-module"
    assert first.Line2D == "line2d"
    assert first.Patch == "patch"
    assert first.Arc == "arc"
    assert first.Rectangle == "rectangle"


def test_build_render_summary_tracks_layer_and_group_bandwidth(two_pod_dense_config):
    summary = build_render_summary(generate_topology(two_pod_dense_config))

    assert summary.layer_bandwidths[(0, 1)] > 0
    assert summary.group_layer_bandwidths[(1, 0, 1)] > 0


def test_visualize_topology_writes_per_fabric_outputs(tmp_path, multi_fabric_config):
    visualize_topology(generate_topology(multi_fabric_config), str(tmp_path))

    assert (tmp_path / "topology_backend.png").exists()
    assert (tmp_path / "topology_frontend.png").exists()
    assert (tmp_path / "topology_oob.png").exists()


def test_visualize_topology_normalizes_fabric_name_in_output_filename(tmp_path):
    config = {
        "groupings": [
            {
                "name": "pod",
                "members_per_group": 1,
            }
        ],
        "gpu_nodes": {
            "total_nodes": 1,
            "fabric_port_layouts": {
                "front/end": {
                    "base_lane_bandwidth_gb": 100,
                    "total_lane_units": 1,
                    "supported_port_modes": [
                        {
                            "port_bandwidth_gb": 100,
                            "lane_units": 1,
                        }
                    ],
                }
            },
        },
        "fabrics": [
            {
                "name": "front/end",
                "grouping": "pod",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "group",
                        "nodes_per_group": 1,
                        "port_layout": {
                            "base_lane_bandwidth_gb": 100,
                            "total_lane_units": 1,
                            "supported_port_modes": [
                                {
                                    "port_bandwidth_gb": 100,
                                    "lane_units": 1,
                                }
                            ],
                        },
                    }
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "leaf",
                        "policy": "within_group_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    }
                ],
            }
        ],
    }

    visualize_topology(generate_topology(config), str(tmp_path))

    assert (tmp_path / "topology_front_end.png").exists()


def render_example(output_dir: Path, config: dict[str, object]) -> Path:
    output_dir.mkdir(parents=True, exist_ok=True)
    visualize_topology(generate_topology(config), str(output_dir))
    return output_dir / "topology.png"


def image_content_metrics(image_path: Path) -> tuple[float, float, dict[str, float]]:
    image = mpimg.imread(image_path)
    if image.shape[-1] == 4:
        rgb = image[..., :3]
    else:
        rgb = image
    mask = rgb.mean(axis=2) < 0.985
    ys, xs = mask.nonzero()
    assert len(xs) > 0
    assert len(ys) > 0

    min_x = xs.min()
    max_x = xs.max()
    min_y = ys.min()
    max_y = ys.max()
    width = mask.shape[1]
    height = mask.shape[0]
    width_fraction = (max_x - min_x + 1) / width
    height_fraction = (max_y - min_y + 1) / height
    margins = {
        "left": min_x / width,
        "right": (width - max_x - 1) / width,
        "top": min_y / height,
        "bottom": (height - max_y - 1) / height,
    }
    return width_fraction, height_fraction, margins
