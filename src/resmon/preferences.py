"""The Preferences dialog: overlay visibility, autostart, corner, and theme."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gtk

from . import autostart, overlay_control
from .paths import resmon_executable
from .settings import CORNERS, OVERLAY_STYLES, UPDATE_INTERVALS_MS, Settings
from .themes import THEME_IDS, THEME_LABELS

CORNER_LABELS = ["Top Right", "Top Left", "Bottom Right", "Bottom Left"]
STYLE_LABELS = ["Bars", "Percentages"]
INTERVAL_LABELS = ["1 second", "2 seconds", "5 seconds"]


class PreferencesDialog(Adw.PreferencesDialog):
    def __init__(self, settings: Settings, on_theme_changed: Callable[[], None] | None = None):
        super().__init__(title="Preferences")
        self._settings = settings
        self._executable = resmon_executable()
        self._on_theme_changed = on_theme_changed

        page = Adw.PreferencesPage()

        appearance = Adw.PreferencesGroup(
            title="Appearance",
            description="Applies to both the app and the overlay.",
        )
        theme_model = Gtk.StringList.new([THEME_LABELS[t] for t in THEME_IDS])
        self._theme_row = Adw.ComboRow(
            title="Theme",
            subtitle="Onyx restarts the overlay, if running, to apply",
            model=theme_model,
        )
        self._theme_row.set_selected(THEME_IDS.index(settings.get("theme")))
        self._theme_row.connect("notify::selected", self._on_theme_row_changed)
        appearance.add(self._theme_row)
        page.add(appearance)

        performance = Adw.PreferencesGroup(
            title="Performance",
            description="Lower uses less CPU; higher is more responsive.",
        )
        interval_model = Gtk.StringList.new(INTERVAL_LABELS)
        self._interval_row = Adw.ComboRow(
            title="Update Interval",
            subtitle="Restarts the overlay, if running; app takes it on next launch",
            model=interval_model,
        )
        self._interval_row.set_selected(UPDATE_INTERVALS_MS.index(settings.get("update_interval_ms")))
        self._interval_row.connect("notify::selected", self._on_interval_changed)
        performance.add(self._interval_row)
        page.add(performance)

        alerts = Adw.PreferencesGroup(
            title="Alerts",
            description="A desktop notification when a metric crosses a limit (checked wherever "
            "the app or overlay is running, at most once every 5 minutes per metric).",
        )
        self._alerts_row = Adw.SwitchRow(title="Enable Alerts")
        self._alerts_row.set_active(settings.get("alerts_enabled"))
        self._alerts_row.connect("notify::active", self._on_alerts_toggled)
        alerts.add(self._alerts_row)

        self._cpu_threshold_row = Adw.SpinRow.new_with_range(0, 100, 5)
        self._cpu_threshold_row.set_title("CPU Threshold")
        self._cpu_threshold_row.set_subtitle("% — 0 disables")
        self._cpu_threshold_row.set_value(settings.get("alert_cpu_percent"))
        self._cpu_threshold_row.connect("notify::value", self._on_cpu_threshold_changed)
        alerts.add(self._cpu_threshold_row)

        self._mem_threshold_row = Adw.SpinRow.new_with_range(0, 100, 5)
        self._mem_threshold_row.set_title("Memory Threshold")
        self._mem_threshold_row.set_subtitle("% — 0 disables")
        self._mem_threshold_row.set_value(settings.get("alert_mem_percent"))
        self._mem_threshold_row.connect("notify::value", self._on_mem_threshold_changed)
        alerts.add(self._mem_threshold_row)

        self._temp_threshold_row = Adw.SpinRow.new_with_range(0, 120, 5)
        self._temp_threshold_row.set_title("Temperature Threshold")
        self._temp_threshold_row.set_subtitle("°C — 0 disables")
        self._temp_threshold_row.set_value(settings.get("alert_temp_celsius"))
        self._temp_threshold_row.connect("notify::value", self._on_temp_threshold_changed)
        alerts.add(self._temp_threshold_row)

        page.add(alerts)

        group = Adw.PreferencesGroup(
            title="Desktop Overlay",
            description="A small always-on-top widget docked to a screen corner.",
        )

        self._overlay_row = Adw.SwitchRow(
            title="Show Overlay Now",
            subtitle="Toggle the corner widget for this session",
        )
        self._overlay_row.set_active(overlay_control.is_running())
        self._overlay_row.connect("notify::active", self._on_overlay_toggled)
        group.add(self._overlay_row)

        self._autostart_row = Adw.SwitchRow(
            title="Start at Login",
            subtitle="Launch the overlay automatically when you log in",
        )
        self._autostart_row.set_active(autostart.is_enabled())
        self._autostart_row.connect("notify::active", self._on_autostart_toggled)
        group.add(self._autostart_row)

        corner_model = Gtk.StringList.new(CORNER_LABELS)
        self._corner_row = Adw.ComboRow(title="Position", model=corner_model)
        self._corner_row.set_selected(CORNERS.index(settings.get("overlay_corner")))
        self._corner_row.connect("notify::selected", self._on_corner_changed)
        group.add(self._corner_row)

        style_model = Gtk.StringList.new(STYLE_LABELS)
        self._style_row = Adw.ComboRow(
            title="Style",
            subtitle="Bars show history; Percentages is a compact stat card",
            model=style_model,
        )
        self._style_row.set_selected(OVERLAY_STYLES.index(settings.get("overlay_style")))
        self._style_row.connect("notify::selected", self._on_style_changed)
        group.add(self._style_row)

        page.add(group)
        self.add(page)

    def _restart_overlay_if_running(self) -> None:
        if overlay_control.is_running():
            overlay_control.stop()
            overlay_control.start(self._executable)

    def _on_theme_row_changed(self, row: Adw.ComboRow, _pspec) -> None:
        theme = THEME_IDS[row.get_selected()]
        self._settings.set("theme", theme)
        if self._on_theme_changed is not None:
            self._on_theme_changed()
        self._restart_overlay_if_running()

    def _on_overlay_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        active = row.get_active()
        self._settings.set("overlay_enabled", active)
        if active:
            overlay_control.start(self._executable)
        else:
            overlay_control.stop()

    def _on_autostart_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        enabled = row.get_active()
        self._settings.set("autostart_enabled", enabled)
        autostart.set_enabled(enabled, self._executable)

    def _on_corner_changed(self, row: Adw.ComboRow, _pspec) -> None:
        corner = CORNERS[row.get_selected()]
        self._settings.set("overlay_corner", corner)
        self._restart_overlay_if_running()

    def _on_style_changed(self, row: Adw.ComboRow, _pspec) -> None:
        style = OVERLAY_STYLES[row.get_selected()]
        self._settings.set("overlay_style", style)
        self._restart_overlay_if_running()

    def _on_interval_changed(self, row: Adw.ComboRow, _pspec) -> None:
        interval_ms = UPDATE_INTERVALS_MS[row.get_selected()]
        self._settings.set("update_interval_ms", interval_ms)
        self._restart_overlay_if_running()

    def _on_alerts_toggled(self, row: Adw.SwitchRow, _pspec) -> None:
        self._settings.set("alerts_enabled", row.get_active())

    def _on_cpu_threshold_changed(self, row: Adw.SpinRow, _pspec) -> None:
        self._settings.set("alert_cpu_percent", int(row.get_value()))

    def _on_mem_threshold_changed(self, row: Adw.SpinRow, _pspec) -> None:
        self._settings.set("alert_mem_percent", int(row.get_value()))

    def _on_temp_threshold_changed(self, row: Adw.SpinRow, _pspec) -> None:
        self._settings.set("alert_temp_celsius", int(row.get_value()))
