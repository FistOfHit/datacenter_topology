import pytest

from topology_generator.config_types import InvalidTopologyConfig, TopologyConfig


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


def test_topology_config_accepts_lane_based_pool_schema(mixed_speed_config):
    config = TopologyConfig.from_mapping(mixed_speed_config)

    assert config.group() is not None
    assert config.group().name == "pod"
    assert config.layer("Leaf Switch").total_lane_units == 4
    assert config.layer("Leaf Switch").supported_port_bandwidths_gb == (400.0, 800.0)
    assert config.layer("Leaf Switch").port_pool_names == ("fabric",)


def test_topology_config_accepts_multiple_port_pools():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 4, [(400, 1), (800, 2)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 4, [(400, 1), (800, 2)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "mgmt",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 100,
            }
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.layer("leaf").port_pool_names == ("fabric", "mgmt")
    assert parsed.layer("leaf").port_pool("mgmt").total_lane_units == 2
    assert parsed.layer("leaf").port_pool_offset("mgmt") == 4


def test_topology_config_accepts_same_adjacent_layers_on_different_pools():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "fabric",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 400,
            },
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "mgmt",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 100,
            },
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert tuple(link.port_pool for link in parsed.links) == ("fabric", "mgmt")


def test_topology_config_rejects_duplicate_adjacent_layers_on_same_pool():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [_pool("fabric", 400, 2, [(400, 1)])],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [_pool("fabric", 400, 2, [(400, 1)])],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "fabric",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 400,
            },
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "fabric",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 400,
            },
        ],
    }

    with pytest.raises(
        InvalidTopologyConfig,
        match="adjacent layer pair and port_pool combination may only be linked once",
    ):
        TopologyConfig.from_mapping(config)


