#!/usr/bin/env bash
# Full-page screenshots of every serve route via agent-browser.
#
# Usage: scripts/serve_demo/screenshots.sh OUTDIR [light|dark ...]
# Env:   RAFT_DEMO_PORT (default 8821), RAFT_DEMO_VIEWPORT (default "1440 900")
set -euo pipefail

OUT=${1:?usage: screenshots.sh OUTDIR [light|dark ...]}
shift
THEMES=${*:-light dark}
BASE="http://127.0.0.1:${RAFT_DEMO_PORT:-8821}"
export XDG_RUNTIME_DIR=${XDG_RUNTIME_DIR:-/tmp/ab-runtime}
mkdir -p "$OUT" "$XDG_RUNTIME_DIR"

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
  "service:/service/$svc"
)

# shellcheck disable=SC2086
agent-browser set viewport ${RAFT_DEMO_VIEWPORT:-1440 900} >/dev/null
agent-browser open "$BASE/" >/dev/null
for theme in $THEMES; do
  agent-browser eval "localStorage.setItem('raft-serve-theme','$theme')" >/dev/null
  for route in "${ROUTES[@]}"; do
    name=${route%%:*}
    path=${route#*:}
    agent-browser open "$BASE$path" >/dev/null
    agent-browser wait 2500 >/dev/null
    agent-browser screenshot --full "$OUT/$name-$theme.png" >/dev/null
  done
done
ls "$OUT"
