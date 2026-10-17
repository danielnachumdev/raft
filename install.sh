#!/usr/bin/env bash
# Install raft via uv tool. Default ref = latest GitHub Release tag.
# Override: --ref <tag|branch|sha> or RAFT_REF (RAFT_BRANCH deprecated alias).
# Usage: curl -fsSL …/install.sh | bash
#        curl -fsSL …/install.sh | bash -s -- --ref main
set -euo pipefail

RAFT_REPO_URL="${RAFT_REPO_URL:-https://github.com/danielnachumdev/raft.git}"
# Capture explicit overrides before any defaults (empty = resolve latest Release).
_RAFT_REF_ENV="${RAFT_REF:-}"
_RAFT_BRANCH_ENV="${RAFT_BRANCH:-}"
RAFT_KEEP_CHECKOUT="${RAFT_KEEP_CHECKOUT:-0}"
RAFT_INSTALL_QUIET="${RAFT_INSTALL_QUIET:-0}"
RAFT_CLI_REF=""
RAFT_REF=""

_color_stdout() {
  [[ -z "${NO_COLOR:-}" ]] && { [[ -n "${FORCE_COLOR:-}" ]] || [[ -t 1 ]]; }
}

_color_stderr() {
  [[ -z "${NO_COLOR:-}" ]] && { [[ -n "${FORCE_COLOR:-}" ]] || [[ -t 2 ]]; }
}

if _color_stdout; then
  C_INFO=$'\033[36m'
  C_OK=$'\033[32m'
  C_WARN=$'\033[33m'
  C_RESET=$'\033[0m'
else
  C_INFO=''
  C_OK=''
  C_WARN=''
  C_RESET=''
fi

if _color_stderr; then
  C_ERR=$'\033[31m'
  C_ERR_RESET=$'\033[0m'
else
  C_ERR=''
  C_ERR_RESET=''
fi

die() {
  printf '%sinstall.sh: %s%s\n' "${C_ERR}" "$*" "${C_ERR_RESET}" >&2
  exit 1
}

log() {
  [[ "${RAFT_INSTALL_QUIET}" == "1" ]] && return 0
  printf '%s%s%s\n' "${C_INFO}" "$*" "${C_RESET}"
}

log_ok() {
  [[ "${RAFT_INSTALL_QUIET}" == "1" ]] && return 0
  printf '%s%s%s\n' "${C_OK}" "$*" "${C_RESET}"
}

log_warn() {
  [[ "${RAFT_INSTALL_QUIET}" == "1" ]] && return 0
  printf '%s%s%s\n' "${C_WARN}" "$*" "${C_RESET}"
}

usage() {
  cat <<'EOF'
Install raft (uv tool). Default: latest GitHub Release tag.

  curl -fsSL …/install.sh | bash
  curl -fsSL …/install.sh | bash -s -- --ref main
  RAFT_REF=v0.10.0 bash install.sh

Options:
  --ref <tag|branch|sha>   Install this git ref instead of latest Release
  -h, --help               Show this help

Env:
  RAFT_REF                 Same as --ref (wins over latest; --ref wins over env)
  RAFT_BRANCH              Deprecated alias for RAFT_REF
  RAFT_REPO_URL            Git remote (default: github.com/danielnachumdev/raft.git)
  RAFT_KEEP_CHECKOUT=1     Clone to RAFT_HOME (default ~/raft) and editable-install
EOF
}

parse_args() {
  while [[ $# -gt 0 ]]; do
    case "$1" in
      --ref)
        [[ $# -ge 2 ]] || die "--ref requires a value"
        RAFT_CLI_REF="$2"
        shift 2
        ;;
      --ref=*)
        RAFT_CLI_REF="${1#--ref=}"
        shift
        ;;
      -h | --help)
        usage
        exit 0
        ;;
      *)
        die "unknown argument: $1 (try --help)"
        ;;
    esac
  done
}

github_repo_slug() {
  local url="${1%.git}"
  if [[ "${url}" =~ github\.com[:/]([^/]+)/([^/]+)$ ]]; then
    printf '%s/%s\n' "${BASH_REMATCH[1]}" "${BASH_REMATCH[2]}"
    return 0
  fi
  die "cannot derive GitHub repo slug from RAFT_REPO_URL=${1}"
}

latest_release_tag() {
  local slug api tag
  slug="$(github_repo_slug "${RAFT_REPO_URL}")"
  api="https://api.github.com/repos/${slug}/releases/latest"
  tag="$(
    curl -fsSL "${api}" \
      | sed -n 's/^[[:space:]]*"tag_name":[[:space:]]*"\([^"]*\)".*/\1/p' \
      | head -1
  )" || die "could not resolve latest GitHub Release from ${api}
Fix: pass --ref <tag|branch|sha> or set RAFT_REF, and check outbound HTTPS"
  [[ -n "${tag}" ]] || die "latest Release JSON missing tag_name
Fix: pass --ref or set RAFT_REF"
  printf '%s\n' "${tag}"
}

resolve_install_ref() {
  if [[ -n "${RAFT_CLI_REF}" ]]; then
    RAFT_REF="${RAFT_CLI_REF}"
    return 0
  fi
  if [[ -n "${_RAFT_REF_ENV}" ]]; then
    RAFT_REF="${_RAFT_REF_ENV}"
    return 0
  fi
  if [[ -n "${_RAFT_BRANCH_ENV}" ]]; then
    log_warn "RAFT_BRANCH is deprecated; use RAFT_REF or --ref"
    RAFT_REF="${_RAFT_BRANCH_ENV}"
    return 0
  fi
  log "Resolving latest GitHub Release…"
  RAFT_REF="$(latest_release_tag)"
  log "Using release ${RAFT_REF}"
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
  log "uv not found; installing via https://astral.sh/uv/install.sh"
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
    log "Updating checkout at ${dest} (ref ${RAFT_REF})"
    git -C "${dest}" remote set-url origin "${RAFT_REPO_URL}"
    git -C "${dest}" fetch --depth 1 origin "${RAFT_REF}"
    git -C "${dest}" checkout -f FETCH_HEAD
  else
    if [[ -e "${dest}" ]]; then
      die "${dest} exists but is not a git checkout; set RAFT_HOME or remove it"
    fi
    log "Cloning ${RAFT_REPO_URL} (${RAFT_REF}) → ${dest}"
    git clone --depth 1 --branch "${RAFT_REF}" "${RAFT_REPO_URL}" "${dest}"
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
  local spec="git+${RAFT_REPO_URL}@${RAFT_REF}"
  log "Installing raft from ${spec}…"
  uv_tool_install "${spec}"
}

finish_message() {
  ensure_path_local_bin

  if command -v raft >/dev/null 2>&1; then
    log_ok "Installed raft (${RAFT_REF}) → $(command -v raft)"
    raft -- --help >/dev/null 2>&1 || raft -h >/dev/null 2>&1 || true
  else
    log_warn "raft was installed but is not on PATH yet."
    log_warn "Open a new shell, or run:  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    log_warn "Then:  uv tool update-shell"
  fi
}

main() {
  parse_args "$@"
  resolve_install_ref
  export RAFT_REF

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
