"""The full System Monitor app window: sidebar nav across Overview,
Processes, and System Info."""

from __future__ import annotations

from typing import Callable

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gio, GLib, Gtk

from .alerts import AlertChecker
from .metrics import Sampler, format_rate, format_temp
from .process_list import ProcessListView
from .system_info_page import SystemInfoPage
from .themes import colors_for
from .widgets.graph import CoreBars
from .widgets.metric_row import MetricRow

NAV_ITEMS = [
    ("overview", "Overview", "view-grid-symbolic"),
    ("processes", "Processes", "view-list-symbolic"),
    ("system-info", "System Info", "dialog-information-symbolic"),
]


def _card(*widgets: Gtk.Widget, onyx: bool = False) -> Gtk.Widget:
    card = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
    card.add_css_class("card")
    if onyx:
        card.add_css_class("onyx-surface")

    inner = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=14)
    inner.set_margin_top(16)
    inner.set_margin_bottom(16)
    inner.set_margin_start(16)
    inner.set_margin_end(16)

    for widget in widgets:
        inner.append(widget)

    card.append(inner)
    return card


class OverviewPage(Gtk.ScrolledWindow):
    def __init__(self, sampler: Sampler, theme: str = "default"):
        super().__init__()
        self.set_vexpand(True)
        onyx = theme == "onyx"
        colors = colors_for(theme)

        clamp = Adw.Clamp(maximum_size=760, tightening_threshold=560)
        box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=16)
        box.set_margin_top(20)
        box.set_margin_bottom(20)
        box.set_margin_start(16)
        box.set_margin_end(16)

        # CPU gets a full-width "hero" card since it also carries per-core detail.
        self.cpu_row = MetricRow("CPU", colors["cpu"], sampler.cpu_history, big=True, graph_style="area")
        self.core_bars = CoreBars(colors["cpu"])
        core_label = Gtk.Label(label="Per Core", xalign=0)
        core_label.add_css_class("dim-label")
        core_label.add_css_class("caption")
        box.append(_card(self.cpu_row, core_label, self.core_bars, onyx=onyx))

        # Everything else is a compact tile in a responsive grid.
        grid = Gtk.FlowBox()
        grid.set_selection_mode(Gtk.SelectionMode.NONE)
        grid.set_homogeneous(True)
        grid.set_column_spacing(16)
        grid.set_row_spacing(16)
        grid.set_min_children_per_line(1)
        grid.set_max_children_per_line(2)

        self.ram_row = MetricRow("Memory", colors["ram"], sampler.ram_history, big=True, graph_style="area")
        self.disk_row = MetricRow("Disk", colors["disk"], sampler.disk_history, big=True, graph_style="area")
        self.diskio_row = MetricRow(
            "Disk I/O", colors["diskio"], sampler.diskio_history, big=True, graph_style="area", stack_value=True
        )
        self.net_row = MetricRow(
            "Network", colors["net"], sampler.net_history, big=True, graph_style="area", stack_value=True
        )

        for row in (self.ram_row, self.disk_row, self.diskio_row, self.net_row):
            grid.append(_card(row, onyx=onyx))

        self.gpu_row = None
        if sampler.gpu_available:
            self.gpu_row = MetricRow("GPU", colors["gpu"], sampler.gpu_history, big=True, graph_style="area")
            grid.append(_card(self.gpu_row, onyx=onyx))

        self.temp_row = None
        if sampler.temp_available:
            self.temp_row = MetricRow(
                "Temperature", colors["temp"], sampler.temp_history, big=True, graph_style="area"
            )
            grid.append(_card(self.temp_row, onyx=onyx))

        box.append(grid)

        clamp.set_child(box)
        self.set_child(clamp)

    def update(self, sampler: Sampler):
        snap = sampler.sample()

        self.cpu_row.set_value_text(f"{snap.cpu:.0f}%")
        self.ram_row.set_value_text(f"{snap.ram:.0f}%")
        self.disk_row.set_value_text(f"{snap.disk:.0f}%")
        self.diskio_row.set_value_text(f"↓{format_rate(snap.disk_read)}/s ↑{format_rate(snap.disk_write)}/s")
        self.net_row.set_value_text(f"↓{format_rate(snap.net_down)}/s ↑{format_rate(snap.net_up)}/s")

        if self.gpu_row is not None:
            self.gpu_row.set_value_text(f"{snap.gpu:.0f}%" if snap.gpu is not None else "—")

        if self.temp_row is not None:
            self.temp_row.set_value_text(format_temp(snap.temp) if snap.temp is not None else "—")

        for row in (self.cpu_row, self.ram_row, self.disk_row, self.diskio_row, self.net_row, self.gpu_row, self.temp_row):
            if row is not None:
                row.redraw()

        self.core_bars.set_values(sampler.cpu_percpu)
        return snap


