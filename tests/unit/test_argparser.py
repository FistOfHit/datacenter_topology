import os
import sys
from unittest.mock import patch

# Add the parent directory to sys.path for module imports
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), "..")))

from topology_generator.argparser import parse_args


def test_parse_args_defaults():
    """
    Test the default values when no arguments are provided.

    Verifies that default config path and output directory are set correctly.
    """
    with patch("sys.argv", ["main.py"]):
        with patch(
            "topology_generator.argparser.get_timestamped_dir", return_value="output"
        ):
            args = parse_args()
            assert args.config == "config.yaml"
            assert args.output_dir == "output"


def test_parse_args_custom():
    """
    Test with custom command line arguments.

    Verifies that custom config path and output directory are properly parsed.
    """
    with patch(
        "sys.argv",
        ["main.py", "--config", "custom_config.yaml", "--output-dir", "custom_output"],
    ):
        with patch(
            "topology_generator.argparser.get_timestamped_dir",
            return_value="custom_output_test_dir",
        ):
            args = parse_args()
            assert args.config == "custom_config.yaml"
            assert args.output_dir == "custom_output"
