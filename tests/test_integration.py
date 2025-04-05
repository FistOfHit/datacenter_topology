import pytest
from unittest.mock import patch
import os
import sys

# Add the parent directory to the path so we can import the module
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Import the module to test
from topology_generator.main import main

@pytest.fixture
def setup_test_environment():
    """Set up the test environment."""
    # Create a test output directory
    os.makedirs("test_output", exist_ok=True)
    yield
    # Clean up
    if os.path.exists("test_output"):
        import shutil
        shutil.rmtree("test_output")

def test_main_integration(setup_test_environment):
    """Test the main function with a simple configuration."""
    # Create a test config file
    with open("test_config.yaml", "w") as f:
        f.write("""
num_server: 4
num_leaf: 2
num_spine: 2
num_core: 1
server_port_bandwidth_gb: 10
leaf_port_bandwidth_gb: 40
spine_port_bandwidth_gb: 100
core_port_bandwidth_gb: 100
server_to_leaf_num_cables: 1
server_to_leaf_cable_bandwidth_gb: 10
leaf_to_spine_num_cables: 2
leaf_to_spine_cable_bandwidth_gb: 40
spine_to_core_num_cables: 2
spine_to_core_cable_bandwidth_gb: 100
        """)
    
    # Mock the command line arguments
    with patch('sys.argv', ['main.py', '--config', 'test_config.yaml', '--output-dir', 'test_output']):
        # Run the main function
        try:
            main()
            # Check that the output files were created
            assert os.path.exists("test_output/topology.png")
            assert os.path.exists("test_output/port_mapping.csv")
            assert os.path.exists("test_output/port_mapping.xlsx")
            assert os.path.exists("test_output/topology.vdx")
        finally:
            # Clean up
            if os.path.exists("test_config.yaml"):
                os.remove("test_config.yaml")
