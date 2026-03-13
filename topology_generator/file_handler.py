from datetime import datetime
import os
from pathlib import Path
from typing import Any
import logging
import yaml

from topology_generator.config_schema import TopologyConfig


def get_timestamped_dir(base_dir: str) -> str:
    """
    Create and return a timestamped subdirectory within the base directory.

    Args:
        base_dir: The base directory to create the timestamped subdirectory in.

    Returns:
        The path to the timestamped subdirectory.
    """
    # Create timestamp string in format: YYYYMMDD_HHMMSS
    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    output_dir = os.path.join(base_dir, timestamp)

    # Create directory if it doesn't exist
    Path(output_dir).mkdir(parents=True, exist_ok=True)

    return output_dir


def ensure_output_dir(output_dir: str) -> Path:
    """Create the output directory if needed and return it as a path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def load_config_from_file(config_path: str) -> TopologyConfig:
    """
    Load and validate configuration from a YAML file.

    Args:
        config_path: The path to the YAML configuration file.

    Returns:
        The validated configuration model.

    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
        yaml.YAMLError: If the YAML file has invalid syntax.
    """
    try:
        with open(config_path, "r") as f:
            raw_config: Any = yaml.safe_load(f)
            return TopologyConfig.from_mapping(raw_config)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Invalid YAML in configuration file: {str(e)}")
        raise
