import argparse
import logging
import sys
import os

from topology_generator.file_handler import ensure_output_dir


LOGGER_NAME = "topology_generator"


def setup_logging(args: argparse.Namespace) -> logging.Logger:
    """
    Set up logging configuration for the application.

    Configures logging to output to both console and a log file in the
    specified output directory.

    Args:
        args: Command line arguments containing output_dir.

    Returns:
        logging.Logger: Configured logger instance.
    """
    output_dir = ensure_output_dir(args.output_dir)
    logger = logging.getLogger(LOGGER_NAME)
    logger.setLevel(logging.INFO)
    logger.propagate = False

    for handler in list(logger.handlers):
        handler.close()
        logger.removeHandler(handler)

    formatter = logging.Formatter("%(asctime)s - %(levelname)s - %(message)s")

    stream_handler = logging.StreamHandler(sys.stdout)
    stream_handler.setFormatter(formatter)

    file_handler = logging.FileHandler(
        os.path.join(output_dir, "network_topology.log"),
        mode="w",
    )
    file_handler.setFormatter(formatter)

    logger.addHandler(stream_handler)
    logger.addHandler(file_handler)
    return logger
