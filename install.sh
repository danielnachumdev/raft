#!/usr/bin/env bash
# Install raft as a user-wide uv tool (`raft` on PATH).
#
# Default (curl|bash): install from GitHub — no lasting checkout left on disk.
# From a local checkout (`./install.sh`): install from that tree; leave it alone.
#
# Usage:
#   curl -fsSL https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh | bash
#   # or, from a checkout:
#   ./install.sh
#
# Env overrides:
#   RAFT_REPO_URL   Git remote (default: https://github.com/danielnachumdev/raft.git)
#   RAFT_BRANCH     Branch / ref to install (default: main)
#   RAFT_HOME       If set with RAFT_KEEP_CHECKOUT=1, shallow-clone/update here and
#                   install from that path (dev/ops who want a durable checkout).
#   RAFT_KEEP_CHECKOUT  Set to 1 to keep/use RAFT_HOME (default: ~/raft when unset).
#   RAFT_EDITABLE   When installing from a local path, pass --editable (default: 1
#                   for checkout installs / keep-checkout; 0 for git URL installs).
set -euo pipefail

RAFT_REPO_URL="${RAFT_REPO_URL:-https://github.com/danielnachumdev/raft.git}"
RAFT_BRANCH="${RAFT_BRANCH:-main}"
RAFT_KEEP_CHECKOUT="${RAFT_KEEP_CHECKOUT:-0}"

die() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

ensure_path_local_bin() {
  case ":${PATH}:" in
    *":${HOME}/.local/bin:"*) ;;
    *) export PATH="${HOME}/.local/bin:${PATH}" ;;
  esac
}

ensure_uv() {
  ensure_path_local_bin
  if command -v uv >/dev/null 2>&1; then
    return 0
  fi
  echo "uv not found; installing via https://astral.sh/uv/install.sh"
  curl -LsSf https://astral.sh/uv/install.sh | sh
  ensure_path_local_bin
  command -v uv >/dev/null 2>&1 || die "uv install finished but 'uv' is not on PATH (expected ${HOME}/.local/bin)"
}

ensure_git() {
  command -v git >/dev/null 2>&1 || die "git is required"
}

# True when this script lives inside a raft source tree (./install.sh).
local_checkout_dir() {
  local src dir
  src="${BASH_SOURCE[0]:-}"
  [[ -n "${src}" && -f "${src}" ]] || return 1
  dir="$(cd "$(dirname "${src}")" && pwd)"
  [[ -f "${dir}/pyproject.toml" ]] || return 1
  grep -q '^name = "raft"' "${dir}/pyproject.toml" 2>/dev/null || return 1
  printf '%s\n' "${dir}"
}

clone_or_update() {
  local dest="$1"
  if [[ -d "${dest}/.git" ]]; then
    echo "Updating existing checkout at ${dest}"
    git -C "${dest}" remote set-url origin "${RAFT_REPO_URL}"
    git -C "${dest}" fetch --depth 1 origin "${RAFT_BRANCH}"
    git -C "${dest}" checkout -B "${RAFT_BRANCH}" "origin/${RAFT_BRANCH}"
  else
    if [[ -e "${dest}" ]]; then
      die "${dest} exists but is not a git checkout; set RAFT_HOME or remove it"
    fi
    echo "Cloning ${RAFT_REPO_URL} (${RAFT_BRANCH}, depth 1) → ${dest}"
    git clone --depth 1 --branch "${RAFT_BRANCH}" "${RAFT_REPO_URL}" "${dest}"
  fi
}

install_from_path() {
  local path="$1"
  local editable="${2:-0}"
  if [[ "${editable}" == "1" ]]; then
    echo "Installing raft CLI as a uv tool (editable → ${path})"
    uv tool install --force --editable "${path}"
  else
    echo "Installing raft CLI as a uv tool from ${path}"
    uv tool install --force "${path}"
  fi
}

install_from_git() {
  # uv fetches into its cache; nothing durable under ~/raft.
  local spec="git+${RAFT_REPO_URL}@${RAFT_BRANCH}"
  echo "Installing raft CLI as a uv tool from ${spec}"
  uv tool install --force "${spec}"
}

finish_message() {
  local mode="$1"
  ensure_path_local_bin

  if command -v raft >/dev/null 2>&1; then
    echo "OK: $(command -v raft)"
    raft -- --help >/dev/null 2>&1 || raft -h >/dev/null 2>&1 || true
  else
    echo "raft was installed but is not on PATH yet."
    echo "Open a new shell, or run:  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    echo "Then:  uv tool update-shell"
  fi

  cat <<EOF

Installed.
  CLI tool on PATH:  raft   (via uv tool)
  Install mode:      ${mode}
  Operator data:     \${HOME}/.raft   (settings, state, generated, certs, logs)
                     override with RAFT_DATA_HOME

Re-run this script or use \`raft update\` (when available) to refresh from GitHub.
No lasting raft git clone is required for the tool to work.

EOF
}
main() {
  ensure_git
  ensure_uv

  local checkout=""
  local mode=""
  local editable

  if [[ "${RAFT_KEEP_CHECKOUT}" == "1" ]]; then
    local home="${RAFT_HOME:-${HOME}/raft}"
    clone_or_update "${home}"
    editable="${RAFT_EDITABLE:-1}"
    install_from_path "${home}" "${editable}"
    mode="kept checkout at ${home}"
  elif checkout="$(local_checkout_dir)"; then
    editable="${RAFT_EDITABLE:-1}"
    install_from_path "${checkout}" "${editable}"
    mode="local checkout ${checkout} (not removed)"
  else
    install_from_git
    mode="git ${RAFT_REPO_URL}@${RAFT_BRANCH} (no lasting clone)"
  fi

  # Best-effort: ensure the uv tools bin dir is on PATH in common shells.
  uv tool update-shell >/dev/null 2>&1 || true
  finish_message "${mode}"
}

main "$@"
