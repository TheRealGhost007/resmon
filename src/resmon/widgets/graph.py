"""Cairo-drawn graphs: bars, a static per-core strip, and a smooth gradient
area chart."""

from __future__ import annotations

from collections import deque

import cairo
import gi

gi.require_version("Gtk", "4.0")
from gi.repository import Gtk

Color = tuple[float, float, float]
Point = tuple[float, float]


def _rounded_top(cr, x: float, y: float, w: float, h: float, r: float) -> None:
    if r <= 0 or w < 2 * r or h < r:
        cr.rectangle(x, y, w, h)
        return
    cr.new_sub_path()
    cr.arc(x + w - r, y + r, r, -1.5708, 0)
    cr.line_to(x + w, y + h)
    cr.line_to(x, y + h)
    cr.arc(x + r, y + r, r, 3.14159, 4.71239)
    cr.close_path()


class BarGraph(Gtk.DrawingArea):
    """A scrolling bar graph over a fixed-length history buffer."""

    def __init__(self, color: Color, history: deque[float], max_value: float = 100.0):
        super().__init__()
        self._color = color
        self._history = history
        self._max_value = max_value
        self.set_content_width(150)
        self.set_content_height(34)
        self.set_focusable(False)
        self.set_can_target(False)
        self.set_draw_func(self._on_draw)

    def _on_draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        n = len(self._history)
        if n == 0 or width <= 0 or height <= 0:
            return

        gap = 2.0
        bar_w = max(1.0, (width - gap * (n - 1)) / n)
        radius = min(1.5, bar_w / 2)
        r, g, b = self._color

        for i, value in enumerate(self._history):
            frac = max(0.0, min(1.0, value / self._max_value))
            bar_h = max(1.5, frac * height)
            x = i * (bar_w + gap)
            y = height - bar_h

            # Older samples fade out toward the left edge.
            age = (n - 1 - i) / max(1, n - 1)
            alpha = 0.22 + 0.78 * (1 - age)

            cr.set_source_rgba(r, g, b, alpha)
            _rounded_top(cr, x, y, bar_w, bar_h, radius)
            cr.fill()


def _quad_curve_to(cr, ctrl: Point, end: Point) -> None:
    """Cairo only has cubic curve_to; this converts a quadratic segment."""
    x0, y0 = cr.get_current_point()
    c1 = (x0 + 2 / 3 * (ctrl[0] - x0), y0 + 2 / 3 * (ctrl[1] - y0))
    c2 = (end[0] + 2 / 3 * (ctrl[0] - end[0]), end[1] + 2 / 3 * (ctrl[1] - end[1]))
    cr.curve_to(c1[0], c1[1], c2[0], c2[1], end[0], end[1])


def _smooth_path(cr, points: list[Point]) -> None:
    """A smooth curve through every point (not just a spline near them),
    via quadratic beziers through successive midpoints — the standard
    trick for turning a polyline into a smooth curve without overshoot."""
    n = len(points)
    if n == 0:
        return
    cr.move_to(*points[0])
    if n == 1:
        return
    if n == 2:
        cr.line_to(*points[1])
        return
    for i in range(1, n - 1):
        mid = ((points[i][0] + points[i + 1][0]) / 2, (points[i][1] + points[i + 1][1]) / 2)
        _quad_curve_to(cr, points[i], mid)
    _quad_curve_to(cr, points[n - 2], points[n - 1])


class AreaGraph(Gtk.DrawingArea):
    """A smooth, gradient-filled trend line over a fixed-length history."""

    def __init__(self, color: Color, history: deque[float], max_value: float = 100.0):
        super().__init__()
        self._color = color
        self._history = history
        self._max_value = max_value
        self.set_content_height(64)
        self.set_hexpand(True)
        self.set_focusable(False)
        self.set_can_target(False)
        self.set_draw_func(self._on_draw)

    def _points(self, width: float, height: float) -> list[Point]:
        n = len(self._history)
        if n < 2:
            return []
        step = width / (n - 1)
        pad = 3.0  # keeps the line's stroke width from clipping at the top
        points = []
        for i, value in enumerate(self._history):
            frac = max(0.0, min(1.0, value / self._max_value))
            points.append((i * step, pad + (1 - frac) * (height - 2 * pad)))
        return points

    def _on_draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        points = self._points(width, height)
        if len(points) < 2 or width <= 0 or height <= 0:
            return

        r, g, b = self._color

        cr.save()
        _smooth_path(cr, points)
        cr.line_to(points[-1][0], height)
        cr.line_to(points[0][0], height)
        cr.close_path()
        gradient = cairo.LinearGradient(0, 0, 0, height)
        gradient.add_color_stop_rgba(0, r, g, b, 0.40)
        gradient.add_color_stop_rgba(1, r, g, b, 0.0)
        cr.set_source(gradient)
        cr.fill()
        cr.restore()

        # A soft glow: a wide, faint stroke sitting under the crisp line.
        cr.save()
        _smooth_path(cr, points)
        cr.set_source_rgba(r, g, b, 0.28)
        cr.set_line_width(5.5)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()
        cr.restore()

        _smooth_path(cr, points)
        cr.set_source_rgba(r, g, b, 0.95)
        cr.set_line_width(2.0)
        cr.set_line_join(cairo.LINE_JOIN_ROUND)
        cr.set_line_cap(cairo.LINE_CAP_ROUND)
        cr.stroke()


class CoreBars(Gtk.DrawingArea):
    """A static row of per-core load bars, redrawn from the latest reading."""

    def __init__(self, color: Color):
        super().__init__()
        self._color = color
        self._values: list[float] = []
        self.set_content_height(40)
        self.set_hexpand(True)
        self.set_focusable(False)
        self.set_can_target(False)
        self.set_draw_func(self._on_draw)

    def set_values(self, values: list[float]) -> None:
        self._values = values
        self.queue_draw()

    def _on_draw(self, _area: Gtk.DrawingArea, cr, width: int, height: int) -> None:
        n = len(self._values)
        if n == 0 or width <= 0 or height <= 0:
            return

        gap = 3.0
        bar_w = max(2.0, (width - gap * (n - 1)) / n)
        radius = min(2.0, bar_w / 2)
        r, g, b = self._color

        for i, value in enumerate(self._values):
            frac = max(0.0, min(1.0, value / 100.0))
            bar_h = max(2.0, frac * height)
            x = i * (bar_w + gap)
            y = height - bar_h

            cr.set_source_rgba(r, g, b, 0.35 + 0.65 * frac)
            _rounded_top(cr, x, y, bar_w, bar_h, radius)
            cr.fill()
