"""Start/stop the overlay as a detached subprocess, tracked via a PID file."""

from __future__ import annotations

import os
import signal
import subprocess

from .paths import OVERLAY_PID_FILE, RUNTIME_DIR


def _read_live_pid() -> int | None:
    try:
        pid = int(OVERLAY_PID_FILE.read_text().strip())
    except (FileNotFoundError, ValueError):
        return None

    try:
        os.kill(pid, 0)
    except ProcessLookupError:
        OVERLAY_PID_FILE.unlink(missing_ok=True)
        return None
    except PermissionError:
        return pid
    return pid


def is_running() -> bool:
    return _read_live_pid() is not None


def _spawn(executable: list[str]) -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    subprocess.Popen(
        [*executable, "--overlay"],
        start_new_session=True,
        stdin=subprocess.DEVNULL,
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )


def start(executable: list[str]) -> None:
    if is_running():
        return
    _spawn(executable)


def respawn(executable: list[str]) -> None:
    """Unconditionally spawn a new overlay, skipping the is_running() guard.

    For the overlay to restart *itself* (e.g. after changing settings that
    need a fresh process) — at the moment this runs the old process is still
    alive and still holds the PID file, so `start()`'s guard would refuse.
    """
    _spawn(executable)


def stop() -> None:
    pid = _read_live_pid()
    if pid is None:
        return
    try:
        os.kill(pid, signal.SIGTERM)
    except ProcessLookupError:
        pass
    OVERLAY_PID_FILE.unlink(missing_ok=True)


def write_pid() -> None:
    RUNTIME_DIR.mkdir(parents=True, exist_ok=True)
    OVERLAY_PID_FILE.write_text(str(os.getpid()))


def clear_pid() -> None:
    OVERLAY_PID_FILE.unlink(missing_ok=True)
