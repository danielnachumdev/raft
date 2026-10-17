#!/usr/bin/env bash
# CI E2E image seed (sibling of ci.yml).
# Why: compose pulls hit Docker Hub anonymous rate limits. We pull private
# GHCR pins (mirrored by ci_seed_mirror.yml) and retag Hub-facing names.
#
# Pins (keep in sync with ci_seed_mirror.yml):
#   ghcr.io/danielnachumdev/raft/ci-seed-nginx:alpine
#   ghcr.io/danielnachumdev/raft/ci-seed-redis:7-alpine
#   ghcr.io/danielnachumdev/raft/ci-seed-http-echo:1.0.0
#
# Refresh: Actions → "CI seed mirror" → Run workflow (after bumping pins there
# and here together). Weekly cron also re-copies the same tags.
#
# Prerequisite: docker login ghcr.io with GITHUB_TOKEN (see ci.yml E2E job).
set -euo pipefail

# --- config -----------------------------------------------------------------
MAX_ATTEMPTS="${CI_SEED_MAX_ATTEMPTS:-5}"
BASE_SLEEP_SECONDS="${CI_SEED_BASE_SLEEP_SECONDS:-5}"
GHCR_OWNER="${CI_SEED_GHCR_OWNER:-danielnachumdev}"
GHCR_REPO="${CI_SEED_GHCR_REPO:-raft}"
GHCR_PREFIX="ghcr.io/${GHCR_OWNER}/${GHCR_REPO}"

NGINX_GHCR="${GHCR_PREFIX}/ci-seed-nginx:alpine"
REDIS_GHCR="${GHCR_PREFIX}/ci-seed-redis:7-alpine"
HTTP_ECHO_GHCR="${GHCR_PREFIX}/ci-seed-http-echo:1.0.0"

# --- retry: true network flakes only (not registry quota) -------------------
is_retryable() {
  local text="$1"
  [[ "$text" == *"connection reset"* ]] \
    || [[ "$text" == *"Client.Timeout"* ]] \
    || [[ "$text" == *"TLS handshake timeout"* ]] \
    || [[ "$text" == *"i/o timeout"* ]] \
    || [[ "$text" == *"temporary failure"* ]] \
    || [[ "$text" == *"EOF"* ]] \
    || [[ "$text" == *"network is unreachable"* ]]
}

is_missing_ghcr_pin() {
  local text="$1"
  [[ "$text" == *"not found"* ]] \
    || [[ "$text" == *"manifest unknown"* ]] \
    || [[ "$text" == *"unauthorized"* ]] \
    || [[ "$text" == *"denied"* ]] \
    || [[ "$text" == *"authentication required"* ]]
}

print_ghcr_fix_cta() {
  local src="$1"
  cat >&2 <<EOF

Fix: GHCR CI seed pin missing or unreadable: ${src}
  1. Open Actions → "CI seed mirror" → Run workflow (use this branch or main).
  2. Confirm packages exist under the raft repo (GHCR (repo-linked)).
  3. Re-run the E2E job (needs packages:read + docker login ghcr.io).
  Pin refresh docs: .github/workflows/ci_seed_mirror.yml

EOF
}

retry_docker() {
  local attempt=1 sleep_s="$BASE_SLEEP_SECONDS" out rc
  while true; do
    set +e
    out="$("$@" 2>&1)"
    rc=$?
    set -e
    if [[ "$rc" -eq 0 ]]; then
      [[ -n "$out" ]] && printf '%s\n' "$out"
      return 0
    fi
    if is_missing_ghcr_pin "$out"; then
      printf '%s\n' "$out" >&2
      return "$rc"
    fi
    if [[ "$attempt" -ge "$MAX_ATTEMPTS" ]] || ! is_retryable "$out"; then
      printf '%s\n' "$out" >&2
      return "$rc"
    fi
    echo "retry $attempt/$MAX_ATTEMPTS after transient docker error; sleep ${sleep_s}s" >&2
    printf '%s\n' "$out" >&2
    sleep "$sleep_s"
    attempt=$((attempt + 1))
    sleep_s=$((sleep_s * 2))
  done
}

# --- step: pull GHCR pin and retag as Hub-facing name -----------------------
image_present() {
  docker image inspect "$1" >/dev/null 2>&1
}

pull_ghcr_pin() {
  local src="$1"
  echo "pull $src"
  if ! retry_docker docker pull "$src"; then
    print_ghcr_fix_cta "$src"
    return 1
  fi
}

retag_from() {
  local src="$1" local_tag="$2"
  if image_present "$local_tag"; then
    echo "already present: $local_tag"
    return 0
  fi
  docker tag "$src" "$local_tag"
  echo "tagged $local_tag ← $src"
}

seed_nginx() {
  if image_present "nginx:alpine"; then
    echo "already present: nginx:alpine"
    return 0
  fi
  pull_ghcr_pin "$NGINX_GHCR"
  retag_from "$NGINX_GHCR" "nginx:alpine"
}

seed_redis() {
  # One GHCR pull; several Hub-facing tags E2E / fixtures may request.
  local need_pull=0
  local tag
  for tag in redis:7-alpine redis:alpine redis:latest redis; do
    if ! image_present "$tag"; then
      need_pull=1
      break
    fi
  done
  if [[ "$need_pull" -eq 0 ]]; then
    echo "already present: redis (Hub-facing tags)"
    return 0
  fi
  pull_ghcr_pin "$REDIS_GHCR"
  retag_from "$REDIS_GHCR" "redis:7-alpine"
  retag_from "$REDIS_GHCR" "redis:alpine"
  retag_from "$REDIS_GHCR" "redis:latest"
  retag_from "$REDIS_GHCR" "redis"
}

seed_http_echo() {
  local tag
  local need_pull=0
  for tag in \
    hashicorp/http-echo:1.0.0 \
    hashicorp/http-echo:latest \
    hashicorp/http-echo
  do
    if ! image_present "$tag"; then
      need_pull=1
      break
    fi
  done
  if [[ "$need_pull" -eq 0 ]]; then
    echo "already present: hashicorp/http-echo"
    return 0
  fi
  pull_ghcr_pin "$HTTP_ECHO_GHCR"
  retag_from "$HTTP_ECHO_GHCR" "hashicorp/http-echo:1.0.0"
  retag_from "$HTTP_ECHO_GHCR" "hashicorp/http-echo:latest"
  retag_from "$HTTP_ECHO_GHCR" "hashicorp/http-echo"
}

# --- main -------------------------------------------------------------------
main() {
  seed_nginx
  seed_redis
  seed_http_echo
  echo "docker image seed complete"
}

main "$@"
