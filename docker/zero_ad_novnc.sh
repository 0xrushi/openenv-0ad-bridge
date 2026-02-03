#!/usr/bin/env bash

set -euo pipefail

DISPLAY_NUM="${DISPLAY_NUM:-0}"
DISPLAY=":${DISPLAY_NUM}"

VNC_PORT="${VNC_PORT:-5900}"
NOVNC_PORT="${NOVNC_PORT:-6080}"

SCREEN_W="${SCREEN_W:-1280}"
SCREEN_H="${SCREEN_H:-720}"
SCREEN_DEPTH="${SCREEN_DEPTH:-24}"

export DISPLAY

# Clean up any existing X lock files
rm -f /tmp/.X${DISPLAY_NUM}-lock /tmp/.X11-unix/X${DISPLAY_NUM}

echo "Starting Xvfb on ${DISPLAY} (${SCREEN_W}x${SCREEN_H}x${SCREEN_DEPTH})"
Xvfb "${DISPLAY}" -screen 0 "${SCREEN_W}x${SCREEN_H}x${SCREEN_DEPTH}" -nolisten tcp -ac &

# Wait for X server to be ready
sleep 2
until xdpyinfo -display "${DISPLAY}" >/dev/null 2>&1; do
  echo "Waiting for X server..."
  sleep 1
done
echo "X server ready"

echo "Starting Openbox (minimal WM)"
openbox-session &

echo "Starting x11vnc on 0.0.0.0:${VNC_PORT}"
if [[ -n "${VNC_PASSWORD:-}" ]]; then
  x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -listen 0.0.0.0 -forever -shared -passwd "${VNC_PASSWORD}" &
else
  x11vnc -display "${DISPLAY}" -rfbport "${VNC_PORT}" -listen 0.0.0.0 -forever -shared -nopw &
fi

NOVNC_WEB_ROOT="${NOVNC_WEB_ROOT:-/usr/share/novnc}"
if [[ ! -d "${NOVNC_WEB_ROOT}" ]]; then
  echo "ERROR: noVNC web root not found at ${NOVNC_WEB_ROOT}" >&2
  exit 2
fi

echo "Starting noVNC web on 0.0.0.0:${NOVNC_PORT} (serving ${NOVNC_WEB_ROOT})"
websockify --web="${NOVNC_WEB_ROOT}" --wrap-mode=ignore "0.0.0.0:${NOVNC_PORT}" "127.0.0.1:${VNC_PORT}" &

echo "Starting 0 A.D. (RL interface: ${ZEROAD_RL_INTERFACE:-unset})"
# Run as non-root user to avoid 0ad's security restrictions
exec su -c "python launcher.py \
  --binary=\"${ZEROAD_BINARY:-/usr/games/pyrogenesis}\" \
  --map=\"${ZEROAD_MAP:-scenarios/arcadia}\" \
  --players=\"${ZEROAD_PLAYERS:-2}\" \
  --xres=\"${ZEROAD_XRES:-1276}\" \
  --yres=\"${ZEROAD_YRES:-768}\" \
  --nosound" zeroad
