import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
import networkx as nx
from topology_generator.topology_generator import generate_topology, add_network_layer, add_connections, calculate_port_stats

@patch('topology_generator.topology_generator.add_network_layer')
@patch('topology_generator.topology_generator.add_connections')
@patch('topology_generator.topology_generator.calculate_port_stats')
def test_generate_topology(mock_calculate_port_stats, mock_add_connections, mock_add_network_layer):
    """Test the generate_topology function with a simple configuration."""
    config = {
        "num_server": 4,
        "num_leaf": 2,
        "num_spine": 2,
        "num_core": 1,
        "server_port_bandwidth_gb": 10,
        "leaf_port_bandwidth_gb": 40,
        "spine_port_bandwidth_gb": 100,
        "core_port_bandwidth_gb": 100,
        "server_to_leaf_num_cables": 1,
        "server_to_leaf_cable_bandwidth_gb": 10,
        "leaf_to_spine_num_cables": 2,
        "leaf_to_spine_cable_bandwidth_gb": 40,
        "spine_to_core_num_cables": 2,
        "spine_to_core_cable_bandwidth_gb": 100
    }
    
    # Mock the return value of add_network_layer
    mock_graph = nx.Graph()
    mock_add_network_layer.return_value = mock_graph
    
    # Call the function
    topology = generate_topology(config)
    
    # Verify the function calls
    assert mock_add_network_layer.call_count >= 1
    assert mock_add_connections.call_count >= 1
    assert mock_calculate_port_stats.call_count == 1

def test_calculate_port_stats():
    """Test the calculate_port_stats function."""
    G = nx.Graph()
    G.add_node("server1", 
               type="server", 
               port_bandwidth_gb=10, 
               used_bandwidth_gb=20)
    
    calculate_port_stats(G)
    
    # Check that the used_ports_equivalent was calculated correctly
    assert G.nodes["server1"]["used_ports_equivalent"] == 2.0
