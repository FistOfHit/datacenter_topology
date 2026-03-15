import pytest

from topology_generator.config_types import InvalidTopologyConfig
from topology_generator.expander import expand_topology


def test_expand_topology_creates_grouped_and_global_nodes(sample_config):
    expanded = expand_topology(sample_config)

    assert [node.node_id for node in expanded.nodes] == [
        "pod_1_compute_1",
        "pod_1_compute_2",
        "pod_2_compute_1",
        "pod_2_compute_2",
        "pod_1_leaf_1",
        "pod_2_leaf_1",
        "spine_1",
        "spine_2",
    ]


def test_expand_topology_applies_bandwidth_specific_lane_units(mixed_speed_config):
    expanded = expand_topology(mixed_speed_config)

    grouped_links = {
        (link.source_node_id, link.target_node_id): (
            link.cable_bandwidth_gb,
            link.source_lane_units_per_cable,
            link.target_lane_units_per_cable,
        )
        for link in expanded.links
    }

    assert grouped_links[("pod_1_compute_1", "pod_1_leaf_switch_1")] == (400.0, 1, 1)
    assert grouped_links[("pod_1_leaf_switch_1", "spine_1")] == (800.0, 2, 2)


def test_expand_topology_rejects_colliding_node_ids_during_schema_validation():
    invalid_config = {
        "groups": [
            {
                "name": "pod",
                "count": 1,
            }
        ],
        "layers": [
            {
                "name": "compute",
                "placement": "pod",
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
            },
            {
                "name": "pod_1_compute",
                "placement": "global",
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
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "pod_1_compute",
                "policy": "group_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 100,
            }
        ],
    }

    with pytest.raises(InvalidTopologyConfig, match="Expanded node IDs must be unique"):
        expand_topology(invalid_config)


def test_expand_topology_duplicates_gpu_nodes_per_fabric_for_validation(multi_fabric_config):
    expanded = expand_topology(multi_fabric_config)

    shared_gpu_nodes = [
        node
        for node in expanded.nodes
        if node.is_shared_gpu_node and node.graph_node_id == "gpu_nodes_1"
    ]

    assert sorted(node.node_id for node in shared_gpu_nodes) == [
        "backend__gpu_nodes_1",
        "frontend__gpu_nodes_1",
        "oob__gpu_nodes_1",
    ]
    assert {node.fabric_name for node in shared_gpu_nodes} == {"backend", "frontend", "oob"}
    assert {node.group_label for node in shared_gpu_nodes} == {"pod_1", "pod_1_rack_1"}
