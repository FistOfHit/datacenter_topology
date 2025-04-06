import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
import pandas as pd
from topology_generator.port_mapper import (
    create_port_mapping,
    save_to_csv,
    save_to_excel,
)


@patch("pandas.DataFrame")
def test_create_port_mapping(mock_dataframe):
    """Test the create_port_mapping function."""
    # Create a mock topology
    G = MagicMock()

    # Mock the edges method to return a list of edges with data
    G.edges.return_value = [
        (
            "server1",
            "leaf1",
            {"source_ports": [0], "target_ports": [0], "cable_bandwidth_gb": 10},
        )
    ]

    # Mock the nodes method to return node data
    G.nodes.return_value = {"server1": {"type": "server"}, "leaf1": {"type": "leaf"}}

    # Call the function
    create_port_mapping(G)

    # Verify DataFrame was created
    mock_dataframe.assert_called()


def test_save_to_csv():
    """Test the save_to_csv function."""
    # Create a mock port mapping DataFrame
    df = pd.DataFrame(
        [
            {
                "source": "server1",
                "source_port": 0,
                "target": "leaf1",
                "target_port": 0,
                "bandwidth_gb": 10,
            }
        ]
    )

    # Mock the to_csv method
    with patch.object(pd.DataFrame, "to_csv") as mock_to_csv:
        # Test the function
        save_to_csv(df, "test_output_dir")

        # Check that to_csv was called
        mock_to_csv.assert_called_once()


def test_save_to_excel():
    """Test the save_to_excel function."""
    # Create a mock port mapping DataFrame
    df = pd.DataFrame(
        [
            {
                "source": "server1",
                "source_port": 0,
                "target": "leaf1",
                "target_port": 0,
                "bandwidth_gb": 10,
            }
        ]
    )

    # Mock the to_excel method
    with patch.object(pd.DataFrame, "to_excel") as mock_to_excel:
        # Test the function
        save_to_excel(df, "test_output_dir")

        # Check that to_excel was called
        mock_to_excel.assert_called_once()
