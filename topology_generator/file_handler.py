import logging
import os
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from topology_generator.config_schema import TopologyConfig

logger = logging.getLogger(__name__)


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
        with Path(config_path).open("r", encoding="utf-8") as f:
            raw_config: Any = yaml.safe_load(f)
            return TopologyConfig.from_mapping(raw_config)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", config_path)
        raise
    except yaml.YAMLError as e:
        logger.error("Invalid YAML in configuration file: %s", str(e))
        raise
