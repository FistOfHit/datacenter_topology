import argparse
from topology_generator.file_handler import get_timestamped_dir


def parse_args():
    """
    Parse command line arguments for the Network Topology Generator.

    Returns:
        argparse.Namespace: Parsed command line arguments.
    """
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

    parser.add_argument(
        "--timestamp",
        action="store_true",
        help="Add timestamp to output directory",
    )

    args = parser.parse_args()

    # Apply timestamp to output directory if requested
    if args.timestamp:
        args.output_dir = get_timestamped_dir(args.output_dir)

    return args
