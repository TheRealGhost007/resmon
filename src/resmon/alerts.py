"""Threshold-based desktop notifications for CPU/memory/temperature."""

from __future__ import annotations

import time

import gi

gi.require_version("Gio", "2.0")
from gi.repository import Gio

from .settings import Settings

# Don't re-notify for the same metric more than once in this window, so a
# sustained high reading doesn't spam a notification every tick.
_COOLDOWN_SECONDS = 300


class AlertChecker:
    def __init__(self, app: Gio.Application):
        self._app = app
        self._last_fired: dict[str, float] = {}

    def check(self, cpu: float, ram: float, temp: float | None) -> None:
        settings = Settings()
        if not settings.get("alerts_enabled"):
            return

        self._check_one("cpu", cpu, settings.get("alert_cpu_percent"), "CPU usage", "%")
        self._check_one("ram", ram, settings.get("alert_mem_percent"), "Memory usage", "%")
        if temp is not None:
            self._check_one("temp", temp, settings.get("alert_temp_celsius"), "Temperature", "°C")

    def _check_one(self, key: str, value: float, threshold: int, label: str, unit: str) -> None:
        if threshold <= 0 or value < threshold:
            return

        now = time.monotonic()
        if now - self._last_fired.get(key, 0.0) < _COOLDOWN_SECONDS:
            return
        self._last_fired[key] = now

        notification = Gio.Notification.new(f"{label} high")
        notification.set_body(f"{label} is at {value:.0f}{unit} (threshold {threshold}{unit})")
        notification.set_priority(Gio.NotificationPriority.HIGH)
        self._app.send_notification(f"resmon-{key}", notification)
