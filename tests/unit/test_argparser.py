from unittest.mock import patch

from topology_generator.argparser import parse_args


def test_parse_args_defaults():
    with patch("sys.argv", ["main.py"]):
        args = parse_args()

    assert args.config == "configs/examples/two_tier_small.yaml"
    assert args.output_dir == "output"
    assert args.timestamp is False


def test_parse_args_custom():
    with patch(
        "sys.argv",
        ["main.py", "--config", "custom_config.yaml", "--output-dir", "custom_output"],
    ):
        args = parse_args()

    assert args.config == "custom_config.yaml"
    assert args.output_dir == "custom_output"
    assert args.timestamp is False


def test_parse_args_applies_timestamp():
    with patch("sys.argv", ["main.py", "--timestamp", "--output-dir", "base_output"]):
        args = parse_args()

    assert args.output_dir == "base_output"
    assert args.timestamp is True


def test_parse_args_has_no_filesystem_side_effects(tmp_path):
    output_dir = tmp_path / "timestamped_output"

    with patch(
        "sys.argv",
        ["main.py", "--timestamp", "--output-dir", str(output_dir)],
    ):
        args = parse_args()

    assert args.output_dir == str(output_dir)
    assert args.timestamp is True
    assert not output_dir.exists()
