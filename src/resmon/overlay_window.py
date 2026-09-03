"""The floating overlay window: an always-on-top card with metric rows.

Right-click (on the card or the collapsed dot) opens a small menu to switch
corners or hide/show — both apply immediately, no need to open the full app.
"""

from __future__ import annotations

from pathlib import Path

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")
from gi.repository import Adw, Gdk, Gio, GLib, Gtk

try:
    gi.require_version("Gtk4LayerShell", "1.0")
    from gi.repository import Gtk4LayerShell as LayerShell

    HAS_LAYER_SHELL = True
except (ImportError, ValueError):
    HAS_LAYER_SHELL = False

from . import overlay_control
from .alerts import AlertChecker
from .metrics import Sampler, format_rate, format_temp
from .paths import resmon_executable
from .settings import CORNERS, Settings
from .themes import colors_for
from .widgets.metric_row import MetricRow

CORNER_LABELS = {
    "top-right": "Top Right",
    "top-left": "Top Left",
    "bottom-right": "Bottom Right",
    "bottom-left": "Bottom Left",
}

# (edge anchored to the near side, edge anchored to the far side)
CORNER_EDGES: dict[str, tuple] | None = None


def _corner_edges():
    global CORNER_EDGES
    if CORNER_EDGES is None:
        CORNER_EDGES = {
            "top-right": (LayerShell.Edge.TOP, LayerShell.Edge.RIGHT),
            "top-left": (LayerShell.Edge.TOP, LayerShell.Edge.LEFT),
            "bottom-right": (LayerShell.Edge.BOTTOM, LayerShell.Edge.RIGHT),
            "bottom-left": (LayerShell.Edge.BOTTOM, LayerShell.Edge.LEFT),
        }
    return CORNER_EDGES


