import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
from topology_generator.argparser import parse_args

def test_parse_args_defaults():
    """Test the default values when no arguments are provided."""
    with patch('sys.argv', ['main.py']):
        with patch('topology_generator.argparser.get_timestamped_dir', return_value='output_test_dir'):
            args = parse_args()
            assert args.config == 'config.yaml'
            assert args.output_dir == 'output_test_dir'

def test_parse_args_custom():
    """Test with custom arguments."""
    with patch('sys.argv', ['main.py', '--config', 'custom_config.yaml', '--output-dir', 'custom_output']):
        with patch('topology_generator.argparser.get_timestamped_dir', return_value='custom_output_test_dir'):
            args = parse_args()
            assert args.config == 'custom_config.yaml'
            assert args.output_dir == 'custom_output_test_dir'
