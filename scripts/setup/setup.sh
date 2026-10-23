#!/usr/bin/env bash
# Contributor setup for raft: prerequisites, local/ workspace, then capa install.
#
# Usage (from repo root):
#   ./scripts/setup/setup.sh
#
# Run steps independently:
#   ./scripts/setup/prerequisites.sh   # gh, uv, Node, agent-browser, capa; verify docker
#
# Also ensures REPO/local/ exists and, on first run, initializes a git repo there
# with default branch main (skips init if local/.git already present).
#
# Optional env:
#   NODE_VERSION, NO_COLOR, CAPA_INSTALL_ARGS (extra flags for capa install, e.g. -e)

set -euo pipefail

SETUP_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SETUP_DIR}/../.." && pwd)"
SCRIPT_NAME="$(basename "$0")"

_use_color() {
  [[ -t 1 ]] && [[ -z "${NO_COLOR:-}" ]]
}

_status_emit() {
  local tag="$1"
  shift
  local label="[${tag}]"
  local color="" reset=""
  if _use_color; then
    reset=$'\033[0m'
    case "${tag}" in
      step) color=$'\033[1;36m' ;;
      ok | done) color=$'\033[32m' ;;
      install) color=$'\033[36m' ;;
      error | fail) color=$'\033[31m' ;;
    esac
  fi
  if [[ "${tag}" == fail ]]; then
    printf '%s%s%s %s\n' "${color}" "${label}" "${reset}" "$*" >&2
  else
    printf '%s%s%s %s\n' "${color}" "${label}" "${reset}" "$*"
  fi
}

step() { _status_emit step "$@"; }
ok() { _status_emit ok "$@"; }
done_msg() { _status_emit done "$@"; }
install() { _status_emit install "$@"; }

die() {
  _status_emit fail "${SCRIPT_NAME}: $*"
  exit 1
}

ensure_path_local_bin() {
  case ":${PATH}:" in
    *:"${HOME}/.local/bin":*) ;;
    *) export PATH="${HOME}/.local/bin:${PATH}" ;;
  esac
  case ":${PATH}:" in
    *:"${HOME}/.capa/bin":*) ;;
    *)
      if [[ -d "${HOME}/.capa/bin" ]]; then
        export PATH="${HOME}/.capa/bin:${PATH}"
      fi
      ;;
  esac
}

capa_server_running() {
  # Prefer Health line — "Status: … Not running" also contains the word "running".
  capa status 2>/dev/null | grep -Eqi '^Health:[[:space:]]*.*\bHealthy\b'
}

ensure_capa_server() {
  if capa_server_running; then
    return 0
  fi
  local attempt=0
  while [[ "${attempt}" -lt 3 ]]; do
    attempt=$((attempt + 1))
    capa start >/dev/null 2>&1 || true
    sleep 1
    if capa_server_running; then
      return 0
    fi
    sleep 2
  done
  return 1
}

install_capa_capabilities() {
  ensure_path_local_bin
  if [[ ! -f "${REPO_ROOT}/capabilities.yaml" && ! -f "${REPO_ROOT}/capabilities.json" ]]; then
    die "No capabilities.yaml/json at repo root; cannot run capa install."
  fi
  if ! command -v capa >/dev/null 2>&1; then
    die "capa not on PATH after prerequisites. Install from https://capa.sh/."
  fi

  local log ec=0
  log="$(mktemp)"
  {
    if ! ensure_capa_server; then
      echo "capa server failed to start. Try: capa stop; capa start -f"
      capa status || true
      exit 1
    fi
    # shellcheck disable=SC2086
    (cd "${REPO_ROOT}" && capa --headless install --yes ${CAPA_INSTALL_ARGS:-})
  } >"${log}" 2>&1 || ec=$?

  if [[ "${ec}" -eq 0 ]]; then
    rm -f "${log}"
    ok "capa"
    return 0
  fi
  cat "${log}" >&2
  rm -f "${log}"
  die "capa install failed."
}

# Ensure REPO/local/ exists. If it is not already its own git repo (local/.git),
# initialize one and set the default branch to main. Nested under the raft
# checkout, so do not use rev-parse alone — that would see the parent repo.
ensure_local_workspace() {
  local local_dir="${REPO_ROOT}/local"
  step "Ensuring local/ workspace"
  mkdir -p "${local_dir}"
  if [[ -e "${local_dir}/.git" ]]; then
    ok "local/"
    return 0
  fi
  if ! command -v git >/dev/null 2>&1; then
    die "git not on PATH; required to initialize ${local_dir}"
  fi
  (
    cd "${local_dir}"
    git init
    # Portable (pre–Git 2.28): avoid `git init -b`; set HEAD without needing commits.
    git symbolic-ref HEAD refs/heads/main
  ) || die "git init failed in ${local_dir}"
  ok "local/ (git init, branch main)"
}

main() {
  step "Checking prerequisites"
  "${SETUP_DIR}/prerequisites.sh"
  echo

  ensure_local_workspace
  echo

  install_capa_capabilities
}

main "$@"
