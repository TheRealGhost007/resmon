"""CLI entry point for resmon: the full app by default, or the overlay."""

from __future__ import annotations

import argparse


def main() -> None:
    parser = argparse.ArgumentParser(prog="resmon", description="A clean system resource monitor.")
    parser.add_argument(
        "--overlay",
        action="store_true",
        help="Run the desktop corner overlay widget instead of the full app.",
    )
    parser.add_argument(
        "--windowed",
        action="store_true",
        help="(--overlay only) run as a normal window instead of a layer-shell overlay; useful for testing.",
    )
    parser.add_argument(
        "--bar-module",
        action="store_true",
        help="Print one status line for Omarchy's bar `command` module, then exit. No GTK involved.",
    )
    args = parser.parse_args()

    if args.bar_module:
        from .bar_module import main as bar_main

        bar_main()
        return

    if args.overlay:
        from .overlay_app import OverlayApp

        app = OverlayApp(windowed=args.windowed)
    else:
        from .main_app import MainApp

        app = MainApp()

    app.run([])


if __name__ == "__main__":
    main()
