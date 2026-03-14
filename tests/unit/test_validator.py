import pytest

from topology_generator.expander import expand_topology
from topology_generator.validator import (
    TopologyValidationError,
    build_node_usage,
    validate_expanded_topology,
)


def test_build_node_usage_reports_lane_and_bandwidth_totals(mixed_speed_config):
    usage = build_node_usage(expand_topology(mixed_speed_config))

    assert usage["pod_1_compute_1"].required_lane_units == 1
    assert usage["pod_1_compute_1"].bandwidth_up_gb == 400
    assert usage["pod_1_leaf_switch_1"].required_lane_units == 4
    assert usage["pod_1_leaf_switch_1"].bandwidth_down_gb == 800
    assert usage["pod_1_leaf_switch_1"].bandwidth_up_gb == 800
    assert usage["spine_1"].required_lane_units == 2
    assert usage["spine_1"].bandwidth_down_gb == 800


def test_validate_expanded_topology_reports_all_lane_capacity_failures(sample_config):
    invalid_config = dict(sample_config)
    invalid_layers = [dict(layer) for layer in sample_config["layers"]]
    invalid_leaf_port_layout = dict(invalid_layers[1]["port_layout"])
    invalid_leaf_port_layout["total_lane_units"] = 3
    invalid_layers[1]["port_layout"] = invalid_leaf_port_layout
    invalid_spine_port_layout = dict(invalid_layers[2]["port_layout"])
    invalid_spine_port_layout["total_lane_units"] = 1
    invalid_layers[2]["port_layout"] = invalid_spine_port_layout
    invalid_config["layers"] = invalid_layers

    with pytest.raises(TopologyValidationError) as exc_info:
        validate_expanded_topology(expand_topology(invalid_config))

    message = str(exc_info.value)
    assert "pod_1_leaf_1 requires 4 lane units but has 3" in message
    assert "pod_2_leaf_1 requires 4 lane units but has 3" in message
    assert "spine_1 requires 2 lane units but has 1" in message
    assert "spine_2 requires 2 lane units but has 1" in message


def test_validate_expanded_topology_supports_mixed_speed_nodes(mixed_speed_config):
    usage = validate_expanded_topology(expand_topology(mixed_speed_config))

    assert usage["pod_1_leaf_switch_1"].required_lane_units == 4


def test_validate_expanded_topology_keeps_gpu_node_capacity_isolated_by_fabric(
    multi_fabric_config,
):
    usage = validate_expanded_topology(expand_topology(multi_fabric_config))

    assert usage["backend__gpu_nodes_1"].required_lane_units == 1
    assert usage["frontend__gpu_nodes_1"].required_lane_units == 1
    assert usage["oob__gpu_nodes_1"].required_lane_units == 1


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
    assert "backend__gpu_nodes_1 requires 2 lane units but has 1" in message
    assert "frontend__gpu_nodes_1" not in message
    assert "oob__gpu_nodes_1" not in message
