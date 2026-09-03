"""The full System Monitor app's entry point."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, Gtk

from .main_window import MainWindow
from .paths import APP_ID
from .preferences import PreferencesDialog
from .settings import Settings

VERSION = "0.1.0"

# A light-touch reskin for surfaces we own (the metric/process cards), kept
# separate from Adwaita's own chrome so it can't clash across versions.
ONYX_APP_CSS = """
.onyx-surface {
    background-color: #0a0b0d;
    border: 1px solid rgba(70, 150, 255, 0.28);
}
"""


class MainApp(Adw.Application):
    def __init__(self):
        super().__init__(application_id=APP_ID)
        self.settings = Settings()
        self._window: MainWindow | None = None

        self._add_action("preferences", self._on_preferences)
        self._add_action("about", self._on_about)
        self._add_action("quit", lambda *_: self.quit())

        self.set_accels_for_action("app.preferences", ["<primary>comma"])
        self.set_accels_for_action("app.quit", ["<primary>q"])

        self._load_css()
        self.apply_theme()

    def _add_action(self, name: str, callback) -> None:
        action = Gio.SimpleAction.new(name, None)
        action.connect("activate", callback)
        self.add_action(action)

    def _load_css(self) -> None:
        provider = Gtk.CssProvider()
        provider.load_from_data(ONYX_APP_CSS.encode())
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def apply_theme(self) -> None:
        """Forces dark mode for the Onyx theme; live, no restart needed."""
        theme = self.settings.get("theme")
        scheme = Adw.ColorScheme.FORCE_DARK if theme == "onyx" else Adw.ColorScheme.DEFAULT
        Adw.StyleManager.get_default().set_color_scheme(scheme)

    def do_activate(self) -> None:
        if self._window is None:
            self._window = MainWindow(self)
        self._window.present()

    def _on_preferences(self, *_args) -> None:
        PreferencesDialog(self.settings, on_theme_changed=self.apply_theme).present(self._window)

    def _on_about(self, *_args) -> None:
        about = Adw.AboutDialog(
            application_name="Resource Monitor",
            application_icon=APP_ID,
            version=VERSION,
            comments="A clean, minimal system resource monitor with a matching desktop overlay widget.",
        )
        about.present(self._window)
