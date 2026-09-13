#!/usr/bin/env bash
set -euo pipefail

RAFT_REPO_URL="${RAFT_REPO_URL:-https://github.com/danielnachumdev/raft.git}"
RAFT_BRANCH="${RAFT_BRANCH:-main}"
RAFT_KEEP_CHECKOUT="${RAFT_KEEP_CHECKOUT:-0}"
RAFT_INSTALL_QUIET="${RAFT_INSTALL_QUIET:-0}"

die() {
  printf 'install.sh: %s\n' "$*" >&2
  exit 1
}

log() {
  [[ "${RAFT_INSTALL_QUIET}" == "1" ]] && return 0
  printf '%s\n' "$*"
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
    log "Updating checkout at ${dest}"
    git -C "${dest}" remote set-url origin "${RAFT_REPO_URL}"
    git -C "${dest}" fetch --depth 1 origin "${RAFT_BRANCH}"
    git -C "${dest}" checkout -B "${RAFT_BRANCH}" "origin/${RAFT_BRANCH}"
  else
    if [[ -e "${dest}" ]]; then
      die "${dest} exists but is not a git checkout; set RAFT_HOME or remove it"
    fi
    log "Cloning ${RAFT_REPO_URL} (${RAFT_BRANCH}) → ${dest}"
    git clone --depth 1 --branch "${RAFT_BRANCH}" "${RAFT_REPO_URL}" "${dest}"
  fi
}

uv_tool_install() {
  uv tool install -q --force "$@"
}

install_from_path() {
  local path="$1"
  local editable="${2:-0}"
  log "Installing raft…"
  if [[ "${editable}" == "1" ]]; then
    uv_tool_install --editable "${path}"
  else
    uv_tool_install "${path}"
  fi
}

install_from_git() {
  local spec="git+${RAFT_REPO_URL}@${RAFT_BRANCH}"
  log "Installing raft…"
  uv_tool_install "${spec}"
}

finish_message() {
  ensure_path_local_bin

  if command -v raft >/dev/null 2>&1; then
    log "Installed raft → $(command -v raft)"
    raft -- --help >/dev/null 2>&1 || raft -h >/dev/null 2>&1 || true
  else
    echo "raft was installed but is not on PATH yet."
    echo "Open a new shell, or run:  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    echo "Then:  uv tool update-shell"
  fi
}

main() {
  ensure_git
  ensure_uv

  local checkout=""
  local editable

  if [[ "${RAFT_KEEP_CHECKOUT}" == "1" ]]; then
    local home="${RAFT_HOME:-${HOME}/raft}"
    clone_or_update "${home}"
    editable="${RAFT_EDITABLE:-1}"
    install_from_path "${home}" "${editable}"
  elif checkout="$(local_checkout_dir)"; then
    editable="${RAFT_EDITABLE:-1}"
    install_from_path "${checkout}" "${editable}"
  else
    install_from_git
  fi

  uv tool update-shell >/dev/null 2>&1 || true
  finish_message
}

main "$@"
