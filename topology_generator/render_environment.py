from __future__ import annotations

import importlib
import os
import tempfile
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any


def _directory_is_writable(path: Path) -> bool:
    try:
        path.mkdir(parents=True, exist_ok=True)
        probe_file = path / ".write_test"
        probe_file.write_text("ok", encoding="utf-8")
        probe_file.unlink()
        return True
    except OSError:
        return False


def _resolve_mpl_config_dir() -> Path | None:
    default_dir = Path.home() / ".matplotlib"
    if _directory_is_writable(default_dir):
        return None

    fallback_dir = Path(tempfile.gettempdir()) / "topology_generator_matplotlib"
    fallback_dir.mkdir(parents=True, exist_ok=True)
    return fallback_dir


def _should_use_agg_backend() -> bool:
    return not os.environ.get("DISPLAY") and not os.environ.get("WAYLAND_DISPLAY")


def ensure_matplotlib_environment() -> None:
    """Set safe Matplotlib defaults when the user has not provided them."""
    if "MPLCONFIGDIR" not in os.environ:
        fallback_dir = _resolve_mpl_config_dir()
        if fallback_dir is not None:
            os.environ["MPLCONFIGDIR"] = str(fallback_dir)

    if "MPLBACKEND" not in os.environ and _should_use_agg_backend():
        os.environ["MPLBACKEND"] = "Agg"


@dataclass(frozen=True)
class MatplotlibBindings:
    plt: Any
    Line2D: Any
    Patch: Any
    Arc: Any
    Rectangle: Any


@lru_cache(maxsize=1)
def load_matplotlib() -> MatplotlibBindings:
    """Import Matplotlib lazily after the environment is configured."""
    ensure_matplotlib_environment()

    plt = importlib.import_module("matplotlib.pyplot")
    line_2d = importlib.import_module("matplotlib.lines").Line2D
    patches = importlib.import_module("matplotlib.patches")
    return MatplotlibBindings(
        plt=plt,
        Line2D=line_2d,
        Patch=patches.Patch,
        Arc=patches.Arc,
        Rectangle=patches.Rectangle,
    )
