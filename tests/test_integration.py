from unittest.mock import patch

import pandas as pd

from topology_generator.main import main


def test_main_integration(tmp_path):
    output_dir = tmp_path / "integration_output"

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            "configs/examples/three_tier_small.yaml",
            "--output-dir",
            str(output_dir),
        ],
    ):
        main()

    assert (output_dir / "topology.png").exists()
    assert (output_dir / "port_mapping.xlsx").exists()
    assert (output_dir / "network_topology.log").exists()

    port_mapping = pd.read_excel(output_dir / "port_mapping.xlsx")
    assert list(port_mapping.columns) == [
        "source_serial_number",
        "source_group",
        "source_node_id",
        "source_node_port",
        "source_lane_units",
        "target_node_port",
        "target_lane_units",
        "target_node_id",
        "target_group",
        "target_serial_number",
        "cable_bandwidth_gb",
        "cable_number",
    ]
    assert len(port_mapping) == 24576


def test_main_multi_fabric_integration(tmp_path):
    output_dir = tmp_path / "integration_multi_output"

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            "configs/examples/multi_fabric_small.yaml",
            "--output-dir",
            str(output_dir),
        ],
    ):
        main()

    assert (output_dir / "topology_backend.png").exists()
    assert (output_dir / "topology_frontend.png").exists()
    assert (output_dir / "topology_oob.png").exists()
    assert (output_dir / "port_mapping.xlsx").exists()
    assert (output_dir / "network_topology.log").exists()

    port_mapping = pd.read_excel(output_dir / "port_mapping.xlsx")
    assert list(port_mapping.columns) == [
        "fabric",
        "source_serial_number",
        "source_group",
        "source_node_id",
        "source_node_port",
        "source_lane_units",
        "target_node_port",
        "target_lane_units",
        "target_node_id",
        "target_group",
        "target_serial_number",
        "cable_bandwidth_gb",
        "cable_number",
    ]
    assert len(port_mapping) == 7
