import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from unittest.mock import patch, MagicMock
import networkx as nx
from topology_generator.graph_exporter import export_network_to_vdx


@patch("builtins.open", new_callable=MagicMock)
def test_export_network_to_vdx(mock_open):
    """Test the export_network_to_vdx function."""
    # Create a mock topology with all required attributes
    G = nx.Graph()

    # Test the function directly without mocking it
    export_network_to_vdx(G, "test_output_dir")

    # Check that open was called
    mock_open.assert_called()
