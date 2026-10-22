#!/usr/bin/env bash
# Install local tooling required by raft contributor / agent workflows:
# GitHub CLI (+ auth), uv, NVM/Node/npm, agent-browser, capa.
# Docker is verified only (install Engine/Desktop separately).
#
# Usage (from repo root):
#   ./scripts/setup/prerequisites.sh
#
# Optional env:
#   NODE_VERSION   Node major or lts/* for nvm (default: lts/*)
#   NO_COLOR       Non-empty disables ANSI colors

set -euo pipefail

NODE_VERSION="${NODE_VERSION:-lts/*}"
NVM_VERSION="${NVM_VERSION:-v0.40.1}"
UV_INSTALL_SCRIPT_URL="https://astral.sh/uv/install.sh"
UV_INSTALL_SCRIPT_SHA256="14b6b88d74b9300d906d9754118afb4d4151e78ad294f026047b7227f5611760"

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/../.." && pwd)"
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
      install | auth) color=$'\033[36m' ;;
      warn) color=$'\033[33m' ;;
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
auth() { _status_emit auth "$@"; }
warn() { _status_emit warn "$@"; }

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

file_sha256_hex() {
  local f="$1"
  if command -v sha256sum >/dev/null 2>&1; then
    sha256sum "${f}" | awk '{print $1}'
  elif command -v shasum >/dev/null 2>&1; then
    shasum -a 256 "${f}" | awk '{print $1}'
  else
    die "Need sha256sum or shasum to verify downloaded files."
  fi
}

