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
    assert len(excel_data) == 8
    assert list(excel_data.columns) == [
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


def test_main_logs_and_reraises_errors(tmp_path, sample_config):
    output_dir = tmp_path / "outputs"
    invalid_config_path = tmp_path / "invalid.yaml"
    invalid_config = dict(sample_config)
    invalid_links = [dict(link) for link in sample_config["links"]]
    invalid_links[0]["cable_bandwidth_gb"] = 0
    invalid_config["links"] = invalid_links
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
    assert "Traceback (most recent call last)" in log_contents


def test_main_creates_multi_fabric_outputs(tmp_path, multi_fabric_config):
    output_dir = tmp_path / "outputs"
    config_path = tmp_path / "multi_fabric.yaml"
    config_path.write_text(yaml.safe_dump(multi_fabric_config), encoding="utf-8")

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            str(config_path),
            "--output-dir",
            str(output_dir),
        ],
    ):
        main()

    assert (output_dir / "topology_backend.png").exists()
    assert (output_dir / "topology_frontend.png").exists()
    assert (output_dir / "topology_oob.png").exists()
    assert (output_dir / "port_mapping.xlsx").exists()

    excel_data = pd.read_excel(output_dir / "port_mapping.xlsx")
    assert "fabric" in excel_data.columns
    assert len(excel_data) == 7


def test_main_timestamp_writes_outputs_to_resolved_directory(tmp_path, sample_config_file):
    base_output_dir = tmp_path / "outputs"
    resolved_output_dir = base_output_dir / "20260314_120000"

    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            str(sample_config_file),
            "--output-dir",
            str(base_output_dir),
            "--timestamp",
        ],
    ):
        with patch(
            "topology_generator.file_handler.resolve_output_dir",
            return_value=resolved_output_dir,
        ) as mock_resolve_output_dir:
            main()

    mock_resolve_output_dir.assert_called_once_with(str(base_output_dir), True)
    assert (resolved_output_dir / "topology.png").exists()
    assert (resolved_output_dir / "port_mapping.xlsx").exists()
    assert (resolved_output_dir / "network_topology.log").exists()
    assert not (base_output_dir / "topology.png").exists()
    assert not (base_output_dir / "port_mapping.xlsx").exists()
    assert not (base_output_dir / "network_topology.log").exists()

    log_contents = (resolved_output_dir / "network_topology.log").read_text(
        encoding="utf-8"
    )
    assert f"Created output directory: {resolved_output_dir}" in log_contents
