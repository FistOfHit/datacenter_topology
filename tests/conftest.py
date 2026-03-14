import os
from pathlib import Path

import pytest
import yaml


os.environ.setdefault("MPLBACKEND", "Agg")


def port_layout(
    base_lane_bandwidth_gb: float,
    total_lane_units: int,
    supported_modes: list[tuple[float, int]],
) -> dict[str, object]:
    return {
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


def grouped_config_dict() -> dict[str, object]:
    return {
        "groups": [
            {
                "name": "pod",
                "count": 2,
            }
        ],
        "layers": [
            {
                "name": "compute",
                "placement": "pod",
                "nodes_per_group": 2,
                "port_layout": port_layout(100, 1, [(100, 1)]),
            },
            {
                "name": "leaf",
                "placement": "pod",
                "nodes_per_group": 1,
                "port_layout": port_layout(100, 4, [(100, 1)]),
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 2,
                "port_layout": port_layout(100, 2, [(100, 1)]),
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "leaf",
                "policy": "within_group_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 100,
            },
            {
                "from": "leaf",
                "to": "spine",
                "policy": "group_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 100,
            },
        ],
    }


def global_config_dict() -> dict[str, object]:
    return {
        "groups": [],
        "layers": [
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 2,
                "port_layout": port_layout(200, 1, [(200, 1)]),
            },
            {
                "name": "core",
                "placement": "global",
                "nodes_per_group": 1,
                "port_layout": port_layout(200, 2, [(200, 1)]),
            },
        ],
        "links": [
            {
                "from": "spine",
                "to": "core",
                "policy": "global_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            }
        ],
    }


def mixed_speed_config_dict() -> dict[str, object]:
    return {
        "groups": [
            {
                "name": "pod",
                "count": 1,
            }
        ],
        "layers": [
            {
                "name": "Compute",
                "placement": "pod",
                "nodes_per_group": 2,
                "port_layout": port_layout(400, 2, [(400, 1)]),
            },
            {
                "name": "Leaf Switch",
                "placement": "pod",
                "nodes_per_group": 1,
                "port_layout": port_layout(400, 4, [(400, 1), (800, 2)]),
            },
            {
                "name": "Spine",
                "placement": "global",
                "nodes_per_group": 1,
                "port_layout": port_layout(400, 4, [(400, 1), (800, 2)]),
            },
        ],
        "links": [
            {
                "from": "Compute",
                "to": "Leaf Switch",
                "policy": "within_group_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 400,
            },
            {
                "from": "Leaf Switch",
                "to": "Spine",
                "policy": "group_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 800,
            },
        ],
    }


def two_pod_dense_config_dict() -> dict[str, object]:
    return {
        "groups": [
            {
                "name": "pod",
                "count": 2,
            }
        ],
        "layers": [
            {
                "name": "compute",
                "placement": "pod",
                "nodes_per_group": 8,
                "port_layout": port_layout(200, 4, [(200, 1)]),
            },
            {
                "name": "leaf",
                "placement": "pod",
                "nodes_per_group": 4,
                "port_layout": port_layout(200, 12, [(200, 1)]),
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 4,
                "port_layout": port_layout(200, 8, [(200, 1)]),
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "leaf",
                "policy": "within_group_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            },
            {
                "from": "leaf",
                "to": "spine",
                "policy": "group_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            },
        ],
    }


def multi_pod_dense_config_dict() -> dict[str, object]:
    return {
        "groups": [
            {
                "name": "pod",
                "count": 6,
            }
        ],
        "layers": [
            {
                "name": "compute",
                "placement": "pod",
                "nodes_per_group": 8,
                "port_layout": port_layout(200, 4, [(200, 1)]),
            },
            {
                "name": "leaf",
                "placement": "pod",
                "nodes_per_group": 4,
                "port_layout": port_layout(200, 12, [(200, 1)]),
            },
            {
                "name": "spine",
                "placement": "global",
                "nodes_per_group": 4,
                "port_layout": port_layout(200, 32, [(200, 1)]),
            },
            {
                "name": "core",
                "placement": "global",
                "nodes_per_group": 2,
                "port_layout": port_layout(200, 4, [(200, 1)]),
            },
        ],
        "links": [
            {
                "from": "compute",
                "to": "leaf",
                "policy": "within_group_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            },
            {
                "from": "leaf",
                "to": "spine",
                "policy": "group_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            },
            {
                "from": "spine",
                "to": "core",
                "policy": "global_to_global_full_mesh",
                "cables_per_pair": 1,
                "cable_bandwidth_gb": 200,
            },
        ],
    }


def multi_fabric_config_dict() -> dict[str, object]:
    return {
        "groupings": [
            {
                "name": "pod",
                "members_per_group": 2,
            },
            {
                "name": "rack",
                "members_per_group": 1,
            },
        ],
        "gpu_nodes": {
            "total_nodes": 2,
            "fabric_port_layouts": {
                "backend": port_layout(100, 1, [(100, 1)]),
                "frontend": port_layout(50, 1, [(50, 1)]),
                "oob": port_layout(25, 1, [(25, 1)]),
            },
        },
        "fabrics": [
            {
                "name": "backend",
                "grouping": "pod",
                "layers": [
                    {
                        "name": "leaf",
                        "placement": "group",
                        "nodes_per_group": 1,
                        "port_layout": port_layout(100, 3, [(100, 1)]),
                    },
                    {
                        "name": "spine",
                        "placement": "global",
                        "nodes_per_group": 1,
                        "port_layout": port_layout(100, 1, [(100, 1)]),
                    },
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "leaf",
                        "policy": "within_group_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    },
                    {
                        "from": "leaf",
                        "to": "spine",
                        "policy": "group_to_global_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 100,
                    },
                ],
            },
            {
                "name": "frontend",
                "grouping": "pod",
                "layers": [
                    {
                        "name": "tor",
                        "placement": "group",
                        "nodes_per_group": 1,
                        "port_layout": port_layout(50, 2, [(50, 1)]),
                    }
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "tor",
                        "policy": "within_group_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 50,
                    }
                ],
            },
            {
                "name": "oob",
                "grouping": "rack",
                "layers": [
                    {
                        "name": "mgmt",
                        "placement": "global",
                        "nodes_per_group": 1,
                        "port_layout": port_layout(25, 2, [(25, 1)]),
                    }
                ],
                "links": [
                    {
                        "from": "gpu_nodes",
                        "to": "mgmt",
                        "policy": "group_to_global_full_mesh",
                        "cables_per_pair": 1,
                        "cable_bandwidth_gb": 25,
                    }
                ],
            },
        ],
    }


@pytest.fixture
def sample_config():
    return grouped_config_dict()


@pytest.fixture
def sample_global_config():
    return global_config_dict()


@pytest.fixture
def mixed_speed_config():
    return mixed_speed_config_dict()


@pytest.fixture
def sample_config_file(tmp_path, sample_config):
    config_path = Path(tmp_path) / "config.yaml"
    config_path.write_text(yaml.safe_dump(sample_config), encoding="utf-8")
    return config_path


@pytest.fixture
def two_pod_dense_config():
    return two_pod_dense_config_dict()


@pytest.fixture
def multi_pod_dense_config():
    return multi_pod_dense_config_dict()


@pytest.fixture
def multi_fabric_config():
    return multi_fabric_config_dict()
