#!/usr/bin/env python3
"""
Kopilka — Couples Budget Planner
Shared finance management with tax estimation and spending tracking.
"""

import sys
import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio
from kopilka.ui.app_window import AppWindow
from kopilka.storage.json_io import load_budget, ensure_config_dir


def main():
    """Main application entry point."""
    # Ensure config directory exists
    ensure_config_dir()
    
    # Create application
    app = Adw.Application(
        application_id="io.github.calstfrancis.kopilka",
        flags=Gio.ApplicationFlags.DEFAULT_FLAGS
    )
    
    def on_activate(application):
        """Activate the application."""
        window = AppWindow(application)
        window.present()
    
    app.connect("activate", on_activate)
    return app.run(sys.argv)


if __name__ == "__main__":
    sys.exit(main())
