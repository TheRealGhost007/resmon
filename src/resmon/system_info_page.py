"""A static-info reference page: hostname, kernel, hardware, network."""

from __future__ import annotations

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
gi.require_version("Pango", "1.0")
from gi.repository import Adw, GLib, Gtk, Pango

from . import system_info

REFRESH_INTERVAL_MS = 60_000  # only uptime actually changes; no need for more


def _info_row(name: str) -> tuple[Gtk.Widget, Gtk.Label]:
    row = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)

    name_label = Gtk.Label(label=name, xalign=0)
    name_label.add_css_class("dim-label")
    row.append(name_label)

    value_label = Gtk.Label(xalign=1, hexpand=True, wrap=False)
    value_label.set_max_width_chars(1)
    value_label.set_ellipsize(Pango.EllipsizeMode.END)
    value_label.add_css_class("numeric")
    row.append(value_label)

    return row, value_label


def _card(title: str, *rows: Gtk.Widget, onyx: bool = False) -> Gtk.Widget:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("card")
    if onyx:
        card.add_css_class("onyx-surface")

    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
    inner.set_margin_top(16)
    inner.set_margin_bottom(16)
    inner.set_margin_start(16)
    inner.set_margin_end(16)

    heading = Gtk.Label(label=title, xalign=0)
    heading.add_css_class("heading")
    inner.append(heading)

    for row in rows:
        inner.append(row)

    card.append(inner)
    return card


class SystemInfoPage(Gtk.ScrolledWindow):
    def __init__(self, *, onyx: bool = False):
        super().__init__()
        self.set_vexpand(True)

        clamp = Adw.Clamp(maximum_size=680, tightening_threshold=520)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        self._values: dict[str, Gtk.Label] = {}

        system_rows = []
        for key, label in [
            ("hostname", "Hostname"),
            ("distro", "Distribution"),
            ("kernel", "Kernel"),
            ("architecture", "Architecture"),
            ("uptime", "Uptime"),
            ("boot_time", "Booted"),
        ]:
            row, value = _info_row(label)
            self._values[key] = value
            system_rows.append(row)
        box.append(_card("System", *system_rows, onyx=onyx))

        hardware_rows = []
        for key, label in [
            ("cpu_model", "Processor"),
            ("cpu_cores", "Cores"),
            ("total_ram", "Memory"),
            ("total_disk", "Disk"),
        ]:
            row, value = _info_row(label)
            self._values[key] = value
            hardware_rows.append(row)
        box.append(_card("Hardware", *hardware_rows, onyx=onyx))

        net_row, net_value = _info_row("IP Address")
        self._values["ip_address"] = net_value
        box.append(_card("Network", net_row, onyx=onyx))

        clamp.set_child(box)
        self.set_child(clamp)

        self.refresh()
        GLib.timeout_add(REFRESH_INTERVAL_MS, self._on_tick)

    def refresh(self) -> None:
        info = system_info.gather()
        for key, label in self._values.items():
            label.set_label(str(getattr(info, key)))

    def _on_tick(self) -> bool:
        self.refresh()
        return True
