import pytest

from topology_generator.config_schema import InvalidTopologyConfig, TopologyConfig


def test_topology_config_accepts_lane_based_schema(mixed_speed_config):
    config = TopologyConfig.from_mapping(mixed_speed_config)

    assert config.group() is not None
    assert config.group().name == "pod"
    assert config.layer("Leaf Switch").total_lane_units == 4
    assert config.layer("Leaf Switch").supported_port_bandwidths_gb == (400.0, 800.0)


def test_topology_config_rejects_legacy_layer_port_fields(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[0]["ports_per_node"] = 8
    invalid_layers[0]["port_bandwidth_gb_per_port"] = 400
    invalid_config["layers"] = invalid_layers

    with pytest.raises(InvalidTopologyConfig, match="legacy port fields"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_duplicate_normalized_layer_names(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_layers[1]["name"] = "leaf!!"
    invalid_layers[2]["name"] = "leaf"
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


def test_topology_config_rejects_unsupported_link_bandwidth(sample_config):
    invalid_config = dict(sample_config)
    invalid_links = [dict(link) for link in sample_config["links"]]
    invalid_links[0]["cable_bandwidth_gb"] = 200
    invalid_config["links"] = invalid_links

    with pytest.raises(InvalidTopologyConfig, match="is not supported by layer"):
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_rejects_invalid_port_mode_math(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_port_layout = dict(invalid_layers[0]["port_layout"])
    invalid_port_layout["supported_port_modes"] = [
        {
            "port_bandwidth_gb": 150,
            "lane_units": 1,
        }
    ]
    invalid_layers[0]["port_layout"] = invalid_port_layout
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
                "port_layout": {
                    "base_lane_bandwidth_gb": 0.1,
                    "total_lane_units": 3,
                    "supported_port_modes": [
                        {
                            "port_bandwidth_gb": 0.3,
                            "lane_units": 3,
                        }
                    ],
                },
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_layout": {
                    "base_lane_bandwidth_gb": 0.1,
                    "total_lane_units": 3,
                    "supported_port_modes": [
                        {
                            "port_bandwidth_gb": 0.3,
                            "lane_units": 3,
                        }
                    ],
                },
            },
        ],
        "links": [
            {
                "from": "leaf",
                "to": "spine",
                "policy": "global_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 0.3,
            }
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.layer("leaf").lane_units_for_bandwidth(0.3) == 3


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
        TopologyConfig.from_mapping(invalid_config)


def test_topology_config_accepts_multi_fabric_gpu_nodes_schema(multi_fabric_config):
    config = TopologyConfig.from_mapping(multi_fabric_config)

    assert config.is_multi_fabric is True
    assert config.gpu_nodes is not None
    assert config.gpu_nodes.total_nodes == 2
    assert config.grouping("pod").members_per_group == 2
    assert config.grouping("rack").members_per_group == 1
    assert config.fabric_names == ("backend", "frontend", "oob")
    assert config.gpu_nodes.port_layout_for_fabric("backend").total_lane_units == 1
    assert config.fabric("oob").grouping == "rack"


def test_topology_config_rejects_mismatched_gpu_nodes_fabric_names(multi_fabric_config):
    invalid_config = dict(multi_fabric_config)
    invalid_gpu_nodes = dict(multi_fabric_config["gpu_nodes"])
    invalid_port_layouts = dict(invalid_gpu_nodes["fabric_port_layouts"])
    invalid_port_layouts["front_end"] = invalid_port_layouts.pop("frontend")
    invalid_gpu_nodes["fabric_port_layouts"] = invalid_port_layouts
    invalid_config["gpu_nodes"] = invalid_gpu_nodes

    with pytest.raises(InvalidTopologyConfig, match="fabric_port_layouts must match fabrics"):
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


def test_topology_config_accepts_normalized_fabric_port_layout_name_matches():
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
                "front_end": {
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
                "name": "front-end",
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

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.gpu_nodes is not None
    assert parsed.gpu_nodes.port_layout_for_fabric("front-end").total_lane_units == 1


def test_topology_config_reports_correct_multi_fabric_layer_path_for_placement_error():
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
                "backend": {
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
                "name": "backend",
                "grouping": "pod",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "rack",
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
                "links": [],
            }
        ],
    }

    with pytest.raises(InvalidTopologyConfig, match=r"fabrics\[0\]\.layers\[0\]\.placement"):
        TopologyConfig.from_mapping(config)


def test_topology_config_accepts_legacy_multi_fabric_shape():
    config = {
        "groups": [
            {
                "name": "pod",
                "count": 1,
            }
        ],
        "gpu_nodes": {
            "nodes_per_group": 2,
            "fabric_port_layouts": {
                "backend": {
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
                "name": "backend",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "pod",
                        "nodes_per_group": 1,
                        "port_layout": {
                            "base_lane_bandwidth_gb": 100,
                            "total_lane_units": 2,
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

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.gpu_nodes is not None
    assert parsed.gpu_nodes.total_nodes == 2
    assert parsed.grouping("pod").members_per_group == 2
    assert parsed.fabric("backend").grouping == "pod"


def test_topology_config_accepts_legacy_multi_fabric_global_only_shape():
    config = {
        "groups": [],
        "gpu_nodes": {
            "nodes_per_group": 2,
            "fabric_port_layouts": {
                "backend": {
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
                "name": "backend",
                "layers": [
                    {
                        "name": "mgmt",
                        "placement": "global",
                        "nodes_per_group": 1,
                        "port_layout": {
                            "base_lane_bandwidth_gb": 100,
                            "total_lane_units": 2,
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
                        "to": "mgmt",
                        "policy": "global_to_global_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    }
                ],
            }
        ],
    }

    parsed = TopologyConfig.from_mapping(config)

    assert parsed.gpu_nodes is not None
    assert parsed.gpu_nodes.total_nodes == 2
    assert parsed.groupings == ()
    assert parsed.fabric("backend").grouping is None


def test_topology_config_rejects_reserved_gpu_nodes_grouping_name():
    config = {
        "groupings": [
            {
                "name": "gpu_nodes",
                "members_per_group": 1,
            }
        ],
        "gpu_nodes": {
            "total_nodes": 1,
            "fabric_port_layouts": {
                "backend": {
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
                "name": "backend",
                "grouping": "gpu_nodes",
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

    with pytest.raises(InvalidTopologyConfig, match="reserved placement names"):
        TopologyConfig.from_mapping(config)
