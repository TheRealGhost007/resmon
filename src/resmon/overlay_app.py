"""The overlay's application entry point: a standalone, single-window app."""

from __future__ import annotations

import signal

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, GLib

from . import overlay_control
from .overlay_window import OverlayWindow
from .paths import OVERLAY_APP_ID
from .settings import Settings


class OverlayApp(Adw.Application):
    def __init__(self, windowed: bool = False):
        super().__init__(application_id=OVERLAY_APP_ID)
        self._windowed = windowed
        self._window: OverlayWindow | None = None

    def do_activate(self) -> None:
        if self._window is None:
            settings = Settings()
            self._window = OverlayWindow(
                self,
                windowed=self._windowed,
                corner=settings.get("overlay_corner"),
                theme=settings.get("theme"),
                style=settings.get("overlay_style"),
                update_interval_ms=settings.get("update_interval_ms"),
                collapsed=settings.get("overlay_collapsed"),
            )
            overlay_control.write_pid()
            GLib.unix_signal_add(GLib.PRIORITY_DEFAULT, signal.SIGTERM, self._on_sigterm)
        self._window.present()

    def _on_sigterm(self) -> bool:
        overlay_control.clear_pid()
        self.quit()
        return GLib.SOURCE_REMOVE

    def do_shutdown(self) -> None:
        overlay_control.clear_pid()
        Adw.Application.do_shutdown(self)
