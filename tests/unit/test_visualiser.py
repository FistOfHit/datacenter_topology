import networkx as nx

from topology_generator.visualiser import (
    LINK_COLOR_PALETTE,
    calculate_node_positions,
    calculate_plot_limits,
    ensure_matplotlib_environment,
    format_bandwidth,
    format_fanout_label,
    format_hidden_node_label,
    format_node_name,
    get_bandwidth_colors,
    get_fanout_annotation,
    get_leftmost_visible_nodes_by_layer,
    split_node_label,
    visualize_topology,
)
import topology_generator.visualiser as visualiser


def test_format_bandwidth():
    assert format_bandwidth(400) == "400 GB/s"
    assert format_bandwidth(3200) == "3.2 TB/s"


def test_format_fanout_label():
    assert format_fanout_label(16, 400) == "16 x 400 GB/s"


def test_node_name_display_limit():
    assert format_node_name("GPU server") == "gpu_server"
    assert format_node_name("Very long server name") == "very_long_"
    assert split_node_label("Very long server name_12") == ("very_long_", "12")


def test_hidden_node_label_is_fixed_width():
    assert format_hidden_node_label(3) == "...(   3 more)..."
    assert format_hidden_node_label(1234) == "...(1234 more)..."
    assert len(format_hidden_node_label(3)) == len(format_hidden_node_label(1234))


def test_condensed_node_positions_are_consistent():
    positions = calculate_node_positions(1, ["a", "b", "c"])
    assert positions["a"] == (-2.0, 1.0)
    assert positions["c"] == (2.0, 1.0)


def test_small_layers_remain_centered():
    one_node = calculate_node_positions(0, ["a"])
    two_nodes = calculate_node_positions(0, ["a", "b"])
    assert one_node["a"] == (0.0, 0.0)
    assert two_nodes["a"] == (-0.6, 0.0)
    assert two_nodes["b"] == (0.6, 0.0)


def test_get_fanout_annotation_uses_total_cable_count():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0)
    graph.add_node("aggregation_1", layer_index=1)
    graph.add_node("aggregation_2", layer_index=1)
    graph.add_node("aggregation_3", layer_index=1)
    graph.add_edge("compute_1", "aggregation_1", num_cables=4, cable_bandwidth_gb=400)
    graph.add_edge("compute_1", "aggregation_2", num_cables=4, cable_bandwidth_gb=400)
    graph.add_edge("compute_1", "aggregation_3", num_cables=4, cable_bandwidth_gb=400)

    positions = {
        "compute_1": (0.0, 0.0),
        "aggregation_1": (-2.0, 1.0),
        "aggregation_2": (0.0, 1.0),
        "aggregation_3": (2.0, 1.0),
    }
    visible_nodes = {"compute_1", "aggregation_1", "aggregation_3"}

    annotation = get_fanout_annotation(
        graph,
        positions,
        visible_nodes,
        "compute_1",
        "up",
    )

    assert annotation is not None
    assert annotation["label"] == "12 x 400 GB/s"
    assert annotation["label_pos"][1] > annotation["center"][1]


def test_get_fanout_annotation_requires_visible_fan():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0)
    graph.add_node("aggregation_1", layer_index=1)
    graph.add_edge("compute_1", "aggregation_1", num_cables=4, cable_bandwidth_gb=400)

    annotation = get_fanout_annotation(
        graph,
        {"compute_1": (0.0, 0.0), "aggregation_1": (-2.0, 1.0)},
        {"compute_1", "aggregation_1"},
        "compute_1",
        "up",
    )

    assert annotation is None


def test_downward_fanout_label_is_centered_below_arc():
    graph = nx.Graph()
    graph.add_node("aggregation_1", layer_index=1)
    graph.add_node("compute_1", layer_index=0)
    graph.add_node("compute_2", layer_index=0)
    graph.add_edge("aggregation_1", "compute_1", num_cables=4, cable_bandwidth_gb=400)
    graph.add_edge("aggregation_1", "compute_2", num_cables=4, cable_bandwidth_gb=400)

    annotation = get_fanout_annotation(
        graph,
        {
            "aggregation_1": (-2.0, 1.0),
            "compute_1": (-2.0, 0.0),
            "compute_2": (2.0, 0.0),
        },
        {"aggregation_1", "compute_1", "compute_2"},
        "aggregation_1",
        "down",
    )

    assert annotation is not None
    assert annotation["label_pos"][1] < annotation["center"][1]


def test_leftmost_visible_node_is_used_for_each_layer():
    graph = nx.Graph()
    graph.add_node("compute_1", layer_index=0)
    graph.add_node("compute_32", layer_index=0)
    graph.add_node("aggregation_1", layer_index=1)
    graph.add_node("aggregation_8", layer_index=1)

    positions = {
        "compute_1": (-2.0, 0.0),
        "compute_32": (2.0, 0.0),
        "aggregation_1": (-2.0, 1.0),
        "aggregation_8": (2.0, 1.0),
    }
    visible_nodes = set(positions)

    assert get_leftmost_visible_nodes_by_layer(graph, positions, visible_nodes) == {
        0: "compute_1",
        1: "aggregation_1",
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


def test_calculate_plot_limits_expands_to_include_top_layer():
    positions = {
        "compute_1": (-2.0, 0.0),
        "aggregation_1": (-2.0, 1.0),
        "fabric_1": (-2.0, 2.0),
        "core_1": (2.0, 3.0),
    }

    x_limits, y_limits = calculate_plot_limits(positions, set(positions))

    assert x_limits[0] < -2.0
    assert x_limits[1] > 2.0
    assert y_limits[1] > 3.0


def test_visualize_topology_writes_output(tmp_path, sample_config):
    from topology_generator.topology_generator import generate_topology

    visualize_topology(generate_topology(sample_config), str(tmp_path))

    assert (tmp_path / "topology.png").exists()


def test_ensure_matplotlib_environment_sets_safe_fallbacks(tmp_path, monkeypatch):
    monkeypatch.delenv("MPLCONFIGDIR", raising=False)
    monkeypatch.delenv("MPLBACKEND", raising=False)
    monkeypatch.delenv("DISPLAY", raising=False)
    monkeypatch.delenv("WAYLAND_DISPLAY", raising=False)
    monkeypatch.setattr(visualiser, "_directory_is_writable", lambda path: False)
    monkeypatch.setattr(visualiser.tempfile, "gettempdir", lambda: str(tmp_path))

    ensure_matplotlib_environment()

    assert visualiser.os.environ["MPLCONFIGDIR"] == str(
        tmp_path / "topology_generator_matplotlib"
    )
    assert visualiser.os.environ["MPLBACKEND"] == "Agg"
