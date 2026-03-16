import pytest

from topology_generator.expander import expand_topology
from topology_generator.validator import (
    TopologyValidationError,
    build_node_usage,
    validate_expanded_topology,
)


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


def test_build_node_usage_reports_pool_lane_and_bandwidth_totals(mixed_speed_config):
    usage = build_node_usage(expand_topology(mixed_speed_config))

    assert usage["pod_1_compute_1"].required_lane_units_for_pool("fabric") == 1
    assert usage["pod_1_compute_1"].bandwidth_up_gb == 400
    assert usage["pod_1_leaf_switch_1"].required_lane_units_for_pool("fabric") == 4
    assert usage["pod_1_leaf_switch_1"].bandwidth_down_gb == 800
    assert usage["pod_1_leaf_switch_1"].bandwidth_up_gb == 800
    assert usage["spine_1"].required_lane_units_for_pool("fabric") == 2
    assert usage["spine_1"].bandwidth_down_gb == 800


def test_validate_expanded_topology_keeps_port_pool_capacity_isolated():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "compute",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 1, [(400, 1)]),
                ],
            },
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 1, [(400, 1)]),
                    _pool("mgmt", 100, 4, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 1, [(400, 1)]),
                    _pool("mgmt", 100, 4, [(100, 1)]),
                ],
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "leaf",
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
                "cables_per_pair": 3,
                "cable_bandwidth_gb": 100,
            },
        ],
    }

    usage = validate_expanded_topology(expand_topology(config))

    assert usage["leaf_1"].required_lane_units_for_pool("fabric") == 1
    assert usage["leaf_1"].required_lane_units_for_pool("mgmt") == 3
    assert usage["leaf_1"].required_lane_units == 4


def test_validate_expanded_topology_reports_pool_capacity_failures():
    config = {
        "groups": [],
        "layers": [
            {
                "name": "leaf",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 1, [(400, 1)]),
                    _pool("mgmt", 100, 2, [(100, 1)]),
                ],
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_pools": [
                    _pool("fabric", 400, 1, [(400, 1)]),
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
                "cables_per_pair": 3,
                "cable_bandwidth_gb": 100,
            }
        ],
    }

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_expanded_topology(expand_topology(config))

    assert "leaf_1 port pool 'mgmt' requires 3 lane units but has 2" in str(exc_info.value)
    assert "spine_1 port pool 'mgmt' requires 3 lane units but has 2" in str(exc_info.value)


def test_validate_expanded_topology_supports_mixed_speed_nodes(mixed_speed_config):
    usage = validate_expanded_topology(expand_topology(mixed_speed_config))

    assert usage["pod_1_leaf_switch_1"].required_lane_units_for_pool("fabric") == 4


def test_validate_expanded_topology_keeps_gpu_node_capacity_isolated_by_fabric(
    multi_fabric_config,
):
    usage = validate_expanded_topology(expand_topology(multi_fabric_config))

    assert usage["backend__gpu_nodes_1"].required_lane_units_for_pool("fabric") == 1
    assert usage["frontend__gpu_nodes_1"].required_lane_units_for_pool("fabric") == 1
    assert usage["oob__gpu_nodes_1"].required_lane_units_for_pool("fabric") == 1


def test_validate_expanded_topology_reports_only_failing_fabric(multi_fabric_config):
    invalid_config = dict(multi_fabric_config)
    invalid_fabrics = [dict(fabric) for fabric in multi_fabric_config["fabrics"]]
    invalid_links = [dict(link) for link in invalid_fabrics[0]["links"]]
    invalid_links[0]["cables_per_pair"] = 2
    invalid_fabrics[0]["links"] = invalid_links
    invalid_config["fabrics"] = invalid_fabrics

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_expanded_topology(expand_topology(invalid_config))

    message = str(exc_info.value)
    assert "backend__gpu_nodes_1 port pool 'fabric' requires 2 lane units but has 1" in message
    assert "frontend__gpu_nodes_1" not in message
    assert "oob__gpu_nodes_1" not in message