class OverlayWindow(Gtk.ApplicationWindow):
    # Deliberately Gtk.ApplicationWindow, not Adw.ApplicationWindow: Adwaita's
    # adaptive-window machinery enforces its own minimum size, which fought
    # every attempt to size this down to a small collapsed dot. Nothing here
    # needs Adwaita chrome (no HeaderBar/ToolbarView) — it's all custom
    # content styled through style-*.css, so plain Gtk is the right base.
    def __init__(
        self,
        app: Adw.Application,
        *,
        windowed: bool = False,
        corner: str = "top-right",
        theme: str = "default",
        style: str = "bars",
        update_interval_ms: int = 2000,
        collapsed: bool = False,
    ):
        super().__init__(application=app)
        self.set_title("Resource Monitor")
        self.set_decorated(False)
        self.set_resizable(False)

        self._sampler = Sampler()
        self._alert_checker = AlertChecker(app)
        self._colors = colors_for(theme)
        self._show_graph = style != "percent"
        self._corner = corner
        self._collapsed = collapsed

        self._add_actions()
        self._load_css(theme)

        self._card = self._build_card()
        self._dot = self._build_dot()
        self._apply_collapsed_state()

        if HAS_LAYER_SHELL and not windowed:
            self._init_layer_shell(corner)

        self._tick()
        GLib.timeout_add(update_interval_ms, self._tick)

    def _add_actions(self) -> None:
        set_corner = Gio.SimpleAction.new("set-corner", GLib.VariantType.new("s"))
        set_corner.connect("activate", self._on_set_corner)
        self.add_action(set_corner)

        toggle_hidden = Gio.SimpleAction.new("toggle-hidden", None)
        toggle_hidden.connect("activate", self._on_toggle_hidden)
        self.add_action(toggle_hidden)

    def _build_card(self) -> Gtk.Widget:
        root = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10 if not self._show_graph else 14)
        root.add_css_class("resmon-card")
        root.set_margin_top(16)
        root.set_margin_bottom(16)
        root.set_margin_start(16)
        root.set_margin_end(16)
        self._add_context_menu(root)

        title = Gtk.Label(label="SYSTEM", xalign=0)
        title.add_css_class("resmon-title")
        root.append(title)

        kwargs = {"show_graph": self._show_graph}
        self.cpu_row = MetricRow("CPU", self._colors["cpu"], self._sampler.cpu_history, **kwargs)
        self.ram_row = MetricRow("MEM", self._colors["ram"], self._sampler.ram_history, **kwargs)
        self.disk_row = MetricRow("DISK", self._colors["disk"], self._sampler.disk_history, **kwargs)
        self.net_row = MetricRow("NET", self._colors["net"], self._sampler.net_history, **kwargs)

        self.gpu_row = None
        if self._sampler.gpu_available:
            self.gpu_row = MetricRow("GPU", self._colors["gpu"], self._sampler.gpu_history, **kwargs)

        self.temp_row = None
        if self._sampler.temp_available:
            self.temp_row = MetricRow("TEMP", self._colors["temp"], self._sampler.temp_history, **kwargs)

        for row in (self.cpu_row, self.ram_row, self.disk_row, self.net_row, self.gpu_row, self.temp_row):
            if row is not None:
                root.append(row)

        return root

    def _build_dot(self) -> Gtk.Widget:
        dot = Gtk.Button()
        dot.add_css_class("resmon-dot")
        dot.set_tooltip_text("Resource Monitor (click to show)")
        # CSS min-width/min-height alone isn't reliable against the theme's
        # own button sizing, so force it explicitly via the widget API too.
        dot.set_size_request(14, 14)
        dot.set_hexpand(False)
        dot.set_vexpand(False)
        dot.set_halign(Gtk.Align.CENTER)
        dot.set_valign(Gtk.Align.CENTER)
        dot.set_margin_top(8)
        dot.set_margin_bottom(8)
        dot.set_margin_start(8)
        dot.set_margin_end(8)
        dot.connect("clicked", lambda _b: self._set_collapsed(False))
        self._add_context_menu(dot)
        return dot

    def _add_context_menu(self, widget: Gtk.Widget) -> None:
        click = Gtk.GestureClick.new()
        click.set_button(3)  # secondary/right click
        click.connect("pressed", self._on_secondary_click)
        widget.add_controller(click)

    def _on_secondary_click(self, _gesture, _n_press: int, x: float, y: float) -> None:
        menu = Gio.Menu()

        positions = Gio.Menu()
        for c in CORNERS:
            item = Gio.MenuItem.new(CORNER_LABELS[c], None)
            item.set_action_and_target_value("win.set-corner", GLib.Variant.new_string(c))
            positions.append_item(item)
        menu.append_section("Position", positions)

        visibility = Gio.Menu()
        visibility.append("Show" if self._collapsed else "Hide", "win.toggle-hidden")
        menu.append_section(None, visibility)

        popover = Gtk.PopoverMenu.new_from_model(menu)
        popover.set_parent(self.get_child())
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        popover.set_pointing_to(rect)
        popover.popup()

    def _on_set_corner(self, _action, param: GLib.Variant) -> None:
        corner = param.get_string()
        if corner == self._corner:
            return
        settings = Settings()
        settings.set("overlay_corner", corner)
        self._restart_self()

    def _on_toggle_hidden(self, _action, _param) -> None:
        self._set_collapsed(not self._collapsed)

    def _set_collapsed(self, collapsed: bool) -> None:
        self._collapsed = collapsed
        Settings().set("overlay_collapsed", collapsed)
        self._apply_collapsed_state()

    def _apply_collapsed_state(self) -> None:
        # An explicit default-size dimension acts as a size *floor* — GTK
        # will grow past it for larger natural content, but never shrinks
        # below it. So the dot needs (-1, -1) here, not just a small content
        # widget, or it would keep the card's width even once collapsed.
        if self._collapsed:
            self.set_default_size(-1, -1)
            self.set_child(self._dot)
        else:
            self.set_default_size(230, -1)
            self.set_child(self._card)

    def _restart_self(self) -> None:
        """Applies a settings change by respawning a fresh overlay process.

        Layer-shell anchors are fixed at init, so there's no live way to
        re-anchor an already-mapped surface — a new process picks up the new
        settings from scratch. The new one starts before this one quits, so
        there's no visible gap.
        """
        overlay_control.respawn(resmon_executable())
        self.get_application().quit()

    def _init_layer_shell(self, corner: str) -> None:
        edges = _corner_edges().get(corner, _corner_edges()["top-right"])

        LayerShell.init_for_window(self)
        LayerShell.set_layer(self, LayerShell.Layer.OVERLAY)
        for edge in edges:
            LayerShell.set_anchor(self, edge, True)
            LayerShell.set_margin(self, edge, 16)
        LayerShell.set_keyboard_mode(self, LayerShell.KeyboardMode.NONE)
        LayerShell.set_namespace(self, "resmon")

    def _load_css(self, theme: str) -> None:
        css_path = Path(__file__).with_name(f"style-{theme}.css")
        if not css_path.exists():
            css_path = Path(__file__).with_name("style-default.css")
        provider = Gtk.CssProvider()
        provider.load_from_path(str(css_path))
        Gtk.StyleContext.add_provider_for_display(
            Gdk.Display.get_default(),
            provider,
            Gtk.STYLE_PROVIDER_PRIORITY_APPLICATION,
        )

    def _tick(self) -> bool:
        snap = self._sampler.sample()

        self.cpu_row.set_value_text(f"{snap.cpu:.0f}%")
        self.ram_row.set_value_text(f"{snap.ram:.0f}%")
        self.disk_row.set_value_text(f"{snap.disk:.0f}%")
        self.net_row.set_value_text(f"↓{format_rate(snap.net_down)}/s ↑{format_rate(snap.net_up)}/s")

        if self.gpu_row is not None:
            self.gpu_row.set_value_text(f"{snap.gpu:.0f}%" if snap.gpu is not None else "—")

        if self.temp_row is not None:
            self.temp_row.set_value_text(format_temp(snap.temp) if snap.temp is not None else "—")

        for row in (self.cpu_row, self.ram_row, self.disk_row, self.net_row, self.gpu_row, self.temp_row):
            if row is not None:
                row.redraw()

        self._alert_checker.check(snap.cpu, snap.ram, snap.temp)

        return True
