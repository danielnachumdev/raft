#!/bin/sh
# Supervisor: app on loopback, then nginx auth edge on the published port.
set -eu

echo "dashboard: writing nginx.conf + starting app"
python -m raft.services.dashboard
# DashboardProcess runs nginx in the foreground and exits when either dies.
