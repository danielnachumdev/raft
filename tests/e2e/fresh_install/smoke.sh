#!/usr/bin/env bash
# Routine CLI smoke after a fresh uv-tool install (catches missing package data).
# Image has no Docker Engine — avoid commands that shell out to ``docker``.
set -euo pipefail

export PATH="${HOME}/.local/bin:${PATH}"
export RAFT_DATA_HOME="${RAFT_DATA_HOME:-/tmp/raft-fresh-install}"
mkdir -p "${RAFT_DATA_HOME}"

command -v raft >/dev/null
raft get apps
raft apply --file /opt/raft-fresh-fixture/.raft/app.yaml --no-deploy
raft get app fresh-install-smoke

RAFT_BIN="$(readlink -f "$(command -v raft)")"
RAFT_PYTHON="$(dirname "${RAFT_BIN}")/python"
"${RAFT_PYTHON}" - <<'PY'
from raft.core.core.config.paths import PackageRootFinder

root = PackageRootFinder().find()
assert (root / "compose.yaml").is_file(), root
assert (root / "nginx").is_dir(), root
print(f"OK packaged share at {root}")
PY
