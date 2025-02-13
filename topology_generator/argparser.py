import argparse

from file_handler import get_timestamped_dir


def parse_args():
    parser = argparse.ArgumentParser(description="Network Topology Generator")

    parser.add_argument(
        "--config",
        type=str,
        required=True,
        help="Path to configuration JSON file",
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
