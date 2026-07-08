#!/usr/bin/env bash
# capture-screenshots.sh — capture a fresh screenshot of Kopilka against demo data
#
# Launches the app from source under a throwaway $HOME (so it never touches
# Cal's real config/budget data), inside an isolated Xvfb display forced via
# GDK_BACKEND=x11 (GTK4 otherwise prefers the real Wayland session and would
# render on the actual desktop). Waits for the window to render, screenshots
# just the window, and overwrites screenshots/kopilka-main.png.
#
# Requires: Xvfb, ImageMagick (magick), python3-gi/gtk4/libadwaita (same deps
# as running Kopilka normally).

set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

DEMO_HOME=$(mktemp -d /tmp/kopilka-demo-home.XXXXXX)
OUT="screenshots/kopilka-main.png"
WINDOW_W=1200
WINDOW_H=800

cleanup() {
  [[ -n "${APP_PID:-}" ]] && kill "$APP_PID" 2>/dev/null || true
  [[ -n "${XVFB_PID:-}" ]] && kill "$XVFB_PID" 2>/dev/null || true
  rm -rf "$DEMO_HOME"
}
trap cleanup EXIT

echo "==> Seeding demo config in $DEMO_HOME"
mkdir -p "$DEMO_HOME/.config/kopilka"
cp screenshots/demo-budget.json "$DEMO_HOME/.config/kopilka/budget.json"
cat > "$DEMO_HOME/.config/kopilka/config.json" <<JSON
{
  "user1_name": "Partner A",
  "user2_name": "Partner B"
}
JSON

# Isolated Xvfb display, well clear of any real display number in use.
DISPLAY_NUM=224
while [[ -e "/tmp/.X${DISPLAY_NUM}-lock" ]]; do
  DISPLAY_NUM=$((DISPLAY_NUM + 1))
done

echo "==> Starting isolated Xvfb on :$DISPLAY_NUM"
Xvfb ":$DISPLAY_NUM" -screen 0 1280x900x24 &
XVFB_PID=$!
sleep 2

echo "==> Launching Kopilka against demo data inside the isolated display"
# GDK_BACKEND=x11 + unsetting WAYLAND_DISPLAY is required: GTK4 prefers Wayland
# by default, which would otherwise connect to the real desktop session and
# render there instead of into the isolated Xvfb display.
env -u WAYLAND_DISPLAY GDK_BACKEND=x11 HOME="$DEMO_HOME" DISPLAY=":$DISPLAY_NUM" python3 -m kopilka.kopilka &
APP_PID=$!

echo "==> Waiting for window to render"
sleep 10

echo "==> Capturing and cropping to the app window"
DISPLAY=":$DISPLAY_NUM" magick x:root -crop "${WINDOW_W}x${WINDOW_H}+0+0" +repage "$OUT"

echo "Done. Wrote $OUT"
