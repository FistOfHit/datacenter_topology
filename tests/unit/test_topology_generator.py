import networkx as nx

from topology_generator.config_schema import TopologyConfig
from topology_generator.topology_generator import calculate_port_stats, generate_topology


def test_generate_topology_builds_expected_graph(sample_config):
    graph = generate_topology(sample_config)

    assert sorted(graph.nodes) == [
        "aggregation_1",
        "aggregation_2",
        "compute_1",
        "compute_2",
        "core_1",
        "fabric_1",
    ]
    assert sorted(graph.edges()) == [
        ("aggregation_1", "fabric_1"),
        ("aggregation_2", "fabric_1"),
        ("compute_1", "aggregation_1"),
        ("compute_1", "aggregation_2"),
        ("compute_2", "aggregation_1"),
        ("compute_2", "aggregation_2"),
        ("fabric_1", "core_1"),
    ]

    assert graph.edges["compute_1", "aggregation_1"]["source_ports"] == [1]
    assert graph.edges["compute_1", "aggregation_1"]["target_ports"] == [1]
    assert graph.edges["aggregation_1", "fabric_1"]["source_ports"] == [3, 4]
    assert graph.edges["aggregation_1", "fabric_1"]["target_ports"] == [1, 2]
    assert graph.edges["fabric_1", "core_1"]["source_ports"] == [5]
    assert graph.edges["fabric_1", "core_1"]["target_ports"] == [1]

    assert graph.nodes["compute_1"]["used_bandwidth_gb"] == 20
    assert graph.nodes["compute_1"]["used_ports_equivalent"] == 2.0
    assert graph.nodes["aggregation_1"]["used_bandwidth_gb"] == 60
    assert graph.nodes["aggregation_1"]["used_ports_equivalent"] == 3.0
    assert graph.nodes["fabric_1"]["used_bandwidth_gb"] == 120
    assert graph.nodes["fabric_1"]["used_ports_equivalent"] == 3.0
    assert graph.nodes["core_1"]["used_bandwidth_gb"] == 40
    assert graph.nodes["core_1"]["used_ports_equivalent"] == 1.0


def test_generate_topology_accepts_validated_config(sample_config):
    config = TopologyConfig.from_mapping(sample_config)

    graph = generate_topology(config)

    assert graph.number_of_nodes() == 6
    assert graph.number_of_edges() == 7


def test_calculate_port_stats():
    graph = nx.Graph()
    graph.add_node("node1", layer_index=0, port_bandwidth_gb=10, used_bandwidth_gb=20)

    calculate_port_stats(graph)

    assert graph.nodes["node1"]["used_ports_equivalent"] == 2.0


def test_calculate_port_stats_handles_zero_port_bandwidth():
    graph = nx.Graph()
    graph.add_node("node1", layer_index=0, port_bandwidth_gb=0, used_bandwidth_gb=20)

    calculate_port_stats(graph)

    assert graph.nodes["node1"]["used_ports_equivalent"] == 0
