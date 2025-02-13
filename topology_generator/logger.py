import argparse
import logging
import sys
import os


def setup_logging(args: argparse.Namespace) -> logging.Logger:
    """
    Set up logging configuration with the provided output directory.

    Params:
        args: argparse.Namespace

    Returns:
        logging.Logger
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
