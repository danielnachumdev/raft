#!/usr/bin/env bash
# Install raft via uv tool. Default: latest GitHub Release wheel (SPA baked in);
# git@tag fallback. Override: --ref / RAFT_REF. Usage: curl -fsSL …/install.sh | bash
#        curl -fsSL …/install.sh | bash -s -- --ref main
set -euo pipefail

RAFT_REPO_URL="${RAFT_REPO_URL:-https://github.com/danielnachumdev/raft.git}"
# Capture explicit overrides before any defaults (empty = resolve latest Release).
_RAFT_REF_ENV="${RAFT_REF:-}"
RAFT_KEEP_CHECKOUT="${RAFT_KEEP_CHECKOUT:-0}"
RAFT_INSTALL_QUIET="${RAFT_INSTALL_QUIET:-0}"
RAFT_PREFER_WHEEL="${RAFT_PREFER_WHEEL:-1}"
RAFT_CLI_REF=""
RAFT_REF=""
# Set by install_from_*; printed in finish_message (release tag / wheel / git / path).
RAFT_INSTALL_SOURCE=""
# Captured before reinstall when raft is already on PATH (OK: prev → current).
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
  RAFT_REPO_URL            Git remote (default: github.com/danielnachumdev/raft.git)
  RAFT_PREFER_WHEEL=0      Skip Release wheel; always git+@ref (needs Node 22+ to bake SPA)
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

# Node major required for Vite 8 / CI (git-ref and path installs bake the SPA).
_RAFT_NODE_MIN_MAJOR=22
_RAFT_NODE_BOOTSTRAP_VER="22.14.0"

_node_major() {
  local v
  v="$(node -p "process.versions.node.split('.')[0]" 2>/dev/null || true)"
  [[ "${v}" =~ ^[0-9]+$ ]] || { printf '0\n'; return 0; }
  printf '%s\n' "${v}"
}

ensure_node() {
  ensure_path_local_bin
  local major
  major="$(_node_major)"
  if [[ "${major}" -ge "${_RAFT_NODE_MIN_MAJOR}" ]] && command -v npm >/dev/null 2>&1; then
    return 0
  fi
  local arch plat url tgz node_root name
  plat="$(uname -s | tr '[:upper:]' '[:lower:]')"
  case "$(uname -m)" in
    x86_64 | amd64) arch="x64" ;;
    aarch64 | arm64) arch="arm64" ;;
    *) die "unsupported CPU for Node bootstrap: $(uname -m)" ;;
  esac
  [[ "${plat}" == "linux" || "${plat}" == "darwin" ]] \
    || die "unsupported OS for Node bootstrap: ${plat}"
  name="node-v${_RAFT_NODE_BOOTSTRAP_VER}-${plat}-${arch}"
  node_root="${HOME}/.local/${name}"
  mkdir -p "${HOME}/.local/bin"
  tgz="$(mktemp "${TMPDIR:-/tmp}/node.XXXXXX.tgz")"
  url="https://nodejs.org/dist/v${_RAFT_NODE_BOOTSTRAP_VER}/${name}.tar.gz"
  log "Node ${_RAFT_NODE_MIN_MAJOR}+ not found; installing v${_RAFT_NODE_BOOTSTRAP_VER} → ${node_root}"
  curl -fsSL "${url}" -o "${tgz}" || die "failed to download Node from ${url}"
  rm -rf "${node_root}"
  tar -xzf "${tgz}" -C "${HOME}/.local"
  rm -f "${tgz}"
  ln -sfn "${node_root}/bin/node" "${HOME}/.local/bin/node"
  ln -sfn "${node_root}/bin/npm" "${HOME}/.local/bin/npm"
  ln -sfn "${node_root}/bin/npx" "${HOME}/.local/bin/npx"
  ensure_path_local_bin
  major="$(_node_major)"
  [[ "${major}" -ge "${_RAFT_NODE_MIN_MAJOR}" ]] && command -v npm >/dev/null 2>&1 \
    || die "Node bootstrap finished but node/npm ${_RAFT_NODE_MIN_MAJOR}+ is not on PATH"
}

spa_out_dir() {
  printf '%s\n' "$1/src/raft/core/platform/share/serve/spa"
}

spa_already_baked() {
  local out
  out="$(spa_out_dir "$1")"
  [[ -f "${out}/index.html" && -d "${out}/assets" ]] || return 1
  find "${out}/assets" -type f -print -quit 2>/dev/null | grep -q .
}

bake_spa() {
  local root="$1"
  local spa="${root}/src/spa"
  local out
  out="$(spa_out_dir "${root}")"
  [[ -d "${spa}" ]] || die "SPA source missing at ${spa}"
  ensure_node
  log "Baking SPA…"
  (
    cd "${spa}"
    npm ci
    npm run build
  ) || die "SPA bake failed (npm ci / npm run build)"
  [[ -f "${out}/index.html" ]] || die "SPA bake missing ${out}/index.html"
  [[ -d "${out}/assets" ]] || die "SPA bake missing ${out}/assets/"
  find "${out}/assets" -type f -print -quit 2>/dev/null | grep -q . \
    || die "SPA bake left ${out}/assets/ empty"
}

bake_spa_if_needed() {
  local root="$1"
  if spa_already_baked "${root}"; then
    log "SPA already baked"
    return 0
  fi
  bake_spa "${root}"
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

# Shallow fetch of RAFT_REF (branch, tag, or SHA) into an empty directory.
clone_ref_to() {
  local dest="$1"
  mkdir -p "${dest}"
  git -C "${dest}" init -q
  git -C "${dest}" remote add origin "${RAFT_REPO_URL}"
  log "Fetching ${RAFT_REPO_URL} (${RAFT_REF}) → ${dest}"
  git -C "${dest}" fetch --depth 1 origin "${RAFT_REF}" \
    || die "git fetch failed for ref ${RAFT_REF}"
  git -C "${dest}" checkout -f FETCH_HEAD
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
    clone_ref_to "${dest}"
  fi
}

uv_tool_install() {
  uv tool install -q --force "$@"
}

install_from_path() {
  local path="$1"
  local editable="${2:-0}"
  bake_spa_if_needed "${path}"
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
  local tmp
  tmp="$(mktemp -d "${TMPDIR:-/tmp}/raft-install.XXXXXX")"
  # shellcheck disable=SC2064
  trap "rm -rf \"${tmp}\"" EXIT
  clone_ref_to "${tmp}"
  bake_spa "${tmp}"
  RAFT_INSTALL_SOURCE="git ref ${RAFT_REF} (baked path)"
  log "Installing raft from ${RAFT_INSTALL_SOURCE}…"
  uv_tool_install "${tmp}"
  rm -rf "${tmp}"
  trap - EXIT
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
  log_ok "OK: ${RAFT_PREVIOUS_VERSION} → ${ver}"
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
