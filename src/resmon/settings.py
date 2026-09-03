"""Small JSON-backed settings store shared by the app and the overlay."""

from __future__ import annotations

import json
from typing import Any

from .paths import CONFIG_DIR, SETTINGS_FILE

CORNERS = ["top-right", "top-left", "bottom-right", "bottom-left"]

OVERLAY_STYLES = ["bars", "percent"]

# Milliseconds between metric samples. Lower is more responsive; higher uses
# less CPU (fewer psutil/proc reads, fewer Cairo redraws, fewer subprocess
# spawns for GPU polling). 2s is a lightweight-by-default middle ground.
UPDATE_INTERVALS_MS = [1000, 2000, 5000]

DEFAULTS: dict[str, Any] = {
    "overlay_enabled": False,
    "autostart_enabled": False,
    "overlay_corner": "top-right",
    "theme": "default",
    "overlay_style": "bars",
    "update_interval_ms": 2000,
    "overlay_collapsed": False,
    "alerts_enabled": False,
    "alert_cpu_percent": 90,
    "alert_mem_percent": 90,
    "alert_temp_celsius": 85,
}


class Settings:
    def __init__(self) -> None:
        self._data: dict[str, Any] = dict(DEFAULTS)
        self._load()

    def _load(self) -> None:
        try:
            self._data.update(json.loads(SETTINGS_FILE.read_text()))
        except (FileNotFoundError, json.JSONDecodeError):
            pass

    def save(self) -> None:
        CONFIG_DIR.mkdir(parents=True, exist_ok=True)
        SETTINGS_FILE.write_text(json.dumps(self._data, indent=2))

    def get(self, key: str) -> Any:
        return self._data[key]

    def set(self, key: str, value: Any) -> None:
        self._data[key] = value
        self.save()
