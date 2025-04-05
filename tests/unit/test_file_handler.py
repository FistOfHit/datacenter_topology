import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
import yaml
from topology_generator.file_handler import load_config_from_file

def test_load_config_from_file(tmp_path):
    # Create a temporary config file
    config_data = {
        "num_server": 10,
        "num_leaf": 2,
        "num_spine": 2,
        "num_core": 1,
        "server_to_leaf_num_cables": 1,
        "server_to_leaf_cable_bandwidth_gb": 10,
        "leaf_to_spine_num_cables": 2,
        "leaf_to_spine_cable_bandwidth_gb": 40,
        "spine_to_core_num_cables": 2,
        "spine_to_core_cable_bandwidth_gb": 100
    }
    
    config_file = tmp_path / "test_config.yaml"
    with open(config_file, "w") as f:
        yaml.dump(config_data, f)
    
    # Test loading the config
    loaded_config = load_config_from_file(str(config_file))
    
    # Verify the loaded config matches the original
    assert loaded_config == config_data

def test_load_config_from_nonexistent_file():
    # Test loading a non-existent file
    with pytest.raises(FileNotFoundError):
        load_config_from_file("nonexistent_file.yaml")
