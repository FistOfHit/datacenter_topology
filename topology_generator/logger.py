import argparse
import logging
import sys
import os


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
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s - %(levelname)s - %(message)s",
        handlers=[
            logging.StreamHandler(sys.stdout),
            logging.FileHandler(
                os.path.join(args.output_dir, "network_topology.log"), mode="w"
            ),
        ],
    )

    return logging.getLogger(__name__)
