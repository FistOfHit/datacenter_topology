from topology_generator.config_types import TopologyConfig
from topology_generator.topology_generator import (
    ContiguousLaneAllocator,
    build_fabric_output_name,
    generate_topology,
    get_fabric_view,
    is_multi_fabric_graph,
)


def test_generate_topology_builds_expected_grouped_graph(sample_config):
    graph = generate_topology(sample_config)

    assert sorted(graph.nodes) == [
        "pod_1_compute_1",
        "pod_1_compute_2",
        "pod_1_leaf_1",
        "pod_2_compute_1",
        "pod_2_compute_2",
        "pod_2_leaf_1",
        "spine_1",
        "spine_2",
    ]
    assert sorted(graph.edges()) == [
        ("pod_1_compute_1", "pod_1_leaf_1"),
        ("pod_1_compute_2", "pod_1_leaf_1"),
        ("pod_1_leaf_1", "spine_1"),
        ("pod_1_leaf_1", "spine_2"),
        ("pod_2_compute_1", "pod_2_leaf_1"),
        ("pod_2_compute_2", "pod_2_leaf_1"),
        ("pod_2_leaf_1", "spine_1"),
        ("pod_2_leaf_1", "spine_2"),
    ]

    assert graph.edges["pod_1_compute_1", "pod_1_leaf_1"]["source_ports"] == [1]
    assert graph.edges["pod_1_compute_1", "pod_1_leaf_1"]["target_ports"] == [1]
    assert graph.edges["pod_1_leaf_1", "spine_1"]["source_ports"] == [3]
    assert graph.edges["pod_1_leaf_1", "spine_1"]["target_ports"] == [1]
    assert graph.edges["pod_2_leaf_1", "spine_2"]["source_ports"] == [4]
    assert graph.edges["pod_2_leaf_1", "spine_2"]["target_ports"] == [2]

    assert graph.nodes["pod_1_compute_1"]["used_bandwidth_gb"] == 100
    assert graph.nodes["pod_1_compute_1"]["used_lane_units"] == 1
    assert graph.nodes["pod_1_leaf_1"]["used_bandwidth_gb"] == 400
    assert graph.nodes["pod_1_leaf_1"]["used_lane_units"] == 4
    assert graph.nodes["spine_1"]["used_bandwidth_gb"] == 200
    assert graph.nodes["spine_1"]["used_lane_units"] == 2


def test_generate_topology_accepts_validated_config(sample_config):
    config = TopologyConfig.from_mapping(sample_config)

    graph = generate_topology(config)

    assert graph.number_of_nodes() == 8
    assert graph.number_of_edges() == 8


def test_generate_topology_supports_global_only_links(sample_global_config):
    graph = generate_topology(sample_global_config)

    assert sorted(graph.nodes) == ["core_1", "spine_1", "spine_2"]
    assert sorted(graph.edges()) == [("spine_1", "core_1"), ("spine_2", "core_1")]


def test_generate_topology_allocates_contiguous_lane_units_for_mixed_speed_links(
    mixed_speed_config,
):
    graph = generate_topology(mixed_speed_config)

    assert graph.edges["pod_1_leaf_switch_1", "spine_1"]["source_ports"] == [3]
    assert graph.edges["pod_1_leaf_switch_1", "spine_1"]["target_ports"] == [1]
    assert graph.edges["pod_1_leaf_switch_1", "spine_1"]["source_lane_units_per_cable"] == 2
    assert graph.edges["pod_1_leaf_switch_1", "spine_1"]["target_lane_units_per_cable"] == 2
    assert graph.nodes["pod_1_leaf_switch_1"]["supported_port_bandwidths_gb"] == (
        400.0,
        800.0,
    )


def test_generate_topology_merges_gpu_nodes_across_fabrics(multi_fabric_config):
    graph = generate_topology(multi_fabric_config)

    assert is_multi_fabric_graph(graph) is True
    assert graph.nodes["gpu_nodes_1"]["is_shared_gpu_node"] is True
    assert set(graph.nodes["gpu_nodes_1"]["fabric_metrics"]) == {
        "backend",
        "frontend",
        "oob",
    }
    assert "backend__pod_1_leaf_1" in graph.nodes
    assert "frontend__pod_1_tor_1" in graph.nodes
    assert "oob__mgmt_1" in graph.nodes


def test_get_fabric_view_flattens_shared_gpu_node_metrics(multi_fabric_config):
    graph = generate_topology(multi_fabric_config)

    backend_view = get_fabric_view(graph, "backend")

    assert backend_view.nodes["gpu_nodes_1"]["used_lane_units"] == 1
    assert backend_view.nodes["gpu_nodes_1"]["total_lane_units"] == 1
    assert backend_view.nodes["gpu_nodes_1"]["group_label"] == "pod_1"
    assert {frozenset(edge) for edge in backend_view.edges()} == {
        frozenset(("backend__pod_1_leaf_1", "backend__spine_1")),
        frozenset(("gpu_nodes_1", "backend__pod_1_leaf_1")),
        frozenset(("gpu_nodes_2", "backend__pod_1_leaf_1")),
    }


def test_get_fabric_view_rejects_unknown_fabric(multi_fabric_config):
    graph = generate_topology(multi_fabric_config)

    try:
        get_fabric_view(graph, "typo")
    except KeyError as exc:
        error = exc
    else:
        error = None

    assert error is not None
    assert "Unknown fabric" in str(error)


def test_build_fabric_output_name_normalizes_for_filesystem():
    assert build_fabric_output_name("front/end") == "front_end"


def test_contiguous_lane_allocator_uses_lowest_available_contiguous_spans():
    allocator = ContiguousLaneAllocator(total_lane_units=8)

    assert allocator.allocate(1) == 1
    assert allocator.allocate(2) == 2
    assert allocator.allocate(3) == 4
    assert allocator.allocate(2) == 7


def test_contiguous_lane_allocator_is_one_based_for_single_lane_allocations():
    allocator = ContiguousLaneAllocator(total_lane_units=3)

    assert allocator.allocate(1) == 1
    assert allocator.allocate(1) == 2
    assert allocator.allocate(1) == 3


def test_contiguous_lane_allocator_rejects_exhausted_capacity():
    allocator = ContiguousLaneAllocator(total_lane_units=4)

    assert allocator.allocate(3) == 1

    try:
        allocator.allocate(2)
    except ValueError as exc:
        error = exc
    else:
        error = None

    assert error is not None
    assert "Unable to allocate 2 contiguous lane units from 4 available units." == str(
        error
    )
