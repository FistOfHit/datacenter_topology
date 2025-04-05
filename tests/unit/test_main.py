import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
from topology_generator.main import main

@patch('topology_generator.main.generate_topology')
@patch('topology_generator.main.visualize_topology')
@patch('topology_generator.main.create_port_mapping')
@patch('topology_generator.main.save_to_csv')
@patch('topology_generator.main.save_to_excel')
@patch('topology_generator.main.export_network_to_vdx')
@patch('topology_generator.main.load_config_from_file')
@patch('topology_generator.main.parse_args')
@patch('topology_generator.main.setup_logging')
def test_main(mock_setup_logging, mock_parse_args, mock_load_config, 
              mock_export, mock_save_excel, mock_save_csv, 
              mock_create_mapping, mock_visualize, mock_generate):
    """Test the main function."""
    # Setup mocks
    mock_args = MagicMock()
    mock_args.config = 'config.yaml'
    mock_args.output_dir = 'output_dir'
    mock_parse_args.return_value = mock_args
    
    mock_logger = MagicMock()
    mock_setup_logging.return_value = mock_logger
    
    mock_config = {'key': 'value'}
    mock_load_config.return_value = mock_config
    
    mock_topology = MagicMock()
    mock_generate.return_value = mock_topology
    
    mock_port_mapping = [{'source': 'server1', 'target': 'leaf1'}]
    mock_create_mapping.return_value = mock_port_mapping
    
    # Call the function
    main()
    
    # Verify all the expected functions were called
    mock_parse_args.assert_called_once()
    mock_setup_logging.assert_called_once_with(mock_args)
    mock_load_config.assert_called_once_with(mock_args.config)
    mock_generate.assert_called_once_with(mock_config)
    mock_visualize.assert_called_once_with(mock_topology, mock_args.output_dir)
    mock_create_mapping.assert_called_once_with(mock_topology)
    mock_save_csv.assert_called_once_with(mock_port_mapping, mock_args.output_dir)
    mock_save_excel.assert_called_once_with(mock_port_mapping, mock_args.output_dir)
    mock_export.assert_called_once_with(mock_topology, mock_args.output_dir)
