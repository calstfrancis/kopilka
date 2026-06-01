"""Dashboard view showing budget summary."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw


class Dashboard(Gtk.Box):
    """Dashboard showing budget overview."""
    
    def __init__(self, budget):
        """Initialize dashboard."""
        super().__init__(orientation=Gtk.Orientation.VERTICAL, spacing=15)
        self.budget = budget
        self.set_margin_top(20)
        self.set_margin_bottom(20)
        self.set_margin_start(20)
        self.set_margin_end(20)
        
        # Title
        title = Gtk.Label(label="Budget Dashboard")
        title.add_css_class("title-1")
        self.append(title)
        
        # Income summary card
        income_card = self._build_income_card()
        self.append(income_card)
        
        # Available to spend card
        available_card = self._build_available_card()
        self.append(available_card)
        
        # Spending categories
        categories_card = self._build_categories_card()
        self.append(categories_card)
    
    def _build_income_card(self):
        """Build income summary card."""
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_box.add_css_class("card")
        card_box.set_margin_bottom(10)
        
        title = Gtk.Label(label="Income Summary")
        title.add_css_class("title-2")
        card_box.append(title)
        
        # Placeholder values
        gross_label = Gtk.Label(label="Monthly Gross: $0")
        tax_label = Gtk.Label(label="Estimated Tax: $0")
        net_label = Gtk.Label(label="Net Available: $0")
        
        card_box.append(gross_label)
        card_box.append(tax_label)
        card_box.append(net_label)
        
        return card_box
    
    def _build_available_card(self):
        """Build available to spend card."""
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_box.add_css_class("card")
        card_box.set_margin_bottom(10)
        
        title = Gtk.Label(label="Available to Spend")
        title.add_css_class("title-2")
        card_box.append(title)
        
        available_label = Gtk.Label(label="$0")
        available_label.add_css_class("title-1")
        available_label.set_markup("<span size='large' weight='bold'>$0</span>")
        card_box.append(available_label)
        
        return card_box
    
    def _build_categories_card(self):
        """Build spending categories card."""
        card_box = Gtk.Box(orientation=Gtk.Orientation.VERTICAL, spacing=10)
        card_box.add_css_class("card")
        
        title = Gtk.Label(label="Spending Categories")
        title.add_css_class("title-2")
        card_box.append(title)
        
        # Placeholder
        placeholder = Gtk.Label(label="No categories yet")
        card_box.append(placeholder)
        
        return card_box
