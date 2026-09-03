"""A labeled metric row: name, live value, and (optionally) a history graph."""

from __future__ import annotations

from collections import deque

import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Pango", "1.0")
from gi.repository import Gtk, Pango

from .graph import AreaGraph, BarGraph, Color


class MetricRow(Gtk.Box):
    def __init__(
        self,
        name: str,
        color: Color,
        history: deque[float],
        max_value: float = 100.0,
        *,
        big: bool = False,
        show_graph: bool = True,
        graph_style: str = "bars",
        stack_value: bool = False,
    ):
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=8 if big else 5)
        self.add_css_class("metric-row")

        # stack_value puts the value on its own line under the name instead
        # of sharing a row with it — needed once a tile gets narrow enough
        # that a two-part value (like "↓1.4MB/s ↑5.2MB/s") won't fit beside
        # the name without ellipsizing.
        header = Gtk.Box(
            orientation=Gtk.Orientation.VERTICAL if stack_value else Gtk.Orientation.HORIZONTAL,
            spacing=2 if stack_value else 6,
        )

        name_label = Gtk.Label(label=name, xalign=0)
        name_label.add_css_class("heading" if big else "metric-name")
        header.append(name_label)

        self.value_label = Gtk.Label(label="—", xalign=0 if stack_value else 1, hexpand=True)
        # Without a capped natural width, a label demands room for its full
        # text and forces the (fixed-width, non-resizable) overlay window to
        # grow instead of truncating — this is what actually keeps it fitting.
        self.value_label.set_max_width_chars(1)
        self.value_label.set_ellipsize(Pango.EllipsizeMode.END)
        self.value_label.add_css_class("numeric" if big else "metric-value")
        if big:
            self.value_label.add_css_class("title-2")
        elif not show_graph:
            self.value_label.add_css_class("metric-value-large")
        header.append(self.value_label)

        self.append(header)

        self.graph: BarGraph | AreaGraph | None = None
        if show_graph:
            graph_cls = AreaGraph if graph_style == "area" else BarGraph
            self.graph = graph_cls(color=color, history=history, max_value=max_value)
            if big:
                self.graph.set_content_height(64 if graph_style == "area" else 56)
                self.graph.set_hexpand(True)
            self.graph.add_css_class("metric-graph")
            self.append(self.graph)

    def set_value_text(self, text: str) -> None:
        self.value_label.set_label(text)

    def redraw(self) -> None:
        if self.graph is not None:
            self.graph.queue_draw()