class _Sidebar(Gtk.Box):
    def __init__(self, stack: Adw.ViewStack, on_select: Callable[[str], None]):
        super().__init__(orientation=Gtk.Orientation.VERTICAL)
        self.set_size_request(180, -1)

        self._stack = stack
        self._on_select = on_select
        self._info_by_row: dict[Gtk.ListBoxRow, tuple[str, str]] = {}

        listbox = Gtk.ListBox()
        listbox.add_css_class("navigation-sidebar")
        listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)

        first_row = None
        for name, label, icon in NAV_ITEMS:
            row = Gtk.ListBoxRow()
            content = Gtk.Box(orientation=Gtk.Orientation.HORIZONTAL, spacing=12)
            content.set_margin_top(10)
            content.set_margin_bottom(10)
            content.set_margin_start(14)
            content.set_margin_end(14)
            content.append(Gtk.Image.new_from_icon_name(icon))
            content.append(Gtk.Label(label=label, xalign=0))
            row.set_child(content)
            listbox.append(row)
            self._info_by_row[row] = (name, label)
            if first_row is None:
                first_row = row

        listbox.connect("row-selected", self._on_row_selected)
        self.append(listbox)
        listbox.select_row(first_row)

    def _on_row_selected(self, _list: Gtk.ListBox, row: Gtk.ListBoxRow | None) -> None:
        if row is None:
            return
        info = self._info_by_row.get(row)
        if info is None:
            return
        name, label = info
        self._stack.set_visible_child_name(name)
        self._on_select(label)


class MainWindow(Adw.ApplicationWindow):
    def __init__(self, app: Adw.Application):
        super().__init__(application=app)
        self.set_title("System Monitor")
        self.set_default_size(860, 660)

        self._sampler = Sampler(history_len=90)
        self._alert_checker = AlertChecker(app)
        theme = app.settings.get("theme")
        onyx = theme == "onyx"
        interval_ms = app.settings.get("update_interval_ms")

        self._stack = Adw.ViewStack()
        self._overview = OverviewPage(self._sampler, theme=theme)
        self._processes = ProcessListView(onyx=onyx)
        self._system_info = SystemInfoPage(onyx=onyx)

        self._stack.add_named(self._overview, "overview")
        self._stack.add_named(self._processes, "processes")
        self._stack.add_named(self._system_info, "system-info")

        self._window_title = Adw.WindowTitle(title="Overview")
        sidebar = _Sidebar(self._stack, on_select=self._window_title.set_title)

        header = Adw.HeaderBar()
        header.set_title_widget(self._window_title)

        menu_button = Gtk.MenuButton(icon_name="open-menu-symbolic")
        menu = Gio.Menu()
        menu.append("Preferences", "app.preferences")
        menu.append("About Resource Monitor", "app.about")
        menu_button.set_menu_model(menu)
        header.pack_end(menu_button)

        toolbar_view = Adw.ToolbarView()
        toolbar_view.add_top_bar(header)
        toolbar_view.set_content(self._stack)

        split_view = Adw.OverlaySplitView()
        split_view.set_sidebar(sidebar)
        split_view.set_content(toolbar_view)
        split_view.set_sidebar_width_fraction(0.24)
        split_view.set_min_sidebar_width(180)
        split_view.set_max_sidebar_width(240)
        split_view.set_pin_sidebar(True)

        self.set_content(split_view)

        self._overview.update(self._sampler)
        GLib.timeout_add(interval_ms, self._tick_metrics)
        GLib.timeout_add(interval_ms, self._tick_processes)

    def _tick_metrics(self) -> bool:
        snap = self._overview.update(self._sampler)
        self._alert_checker.check(snap.cpu, snap.ram, snap.temp)
        return True

    def _tick_processes(self) -> bool:
        # Scanning every process is the single most expensive thing this app
        # does; skip it entirely unless that tab is actually on screen.
        if self._stack.get_visible_child_name() == "processes":
            self._processes.refresh()
        return True
