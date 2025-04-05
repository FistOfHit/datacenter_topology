import os
import sys

# Add the parent directory to the path so we can import the modules
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '..')))

import pytest
from unittest.mock import patch, MagicMock
from topology_generator.logger import setup_logging

def test_setup_logging():
    """Test the setup_logging function."""
    # Mock the args
    args = MagicMock()
    args.output_dir = "test_output_dir"
    
    # Create the directory if it doesn't exist
    os.makedirs(args.output_dir, exist_ok=True)
    
    # Test the function
    logger = setup_logging(args)
    
    # Check that the logger was created
    assert logger is not None
    
    # Clean up
    if os.path.exists(args.output_dir):
        import shutil
        shutil.rmtree(args.output_dir)
