#!/usr/bin/env bash
# Full-page screenshots of every serve route via agent-browser.
#
# Usage: scripts/serve_demo/screenshots.sh OUTDIR [light|dark ...]
# Env:
#   RAFT_DEMO_PORT     (default 8821)
#   RAFT_DEMO_LAYOUT   desktop | tablet | mobile (default desktop)
#   RAFT_DEMO_VIEWPORT override "WIDTH HEIGHT" (defaults per layout)
#
# Layout defaults:
#   desktop → 1440 900   (filenames: status-light.png)
#   tablet  → 820 1180   (filenames: status-light-tablet.png)
#   mobile  → 390 844    (filenames: status-light-mobile.png)
set -euo pipefail

OUT=${1:?usage: screenshots.sh OUTDIR [light|dark ...]}
shift
THEMES=${*:-light dark}
BASE="http://127.0.0.1:${RAFT_DEMO_PORT:-8821}"
LAYOUT=${RAFT_DEMO_LAYOUT:-desktop}
# agent-browser needs a writable runtime dir; /run/user/$UID is often missing in WSL/CI.
if [[ -z "${XDG_RUNTIME_DIR:-}" || ! -w "${XDG_RUNTIME_DIR}" ]]; then
  export XDG_RUNTIME_DIR=/tmp/ab-runtime
fi
mkdir -p "$OUT" "$XDG_RUNTIME_DIR"

case "$LAYOUT" in
  desktop) DEFAULT_VIEWPORT="1440 900"; SUFFIX="" ;;
  tablet)  DEFAULT_VIEWPORT="820 1180"; SUFFIX="-tablet" ;;
  mobile)  DEFAULT_VIEWPORT="390 844";  SUFFIX="-mobile" ;;
  *)
    echo "unknown RAFT_DEMO_LAYOUT='$LAYOUT' (use desktop|tablet|mobile)" >&2
    exit 2
    ;;
esac
VIEWPORT=${RAFT_DEMO_VIEWPORT:-$DEFAULT_VIEWPORT}

svc=$(curl -fsS "$BASE/api/status" | python3 -c \
  "import json,sys;print(next(a['service'] for a in json.load(sys.stdin)['apps'] if a['name'].endswith('demo-api')))")

ROUTES=(
  "status:/"
  "add-service:/add-service"
  "deploy:/deploy"
  "events:/events"
  "settings:/settings"
  "notifications:/settings/notifications"
  "alerts:/settings/alerts"
  "firewall:/settings/edge-access"
  "rbac:/settings/rbac"
  "service:/service/$svc"
)

# shellcheck disable=SC2086
agent-browser set viewport $VIEWPORT >/dev/null
agent-browser open "$BASE/" >/dev/null
for theme in $THEMES; do
  agent-browser eval "localStorage.setItem('raft-serve-theme','$theme')" >/dev/null
  for route in "${ROUTES[@]}"; do
    name=${route%%:*}
    path=${route#*:}
    agent-browser open "$BASE$path" >/dev/null
    agent-browser wait 2500 >/dev/null
    agent-browser screenshot --full "$OUT/$name-$theme$SUFFIX.png" >/dev/null
  done
done
ls "$OUT"
