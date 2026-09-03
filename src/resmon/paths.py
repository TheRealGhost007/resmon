"""Central XDG path resolution and the installed-executable lookup.

Plain stdlib env-var lookups rather than GLib — this module has no reason to
require PyGObject just to resolve a couple of directories, and staying
GTK-free keeps it (and settings.py, which depends on it) importable and
testable without a display or GTK installed at all.
"""

from __future__ import annotations

import os
import shutil
import sys
from pathlib import Path

APP_ID = "dev.local.Resmon"
OVERLAY_APP_ID = "dev.local.Resmon.Overlay"


def _xdg_config_home() -> Path:
    return Path(os.environ.get("XDG_CONFIG_HOME") or Path.home() / ".config")


def _xdg_runtime_dir() -> Path:
    value = os.environ.get("XDG_RUNTIME_DIR")
    return Path(value) if value else Path(f"/run/user/{os.getuid()}")


CONFIG_DIR = _xdg_config_home() / "resmon"
SETTINGS_FILE = CONFIG_DIR / "settings.json"

RUNTIME_DIR = _xdg_runtime_dir() / "resmon"
OVERLAY_PID_FILE = RUNTIME_DIR / "overlay.pid"

AUTOSTART_DIR = _xdg_config_home() / "autostart"
AUTOSTART_FILE = AUTOSTART_DIR / f"{OVERLAY_APP_ID}.desktop"


def resmon_executable() -> list[str]:
    """The command to re-invoke this program, for spawning the overlay or writing desktop files.

    Prefers the `bin/resmon` wrapper (installed on PATH, or found relative to
    this checkout) over a bare `python3 -m resmon`, since the wrapper carries
    the LD_PRELOAD fix gtk4-layer-shell needs to anchor as a real overlay
    instead of silently falling back to a floating window.
    """
    installed = shutil.which("resmon")
    if installed:
        return [installed]

    wrapper = Path(__file__).resolve().parents[2] / "bin" / "resmon"
    if wrapper.exists():
        return [str(wrapper)]

    return [sys.executable, "-m", "resmon"]
