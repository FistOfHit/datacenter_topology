import logging
from datetime import datetime
from os import PathLike
from pathlib import Path
from typing import Any

import yaml

from topology_generator.config_types import InvalidTopologyConfig, TopologyConfig

logger = logging.getLogger(__name__)


def resolve_output_dir(base_dir: str | PathLike[str], timestamp: bool) -> Path:
    """Resolve the final output directory path without creating it."""
    output_path = Path(base_dir)
    if not timestamp:
        return output_path

    timestamp_dir = datetime.now().strftime("%Y%m%d_%H%M%S")
    return output_path / timestamp_dir


def ensure_output_dir(output_dir: str | PathLike[str]) -> Path:
    """Create the output directory if needed and return it as a path."""
    output_path = Path(output_dir)
    output_path.mkdir(parents=True, exist_ok=True)
    return output_path


def load_config_from_file(config_path: str | PathLike[str]) -> TopologyConfig:
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
    config_file = Path(config_path)
    try:
        with config_file.open("r", encoding="utf-8") as f:
            raw_config: Any = yaml.safe_load(f)
            return TopologyConfig.from_mapping(raw_config)
    except FileNotFoundError:
        logger.error("Configuration file not found: %s", config_file)
        raise
    except yaml.YAMLError as exc:
        logger.error(
            "Invalid YAML in configuration file %s: %s",
            config_file,
            str(exc),
        )
        raise
    except InvalidTopologyConfig as exc:
        logger.error(
            "Invalid topology configuration in %s: %s",
            config_file,
            str(exc),
        )
        raise
