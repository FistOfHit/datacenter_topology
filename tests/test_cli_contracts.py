import os
import subprocess
import sys
from pathlib import Path


REPO_ROOT = Path(__file__).resolve().parents[1]


def _run_command(*args: str) -> subprocess.CompletedProcess[str]:
    return subprocess.run(
        args,
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
    )


def test_module_entrypoint_generates_outputs(tmp_path):
    output_dir = tmp_path / "module_entrypoint_output"

    result = _run_command(
        sys.executable,
        "-m",
        "topology_generator",
        "--config",
        "configs/examples/two_tier_small.yaml",
        "--output-dir",
        str(output_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert (output_dir / "topology.png").exists()
    assert (output_dir / "port_mapping.xlsx").exists()
    assert (output_dir / "network_topology.log").exists()


def test_module_help_does_not_create_output_directory(tmp_path):
    output_dir = tmp_path / "help_output"

    result = _run_command(
        sys.executable,
        "-m",
        "topology_generator",
        "--help",
        "--output-dir",
        str(output_dir),
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Network Topology Generator" in result.stdout
    assert not output_dir.exists()


def test_console_script_help_exits_successfully():
    script_path = Path(sys.executable).parent / "topology-generator"

    result = _run_command(str(script_path), "--help")

    assert result.returncode == 0, result.stdout + result.stderr
    assert "Network Topology Generator" in result.stdout


def test_importing_main_module_does_not_set_matplotlib_environment():
    env = dict(os.environ)
    env.pop("MPLCONFIGDIR", None)
    env.pop("MPLBACKEND", None)

    result = subprocess.run(
        [
            sys.executable,
            "-c",
            (
                "import json, os; "
                "import topology_generator.main; "
                "print(json.dumps({"
                "'MPLCONFIGDIR': os.environ.get('MPLCONFIGDIR'), "
                "'MPLBACKEND': os.environ.get('MPLBACKEND')"
                "}))"
            ),
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
        check=False,
        env=env,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    assert result.stdout.strip() == '{"MPLCONFIGDIR": null, "MPLBACKEND": null}'
