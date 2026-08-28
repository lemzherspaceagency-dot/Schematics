#!/bin/sh
# Runs a command against a throwaway X server so the game can be exercised
# without a desktop.
set -e
DISPLAY_NUM=${FF_DISPLAY:-:99}
if ! xdpyinfo -display "$DISPLAY_NUM" >/dev/null 2>&1; then
    Xvfb "$DISPLAY_NUM" -screen 0 1280x720x24 >/dev/null 2>&1 &
    XVFB_PID=$!
    trap 'kill $XVFB_PID 2>/dev/null || true' EXIT
    sleep 2
fi
DISPLAY="$DISPLAY_NUM" exec "$@"
