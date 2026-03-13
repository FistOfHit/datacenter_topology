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
        "source_node_id",
        "source_node_port",
        "target_node_port",
        "target_node_id",
        "target_serial_number",
        "cable_number",
    ]
    assert len(port_mapping) == 832
