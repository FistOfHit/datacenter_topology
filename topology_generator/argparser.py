import argparse
import os
from datetime import datetime
from topology_generator.file_handler import get_timestamped_dir

def parse_args():
    parser = argparse.ArgumentParser(description="Network Topology Generator")
    parser.add_argument(
        "--config",
        type=str,
        default="config.yaml",
        help="Path to configuration YAML file",
    )
    parser.add_argument(
        "--output-dir",
        type=str,
        default="output",
        help="Base output directory for generated files",
    )
    args = parser.parse_args()
    args.output_dir = get_timestamped_dir(args.output_dir)
    return args
