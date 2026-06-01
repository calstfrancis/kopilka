"""Forms for adding and editing budget items."""

import gi
gi.require_version("Gtk", "4.0")
gi.require_version("Adw", "1")

from gi.repository import Gtk, Adw


class AddIncomeDialog(Adw.Dialog):
    """Dialog for adding income source."""
    
    def __init__(self, parent):
        """Initialize dialog."""
        super().__init__()
        self.parent = parent
        # TODO: Implement form


class AddExpenseDialog(Adw.Dialog):
    """Dialog for adding expense."""
    
    def __init__(self, parent):
        """Initialize dialog."""
        super().__init__()
        self.parent = parent
        # TODO: Implement form


class AddDebtDialog(Adw.Dialog):
    """Dialog for adding debt."""
    
    def __init__(self, parent):
        """Initialize dialog."""
        super().__init__()
        self.parent = parent
        # TODO: Implement form


class AddCategoryDialog(Adw.Dialog):
    """Dialog for adding spending category."""
    
    def __init__(self, parent):
        """Initialize dialog."""
        super().__init__()
        self.parent = parent
        # TODO: Implement form
