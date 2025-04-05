import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
from topology_generator.visualiser import visualize_topology

@patch('matplotlib.pyplot.savefig')
@patch('matplotlib.pyplot.figure')
@patch('topology_generator.visualiser.draw_condensed_layer')
def test_visualize_topology(mock_draw_condensed_layer, mock_figure, mock_savefig):
    """Test the visualize_topology function."""
    # Create a mock topology
    G = nx.Graph()
    G.add_node("server1", type="server", pos=(0, 0))
    G.add_node("leaf1", type="leaf", pos=(1, 1))
    G.add_edge("server1", "leaf1")
    
    # Mock the return value of draw_condensed_layer
    mock_draw_condensed_layer.return_value = (set(), [])
    
    # Test the function
    visualize_topology(G, "test_output_dir")
    
    # Check that savefig was called
    mock_savefig.assert_called()
