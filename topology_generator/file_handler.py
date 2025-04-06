from datetime import datetime
import os
from pathlib import Path
from typing import Dict, Any
import logging
import yaml


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


def load_config_from_file(config_path: str) -> Dict[str, Any]:
    """
    Load configuration from a YAML file.

    Args:
        config_path: The path to the YAML configuration file.

    Returns:
        The loaded configuration as a dictionary.

    Raises:
        FileNotFoundError: If the configuration file doesn't exist.
        yaml.YAMLError: If the YAML file has invalid syntax.
    """
    try:
        with open(config_path, "r") as f:
            return yaml.safe_load(f)
    except FileNotFoundError:
        logging.error(f"Configuration file not found: {config_path}")
        raise
    except yaml.YAMLError as e:
        logging.error(f"Invalid YAML in configuration file: {str(e)}")
        raise
