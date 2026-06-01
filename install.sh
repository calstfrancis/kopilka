#!/bin/bash
# Kopilka installation script (from source)

set -e

echo "Installing Kopilka..."

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
    echo "On Ubuntu 22.04+:"
    echo "  sudo apt install python3-gi python3-gi-cairo gir1.2-gtk-4.0 gir1.2-adw-1"
    echo ""
    echo "On Fedora 38+:"
    echo "  sudo dnf install python3-gobject gtk4 libadwaita"
    echo ""
    exit 1
fi

# Install with pipx
echo "Installing via pipx..."
pipx install --system-site-packages .

# Create config directory
mkdir -p ~/.config/kopilka

# Install desktop entry and icon
python3 -m kopilka.desktop_install

echo ""
echo "Kopilka installed!"
echo ""
echo "To launch:"
echo "  kopilka"
echo ""
echo "To update later:"
echo "  pipx upgrade kopilka"
