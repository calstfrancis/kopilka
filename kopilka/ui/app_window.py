"""Main application window."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw, Gio
from kopilka.ui.dashboard import Dashboard
from kopilka.storage.json_io import load_budget


class AppWindow(Adw.ApplicationWindow):
    """Main application window."""
    
    def __init__(self, application):
        """Initialize the main window."""
        super().__init__(application=application)
        
        # Load budget data
        self.budget = load_budget()
        
        # Window properties
        self.set_title("Budget")
        self.set_default_size(1200, 800)
        
        # Create main box
        main_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL)
        self.set_content(main_box)
        
        # Header bar
        header_bar = Adw.HeaderBar()
        main_box.append(header_bar)
        
        # Create sidebar + content area
        paned = Gtk.Paned(orientation=Gtk.Orientation.HORIZONTAL)
        main_box.append(paned)
        main_box.set_vexpand(True)
        
        # Sidebar
        self.sidebar = self._build_sidebar()
        paned.set_start_child(self.sidebar)
        paned.set_position(200)
        
        # Content area (start with dashboard)
        self.content_stack = Gtk.Stack()
        paned.set_end_child(self.content_stack)
        
        # Add dashboard
        self.dashboard = Dashboard(self.budget)
        self.content_stack.add_named(self.dashboard, "dashboard")
        self.content_stack.set_visible_child_name("dashboard")
    
    def _build_sidebar(self):
        """Build the sidebar navigation."""
        sidebar = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        sidebar.set_margin_top(10)
        sidebar.set_margin_bottom(10)
        sidebar.set_margin_start(10)
        sidebar.set_margin_end(10)
        
        # Navigation buttons
        nav_buttons = [
            ("📊 Dashboard", "dashboard"),
            ("💰 Income", "income"),
            ("💸 Expenses", "expenses"),
            ("🚩 Debt", "debt"),
            ("📝 Spending Log", "log"),
            ("⚙️ Settings", "settings"),
        ]
        
        for label, action in nav_buttons:
            btn = Gtk.Button(label=label)
            btn.connect("clicked", self._on_nav_clicked, action)
            sidebar.append(btn)
        
        return sidebar
    
    def _on_nav_clicked(self, button, page):
        """Handle sidebar navigation."""
        # TODO: Switch content based on page
        print(f"Navigation: {page}")
