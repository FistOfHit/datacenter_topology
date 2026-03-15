import argparse


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
        default="configs/examples/two_tier_small.yaml",
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

    return parser.parse_args()
