from unittest.mock import patch

import pandas as pd
import yaml

from topology_generator.main import main


def test_main_creates_outputs(tmp_path, sample_config_file):
    output_dir = tmp_path / "outputs"

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            str(sample_config_file),
            "--output-dir",
            str(output_dir),
        ],
    ):
        main()

    assert (output_dir / "topology.png").exists()
    assert (output_dir / "port_mapping.xlsx").exists()
    assert (output_dir / "network_topology.log").exists()

    excel_data = pd.read_excel(output_dir / "port_mapping.xlsx")
    assert len(excel_data) == 9


def test_main_logs_and_reraises_errors(tmp_path, sample_two_layer_config):
    output_dir = tmp_path / "outputs"
    invalid_config_path = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_two_layer_config)
    invalid_layers = [dict(layer) for layer in sample_two_layer_config["layers"]]
    invalid_layers[0]["uplink_cable_bandwidth_gb"] = 0
    invalid_config["layers"] = invalid_layers
    invalid_config_path.write_text(yaml.safe_dump(invalid_config), encoding="utf-8")

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            str(invalid_config_path),
            "--output-dir",
            str(output_dir),
        ],
    ):
        try:
            main()
        except Exception as exc:
            error = exc
        else:
            error = None

    assert error is not None
    assert "must be greater than zero" in str(error)
    log_contents = (output_dir / "network_topology.log").read_text(encoding="utf-8")
    assert "Error during execution" in log_contents
