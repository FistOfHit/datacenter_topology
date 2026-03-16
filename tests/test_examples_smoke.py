from pathlib import Path
from unittest.mock import patch

import pandas as pd
import pytest

from topology_generator.main import main


EXAMPLE_EXPECTATIONS = {
    "multi_fabric_backend_frontend.yaml": {
        "topology_files": {"topology_backend.png", "topology_frontend.png"},
        "row_count": 27648,
        "has_fabric_column": True,
    },
    "multi_fabric_backend_frontend_oob.yaml": {
        "topology_files": {
            "topology_backend.png",
            "topology_frontend.png",
            "topology_oob.png",
        },
        "row_count": 32064,
        "has_fabric_column": True,
    },
    "multi_fabric_small.yaml": {
        "topology_files": {
            "topology_backend.png",
            "topology_frontend.png",
            "topology_oob.png",
        },
        "row_count": 7,
        "has_fabric_column": True,
    },
    "three_tier_small.yaml": {
        "topology_files": {"topology.png"},
        "row_count": 24576,
        "has_fabric_column": False,
    },
    "two_tier_small.yaml": {
        "topology_files": {"topology.png"},
        "row_count": 96,
        "has_fabric_column": False,
    },
}


def test_example_expectations_cover_all_shipped_examples():
    example_files = {
        path.name for path in Path("configs/examples").glob("*.yaml") if path.is_file()
    }

    assert set(EXAMPLE_EXPECTATIONS) == example_files


@pytest.mark.parametrize(
    ("config_name", "expectations"),
    sorted(EXAMPLE_EXPECTATIONS.items()),
)
def test_shipped_example_configs_generate_expected_outputs(
    tmp_path,
    config_name,
    expectations,
):
    output_dir = tmp_path / config_name.removesuffix(".yaml")
    config_path = Path("configs/examples") / config_name

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

    actual_topology_files = {
        path.name for path in output_dir.glob("topology*.png") if path.is_file()
    }
    assert actual_topology_files == expectations["topology_files"]
    assert (output_dir / "port_mapping.xlsx").exists()
    assert (output_dir / "network_topology.log").exists()

    workbook = pd.read_excel(output_dir / "port_mapping.xlsx")
    assert len(workbook) == expectations["row_count"]
    assert ("fabric" in workbook.columns) is expectations["has_fabric_column"]
