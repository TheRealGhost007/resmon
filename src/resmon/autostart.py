"""Manage the XDG autostart entry that launches the overlay at login.

Login sessions here run `xdg-desktop-autostart.target`, which turns
`~/.config/autostart/*.desktop` files into systemd units automatically, so a
plain desktop-file drop is enough — no compositor-specific wiring needed.
"""

from __future__ import annotations

from .paths import AUTOSTART_DIR, AUTOSTART_FILE

_ENTRY = """[Desktop Entry]
Type=Application
Name=Resource Monitor Overlay
Comment=Docks the resource monitor widget to a screen corner at login
Exec={exec_line}
NoDisplay=true
X-GNOME-Autostart-enabled=true
"""


def is_enabled() -> bool:
    return AUTOSTART_FILE.exists()


def set_enabled(enabled: bool, executable: list[str]) -> None:
    if not enabled:
        AUTOSTART_FILE.unlink(missing_ok=True)
        return

    AUTOSTART_DIR.mkdir(parents=True, exist_ok=True)
    exec_line = " ".join([*executable, "--overlay"])
    AUTOSTART_FILE.write_text(_ENTRY.format(exec_line=exec_line))
