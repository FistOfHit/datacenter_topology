import pytest

from topology_generator.config_types import InvalidTopologyConfig
from topology_generator.expander import expand_topology


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
            link.port_pool,
            link.cable_bandwidth_gb,
            link.source_lane_units_per_cable,
            link.target_lane_units_per_cable,
        )
        for link in expanded.links
    }

    assert grouped_links[("pod_1_compute_1", "pod_1_leaf_switch_1")] == (
        "fabric",
        400.0,
        1,
        1,
    )
    assert grouped_links[("pod_1_leaf_switch_1", "spine_1")] == (
        "fabric",
        800.0,
        2,
        2,
    )


def test_expand_topology_carries_multi_pool_links_without_cross_pool_leakage():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 4, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 4, [(100, 1)]),
                ],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "mgmt",
                "cables_per_pair": 2,
                "cable_bandwidth_gb": 100,
            }
        ],
    }

    expanded = expand_topology(config)

    assert len(expanded.links) == 1
    assert expanded.links[0].port_pool == "mgmt"
    assert expanded.links[0].source_lane_units_per_cable == 1
    assert expanded.links[0].target_lane_units_per_cable == 1


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
                "port_pools": [_pool("fabric", 100, 1, [(100, 1)])],
            },
            {
                "name": "pod_1_compute",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [_pool("fabric", 100, 1, [(100, 1)])],
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "pod_1_compute",
                "policy": "to_global_full_mesh",
                "port_pool": "fabric",
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


def test_expand_topology_pairs_child_scope_nodes_only_with_containing_ancestor_scope():
    config = {
        "groupings": [
            {"name": "pod", "members_per_group": 2},
            {"name": "rack", "members_per_group": 1},
        ],
        "gpu_nodes": {
            "total_nodes": 4,
            "fabric_port_pools": {
                "oob": [_pool("fabric", 100, 1, [(100, 1)])]
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
                        "port_pools": [_pool("fabric", 100, 2, [(100, 1)])],
                    },
                    {
                        "name": "spine",
                        "placement": "pod",
                        "nodes_per_group": 1,
                        "port_pools": [_pool("fabric", 100, 2, [(100, 1)])],
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
                        "cable_bandwidth_gb": 100,
                    },
                ],
            }
        ],
    }

    expanded = expand_topology(config)
    links = {(link.source_node_id, link.target_node_id) for link in expanded.links}

    assert ("oob__pod_1_rack_1_leaf_1", "oob__pod_1_spine_1") in links
    assert ("oob__pod_1_rack_2_leaf_1", "oob__pod_1_spine_1") in links
    assert ("oob__pod_1_rack_1_leaf_1", "oob__pod_2_spine_1") not in links
