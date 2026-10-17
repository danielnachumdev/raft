#!/usr/bin/env bash
# Install raft via uv tool. Default: latest GitHub Release wheel (SPA baked in);
# git@tag fallback. Override: --ref / RAFT_REF. Usage: curl -fsSL …/install.sh | bash
#        curl -fsSL …/install.sh | bash -s -- --ref main
set -euo pipefail

RAFT_REPO_URL="${RAFT_REPO_URL:-https://github.com/danielnachumdev/raft.git}"
# Capture explicit overrides before any defaults (empty = resolve latest Release).
_RAFT_REF_ENV="${RAFT_REF:-}"
_RAFT_BRANCH_ENV="${RAFT_BRANCH:-}"
RAFT_KEEP_CHECKOUT="${RAFT_KEEP_CHECKOUT:-0}"
RAFT_INSTALL_QUIET="${RAFT_INSTALL_QUIET:-0}"
RAFT_PREFER_WHEEL="${RAFT_PREFER_WHEEL:-1}"
RAFT_CLI_REF=""
RAFT_REF=""
# Set by install_from_*; printed in finish_message (release tag / wheel / git / path).
RAFT_INSTALL_SOURCE=""
# Captured before reinstall when raft is already on PATH (PREVIOUS → CURRENT).
RAFT_PREVIOUS_VERSION=""

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
Install raft (uv tool). Default: latest GitHub Release wheel (SPA baked in).

  curl -fsSL …/install.sh | bash
  curl -fsSL …/install.sh | bash -s -- --ref main
  RAFT_REF=v0.10.0 bash install.sh

Options:
  --ref <tag|branch|sha>   Install this git ref (wheel tried first when tag has one)
  -h, --help               Show this help

Env:
  RAFT_REF                 Same as --ref (wins over latest; --ref wins over env)
  RAFT_BRANCH              Deprecated alias for RAFT_REF
  RAFT_REPO_URL            Git remote (default: github.com/danielnachumdev/raft.git)
  RAFT_PREFER_WHEEL=0      Skip Release wheel; always git+@ref
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

release_wheel_url() {
  local tag="$1"
  local slug api url
  [[ -n "${tag}" ]] || return 1
  slug="$(github_repo_slug "${RAFT_REPO_URL}")"
  api="https://api.github.com/repos/${slug}/releases/tags/${tag}"
  url="$(
    curl -fsSL "${api}" 2>/dev/null \
      | sed -n 's/^[[:space:]]*"browser_download_url":[[:space:]]*"\([^"]*\.whl\)".*/\1/p' \
      | head -1
  )" || return 1
  [[ -n "${url}" ]] || return 1
  printf '%s\n' "${url}"
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
  if [[ "${editable}" == "1" ]]; then
    RAFT_INSTALL_SOURCE="editable path ${path}"
  else
    RAFT_INSTALL_SOURCE="path ${path}"
  fi
  log "Installing raft from ${RAFT_INSTALL_SOURCE}…"
  if [[ "${editable}" == "1" ]]; then
    uv_tool_install --editable "${path}"
  else
    uv_tool_install "${path}"
  fi
}

install_from_wheel_url() {
  local url="$1"
  local base
  base="$(basename "${url}")"
  RAFT_INSTALL_SOURCE="Release ${RAFT_REF} wheel ${base}"
  log "Installing raft from ${RAFT_INSTALL_SOURCE}…"
  log "  ${url}"
  uv_tool_install "${url}"
}

install_from_git() {
  local spec="git+${RAFT_REPO_URL}@${RAFT_REF}"
  RAFT_INSTALL_SOURCE="git ref ${RAFT_REF} (${spec})"
  log "Installing raft from ${RAFT_INSTALL_SOURCE}…"
  uv_tool_install "${spec}"
}

try_install_release_wheel() {
  local url
  [[ "${RAFT_PREFER_WHEEL}" == "1" ]] || return 1
  url="$(release_wheel_url "${RAFT_REF}")" || return 1
  log "Found Release wheel for ${RAFT_REF}"
  install_from_wheel_url "${url}"
}

capture_previous_version() {
  if command -v raft >/dev/null 2>&1; then
    RAFT_PREVIOUS_VERSION="$(raft --version 2>/dev/null || true)"
  fi
}

finish_version_lines() {
  local ver="${1:-}"
  [[ -n "${ver}" ]] || return 0
  if [[ -z "${RAFT_PREVIOUS_VERSION}" ]]; then
    log_ok "${ver}"
    return 0
  fi
  if [[ "${RAFT_PREVIOUS_VERSION}" == "${ver}" ]]; then
    log_ok "raft is already up to date"
    log_ok "${ver}"
    return 0
  fi
  log_ok "PREVIOUS → CURRENT"
  log_ok "${RAFT_PREVIOUS_VERSION} → ${ver}"
}

finish_message() {
  ensure_path_local_bin

  if command -v raft >/dev/null 2>&1; then
    log_ok "Installed raft → $(command -v raft)"
    if [[ -n "${RAFT_INSTALL_SOURCE}" ]]; then
      log_ok "Source: ${RAFT_INSTALL_SOURCE}"
    fi
    if ver="$(raft --version 2>/dev/null)"; then
      finish_version_lines "${ver}"
    fi
  else
    log_warn "raft was installed but is not on PATH yet."
    log_warn "Open a new shell, or run:  export PATH=\"\${HOME}/.local/bin:\${PATH}\""
    log_warn "Then:  uv tool update-shell"
    if [[ -n "${RAFT_INSTALL_SOURCE}" ]]; then
      log_warn "Source: ${RAFT_INSTALL_SOURCE}"
    fi
  fi
}

main() {
  parse_args "$@"
  resolve_install_ref
  export RAFT_REF

  ensure_git
  ensure_uv
  capture_previous_version

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
  elif try_install_release_wheel; then
    :
  else
    if [[ "${RAFT_PREFER_WHEEL}" == "1" ]]; then
      log_warn "No wheel asset for ${RAFT_REF}; falling back to git"
    fi
    install_from_git
  fi

  uv tool update-shell >/dev/null 2>&1 || true
  finish_message
}

main "$@"
