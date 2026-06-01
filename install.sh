#!/bin/bash
# Budget App Installation Script

set -e

echo "Installing Budget App..."

# Check for pipx
if ! command -v pipx &> /dev/null; then
    echo "Error: pipx not found. Install with: pip install --user pipx"
    exit 1
fi

# Check for GTK4 + libadwaita
echo "Checking for GTK4 and libadwaita..."
if ! python3 -c "import gi; gi.require_version('Gtk', '4.0'); gi.require_version('Adw', '1')" 2>/dev/null; then
    echo ""
    echo "Error: GTK4 + libadwaita required but not found."
    echo ""
    echo "On openSUSE Tumbleweed:"
    echo "  sudo zypper install python3-gobject typelib-1_0-Adw-1 typelib-1_0-Gtk-4_0"
    echo ""
    echo "On Ubuntu/Debian:"
    echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1"
    echo ""
    exit 1
fi

# Install with pipx
echo "Installing via pipx..."
pipx install --system-site-packages .

# Create config directory
mkdir -p ~/.config/budgetapp
mkdir -p ~/.local/share/budgetapp

# Copy desktop entry (optional)
if [ -f "io.github.calstfrancis.budgetapp.desktop" ]; then
    mkdir -p ~/.local/share/applications
    cp io.github.calstfrancis.budgetapp.desktop ~/.local/share/applications/
    echo "Desktop entry installed"
fi

echo ""
echo "✓ Budget App installed!"
echo ""
echo "To launch:"
echo "  budgetapp"
echo ""
echo "To update later:"
echo "  pipx upgrade budgetapp"