def test_topology_config_rejects_legacy_port_layout_field(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[0]["port_layout"] = {
        "base_lane_bandwidth_gb": 100,
        "total_lane_units": 1,
        "supported_port_modes": [{"port_bandwidth_gb": 100, "lane_units": 1}],
    }
    invalid_config["layers"] = invalid_layers

    with pytest.raises(InvalidTopologyConfig, match="port_layout is no longer supported"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_duplicate_normalized_pool_names(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[1]["port_pools"] = [
        _pool("fabric", 100, 2, [(100, 1)]),
        _pool("fabric!!", 100, 2, [(100, 1)]),
    ]
    invalid_config["layers"] = invalid_layers

    with pytest.raises(InvalidTopologyConfig, match="remain unique after identifier normalization"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_non_alphanumeric_names(sample_config):
    invalid_config = dict(sample_config)
    invalid_groups = [dict(group) for group in sample_config["groups"]]
    invalid_groups[0]["name"] = "!!!"
    invalid_config["groups"] = invalid_groups

    with pytest.raises(InvalidTopologyConfig, match="must contain at least one alphanumeric"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_missing_link_port_pool(sample_config):
    invalid_config = dict(sample_config)
    invalid_links = [dict(link) for link in sample_config["links"]]
    invalid_links[0].pop("port_pool")
    invalid_config["links"] = invalid_links

    with pytest.raises(InvalidTopologyConfig, match="port_pool must be a non-empty string"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_link_port_pool_missing_on_endpoint(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[0]["port_pools"] = [_pool("mgmt", 100, 1, [(100, 1)])]
    invalid_config["layers"] = invalid_layers

    with pytest.raises(InvalidTopologyConfig, match="port_pool 'fabric' is not defined"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_unsupported_link_bandwidth_in_named_pool():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 2, [(400, 1)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "mgmt",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 400,
            }
        ],
    }

    with pytest.raises(InvalidTopologyConfig, match="port pool 'mgmt'"):
        TopologyConfig.from_mapping(config)


def test_topology_config_rejects_invalid_port_mode_math(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_port_pools = [dict(pool) for pool in invalid_layers[0]["port_pools"]]
    invalid_port_pools[0]["supported_port_modes"] = [
        {
            "port_bandwidth_gb": 150,
            "lane_units": 1,
        }
    ]
    invalid_layers[0]["port_pools"] = invalid_port_pools
    invalid_config["layers"] = invalid_layers

    with pytest.raises(InvalidTopologyConfig, match="base_lane_bandwidth_gb \\* lane_units"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_accepts_fractional_bandwidths():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 0.1, 3, [(0.3, 3)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 0.1, 3, [(0.3, 3)]),
                ],
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_full_mesh",
                "port_pool": "fabric",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 0.3,
            }
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.layer("leaf").lane_units_for_pool_bandwidth("fabric", 0.3) == 3


def test_topology_config_rejects_reserved_global_group_name(sample_config):
    invalid_config = dict(sample_config)
    invalid_groups = [dict(group) for group in sample_config["groups"]]
    invalid_groups[0]["name"] = "global"
    invalid_config["groups"] = invalid_groups

    with pytest.raises(InvalidTopologyConfig, match="reserved placement name"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_expanded_node_id_collisions():
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
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_accepts_multi_fabric_gpu_nodes_schema(multi_fabric_config):
    config = TopologyConfig.from_mapping(multi_fabric_config)

    assert config.is_multi_fabric is True
    assert config.gpu_nodes is not None
    assert config.gpu_nodes.total_nodes == 2
    assert config.grouping("pod").members_per_group == 2
    assert config.grouping("rack").members_per_group == 1
    assert config.fabric_names == ("backend", "frontend", "oob")
    assert config.gpu_nodes.port_pools_for_fabric("backend")[0].total_lane_units == 1
    assert config.fabric("oob").gpu_nodes_placement == "rack"


def test_topology_config_rejects_mismatched_gpu_nodes_fabric_names(multi_fabric_config):
    invalid_config = dict(multi_fabric_config)
    invalid_gpu_nodes = dict(multi_fabric_config["gpu_nodes"])
    invalid_port_pools = dict(invalid_gpu_nodes["fabric_port_pools"])
    invalid_port_pools["front_end"] = invalid_port_pools.pop("frontend")
    invalid_gpu_nodes["fabric_port_pools"] = invalid_port_pools
    invalid_config["gpu_nodes"] = invalid_gpu_nodes

    with pytest.raises(InvalidTopologyConfig, match="fabric_port_pools must match fabrics"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_redefining_gpu_nodes_in_fabric_layers(multi_fabric_config):
    invalid_config = dict(multi_fabric_config)
    invalid_fabrics = [dict(fabric) for fabric in multi_fabric_config["fabrics"]]
    invalid_layers = [dict(layer) for layer in invalid_fabrics[0]["layers"]]
    invalid_layers[0]["name"] = "gpu_nodes"
    invalid_fabrics[0]["layers"] = invalid_layers
    invalid_config["fabrics"] = invalid_fabrics

    with pytest.raises(InvalidTopologyConfig, match="must not redefine 'gpu_nodes'"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_accepts_normalized_fabric_port_pool_name_matches():
    config = {
        "groupings": [
            {
                "name": "pod",
                "members_per_group": 1,
            }
        ],
        "gpu_nodes": {
            "total_nodes": 1,
            "fabric_port_pools": {
                "front_end": [_pool("fabric", 100, 1, [(100, 1)])]
            },
        },
        "fabrics": [
            {
                "name": "front-end",
                "gpu_nodes_placement": "pod",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "pod",
                        "nodes_per_group": 1,
                        "port_pools": [_pool("fabric", 100, 1, [(100, 1)])],
                    }
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "leaf",
                        "policy": "same_scope_full_mesh",
                        "port_pool": "fabric",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    }
                ],
            }
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.gpu_nodes is not None
    assert parsed.gpu_nodes.port_pools_for_fabric("front-end")[0].total_lane_units == 1
