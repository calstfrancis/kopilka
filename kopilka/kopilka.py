#!/usr/bin/env python3
"""
Kopilka — Couples Budget Planner
Shared finance management and spending tracker for couples.
"""

import sys
import gi

gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio
from kopilka.ui.app_window import AppWindow
from kopilka.storage.json_io import load_budget, ensure_config_dir
from kopilka.desktop_install import ensure_installed


def main():
    """Main application entry point."""
    ensure_config_dir()
    # ensure_installed is a no-op inside the Flatpak sandbox — the build
    # already installed the desktop entry and icon via flatpak-builder.
    import os
    if not os.environ.get("FLATPAK_ID"):
        ensure_installed()
    
    # Create application
    app = Adw.Application(
        application_id="io.github.calstfrancis.kopilka",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS
    )
    
    def on_activate(application):
        windows = application.get_windows()
        if windows:
            windows[0].present()
            return
        window = AppWindow(application)
        window.present()
    
    app.connect("activate", on_activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
