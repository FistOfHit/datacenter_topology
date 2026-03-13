import os
from pathlib import Path

import pytest
import yaml


os.environ.setdefault("MPLBACKEND", "Agg")


def two_layer_config_dict() -> dict[str, object]:
    return {
        "layers": [
            {
                "name": "compute",
                "node_count_in_layer": 4,
                "ports_per_node": 2,
                "port_bandwidth_gb_per_port": 10,
                "uplink_cables_per_node_to_each_node_in_next_layer": 1,
                "uplink_cable_bandwidth_gb": 10,
            },
            {
                "name": "aggregation",
                "node_count_in_layer": 2,
                "ports_per_node": 4,
                "port_bandwidth_gb_per_port": 10,
                "downlink_cables_per_node_to_each_node_in_previous_layer": 1,
                "downlink_cable_bandwidth_gb": 10,
            },
        ]
    }


def four_layer_config_dict() -> dict[str, object]:
    return {
        "layers": [
            {
                "name": "compute",
                "node_count_in_layer": 2,
                "ports_per_node": 4,
                "port_bandwidth_gb_per_port": 10,
                "uplink_cables_per_node_to_each_node_in_next_layer": 1,
                "uplink_cable_bandwidth_gb": 10,
            },
            {
                "name": "aggregation",
                "node_count_in_layer": 2,
                "ports_per_node": 4,
                "port_bandwidth_gb_per_port": 20,
                "downlink_cables_per_node_to_each_node_in_previous_layer": 1,
                "downlink_cable_bandwidth_gb": 10,
                "uplink_cables_per_node_to_each_node_in_next_layer": 2,
                "uplink_cable_bandwidth_gb": 20,
            },
            {
                "name": "fabric",
                "node_count_in_layer": 1,
                "ports_per_node": 5,
                "port_bandwidth_gb_per_port": 40,
                "downlink_cables_per_node_to_each_node_in_previous_layer": 2,
                "downlink_cable_bandwidth_gb": 20,
                "uplink_cables_per_node_to_each_node_in_next_layer": 1,
                "uplink_cable_bandwidth_gb": 40,
            },
            {
                "name": "core",
                "node_count_in_layer": 1,
                "ports_per_node": 1,
                "port_bandwidth_gb_per_port": 40,
                "downlink_cables_per_node_to_each_node_in_previous_layer": 1,
                "downlink_cable_bandwidth_gb": 40,
            },
        ]
    }


@pytest.fixture
def sample_two_layer_config():
    return two_layer_config_dict()


@pytest.fixture
def sample_config():
    return four_layer_config_dict()


@pytest.fixture
def sample_config_file(tmp_path, sample_config):
    config_path = Path(tmp_path) / "config.yaml"
    config_path.write_text(yaml.safe_dump(sample_config), encoding="utf-8")
    return config_path
