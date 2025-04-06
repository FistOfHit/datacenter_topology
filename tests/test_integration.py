import pytest
import os
import sys
import shutil
from unittest.mock import patch

# Add parent directory to sys.path for module imports
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from topology_generator.main import main


@pytest.fixture
def setup_test_environment():
    """
    Set up the test environment for integration tests.

    Creates necessary test directories and cleans up after tests complete.
    """
    # Create a test output directory
    os.makedirs("test_output", exist_ok=True)

    yield

    # Clean up after test
    if os.path.exists("test_output"):
        shutil.rmtree("test_output")


def test_main_integration(setup_test_environment):
    """
    Integration test for the main application workflow.

    Tests the entire pipeline from configuration loading to output generation.
    Verifies all expected output files are created.
    """
    # Mock command line arguments
    with patch(
        "sys.argv",
        [
            "main.py",
            "--config",
            "tests/test_config.yaml",
            "--output-dir",
            "test_output",
        ],
    ):
        # Run the main function
        main()

        # Verify expected output files were created
        assert os.path.exists("test_output/topology.png")
        assert os.path.exists("test_output/port_mapping.csv")
        assert os.path.exists("test_output/port_mapping.xlsx")
        assert os.path.exists("test_output/topology.vdx")
