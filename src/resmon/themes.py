"""Named color themes shared by the overlay and the full app.

"default" keeps the original multi-hue palette. "onyx" is a high-contrast,
near-black theme where every metric reads in a shade of blue instead.
"""

from __future__ import annotations

THEME_IDS = ["default", "onyx"]
THEME_LABELS = {"default": "Default", "onyx": "Onyx"}

# (r, g, b) in 0..1, one per metric, per theme.
THEME_COLORS: dict[str, dict[str, tuple[float, float, float]]] = {
    "default": {
        "cpu": (0.40, 0.65, 1.00),
        "ram": (0.66, 0.48, 1.00),
        "disk": (1.00, 0.62, 0.30),
        "net": (0.35, 0.85, 0.65),
        "diskio": (1.00, 0.80, 0.35),
        "gpu": (0.95, 0.40, 0.75),
        "temp": (1.00, 0.42, 0.42),
    },
    "onyx": {
        "cpu": (0.19, 0.56, 1.00),
        "ram": (0.36, 0.70, 1.00),
        "disk": (0.55, 0.80, 1.00),
        "net": (0.16, 0.87, 1.00),
        "diskio": (0.75, 0.90, 1.00),
        "gpu": (0.42, 0.66, 1.00),
        "temp": (0.65, 0.85, 1.00),
    },
}


def colors_for(theme: str) -> dict[str, tuple[float, float, float]]:
    return THEME_COLORS.get(theme, THEME_COLORS["default"])