install_with_hash_check() {
  local label="$1"
  local url="$2"
  local expected_sha256="$3"
  shift 3
  [[ "${1:-}" == "--" ]] || die "install_with_hash_check (${label}): expected -- before command"
  shift
  [[ $# -gt 0 ]] || die "install_with_hash_check (${label}): missing command after --"

  local tmp
  tmp="$(mktemp)"
  if ! curl -fsSL "${url}" -o "${tmp}"; then
    rm -f "${tmp}"
    die "Failed to download (${label}): ${url}"
  fi
  local actual
  actual="$(file_sha256_hex "${tmp}")"
  if [[ "${actual}" != "${expected_sha256}" ]]; then
    rm -f "${tmp}"
    die "${label}: SHA-256 mismatch (expected ${expected_sha256}, got ${actual})."
  fi
  local runner="$1"
  shift
  local ec=0
  "${runner}" "${tmp}" "$@" || ec=$?
  rm -f "${tmp}"
  [[ "${ec}" -eq 0 ]] || die "${label}: command exited with status ${ec}."
}

install_gh_linux() {
  if command -v apt-get >/dev/null 2>&1; then
    install "Installing GitHub CLI via apt (needs sudo)..."
    sudo apt-get update -qq
    sudo apt-get install -y ca-certificates curl
    sudo install -m 0755 -d /etc/apt/keyrings
    curl -fsSL https://cli.github.com/packages/githubcli-archive-keyring.gpg |
      sudo tee /etc/apt/keyrings/githubcli-archive-keyring.gpg >/dev/null
    sudo chmod go+r /etc/apt/keyrings/githubcli-archive-keyring.gpg
    echo "deb [arch=$(dpkg --print-architecture) signed-by=/etc/apt/keyrings/githubcli-archive-keyring.gpg] https://cli.github.com/packages stable main" |
      sudo tee /etc/apt/sources.list.d/github-cli.list >/dev/null
    sudo apt-get update -qq
    sudo apt-get install -y gh
    return 0
  fi
  return 1
}

ensure_gh() {
  local report_ok=0
  [[ "${1:-}" == --report-ok ]] && report_ok=1

  if command -v gh >/dev/null 2>&1; then
    [[ "${report_ok}" -eq 1 ]] && ok "gh"
    return 0
  fi
  install "gh not found on PATH; attempting install..."
  if command -v brew >/dev/null 2>&1; then
    brew install gh
  elif install_gh_linux; then
    :
  else
    die "Could not install gh automatically. Install from https://cli.github.com/ and re-run."
  fi
  command -v gh >/dev/null 2>&1 || die "gh install finished but gh not on PATH."
  [[ "${report_ok}" -eq 1 ]] && done_msg "gh installed ($(command -v gh))."
}

ensure_gh_auth() {
  local report_ok=0
  [[ "${1:-}" == --report-ok ]] && report_ok=1

  if gh auth status -h github.com >/dev/null 2>&1; then
    [[ "${report_ok}" -eq 1 ]] && ok "gh auth"
    return 0
  fi
  auth "gh is not logged in; starting interactive login..."
  gh auth login -h github.com
  [[ "${report_ok}" -eq 1 ]] && done_msg "gh auth"
}

ensure_uv() {
  local report_ok=0
  [[ "${1:-}" == --report-ok ]] && report_ok=1

  ensure_path_local_bin
  if command -v uv >/dev/null 2>&1; then
    [[ "${report_ok}" -eq 1 ]] && ok "uv"
    return 0
  fi
  install "Installing uv..."
  install_with_hash_check "uv install.sh" "${UV_INSTALL_SCRIPT_URL}" "${UV_INSTALL_SCRIPT_SHA256}" -- sh
  ensure_path_local_bin
  command -v uv >/dev/null 2>&1 || die "uv install finished but uv not on PATH; add ~/.local/bin to PATH."
  [[ "${report_ok}" -eq 1 ]] && done_msg "uv installed ($(command -v uv))."
}

ensure_nvm_node_npm() {
  export NVM_DIR="${NVM_DIR:-${HOME}/.nvm}"
  if [[ ! -s "${NVM_DIR}/nvm.sh" ]]; then
    install "Installing NVM (${NVM_VERSION})..."
    curl -o- "https://raw.githubusercontent.com/nvm-sh/nvm/${NVM_VERSION}/install.sh" | bash
    done_msg "NVM installed (${NVM_DIR})."
  else
    ok "nvm"
  fi
  # shellcheck disable=SC1090
  [[ -s "${NVM_DIR}/nvm.sh" ]] || die "NVM install failed: missing ${NVM_DIR}/nvm.sh"
  # shellcheck disable=SC1091
  source "${NVM_DIR}/nvm.sh"

  if declare -f nvm_is_version_installed >/dev/null 2>&1 && declare -f nvm_version >/dev/null 2>&1; then
    local resolved
    resolved="$(nvm_version "${NODE_VERSION}" 2>/dev/null || true)"
    if [[ -n "${resolved}" && "${resolved}" != "N/A" ]] && nvm_is_version_installed "${resolved}"; then
      nvm use "${NODE_VERSION}" >/dev/null
      ok "node ($(node -v), npm $(npm -v))"
    else
      install "Installing Node ${NODE_VERSION}..."
      nvm install "${NODE_VERSION}"
      nvm use "${NODE_VERSION}" >/dev/null
      done_msg "Node installed ($(node -v), $(npm -v))."
    fi
  else
    install "Installing Node ${NODE_VERSION}..."
    nvm install "${NODE_VERSION}"
    nvm use "${NODE_VERSION}" >/dev/null
    done_msg "Node installed ($(node -v), $(npm -v))."
  fi
  command -v node >/dev/null 2>&1 || die "node not available after nvm install."
  command -v npm >/dev/null 2>&1 || die "npm not available after nvm install."
}

agent_browser_chrome_ready() {
  local json
  json="$(agent-browser doctor --offline --quick --json 2>/dev/null)" || return 1
  if command -v jq >/dev/null 2>&1; then
    printf '%s' "${json}" | jq -e '
      .checks[] | select(.id == "chrome.installed" and .status == "pass")
    ' >/dev/null 2>&1
    return $?
  fi
  printf '%s' "${json}" | python3 -c '
import json, sys
data = json.load(sys.stdin)
sys.exit(0 if any(
    c.get("id") == "chrome.installed" and c.get("status") == "pass"
    for c in data.get("checks", [])
) else 1)
'
}

ensure_agent_browser() {
  ensure_path_local_bin
  command -v npm >/dev/null 2>&1 || die "npm required before agent-browser install."

  if ! command -v agent-browser >/dev/null 2>&1; then
    install "Installing agent-browser globally via npm..."
    npm install -g agent-browser
    command -v agent-browser >/dev/null 2>&1 || die \
      "agent-browser install finished but not on PATH; ensure npm global bin is on PATH."
    done_msg "agent-browser CLI installed ($(command -v agent-browser))."
  fi

  if agent_browser_chrome_ready; then
    ok "agent-browser"
    return 0
  fi

  install "Installing agent-browser Chrome for Testing..."
  agent-browser install
  agent_browser_chrome_ready || die "agent-browser Chrome install finished but doctor still reports missing chrome.installed."
  done_msg "agent-browser browser runtime ready."
}

ensure_capa() {
  ensure_path_local_bin
  if command -v capa >/dev/null 2>&1; then
    ok "capa ($(capa --version 2>/dev/null || echo present))"
    return 0
  fi
  install "Installing capa (https://capa.sh/install.sh)..."
  curl -LsSf https://capa.sh/install.sh | sh
  ensure_path_local_bin
  if ! command -v capa >/dev/null 2>&1 && [[ -x "${HOME}/.capa/bin/capa" ]]; then
    export PATH="${HOME}/.capa/bin:${PATH}"
  fi
  command -v capa >/dev/null 2>&1 || die \
    "capa install finished but capa not on PATH; add capa's bin dir to PATH (see https://capa.sh/)."
  done_msg "capa installed ($(capa --version))."
}

ensure_docker() {
  if command -v docker >/dev/null 2>&1; then
    ok "docker"
    return 0
  fi
  die "docker not on PATH. Install Docker Engine or Desktop separately, then re-run."
}

main() {
  ensure_path_local_bin
  step "Checking prerequisites (repo: ${REPO_ROOT})"
  ensure_gh --report-ok
  ensure_gh_auth --report-ok
  ensure_uv --report-ok
  ensure_nvm_node_npm
  ensure_agent_browser
  ensure_capa
  ensure_docker
  done_msg "prerequisites ready."
}

main "$@"
