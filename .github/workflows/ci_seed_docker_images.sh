#!/usr/bin/env bash
# CI E2E image seed (sibling of ci.yml).
# Why: compose pulls hit Docker Hub anonymous rate limits; we seed from ECR Public
# and build a local http-echo stand-in instead.
set -euo pipefail

# --- config -----------------------------------------------------------------
MAX_ATTEMPTS="${CI_SEED_MAX_ATTEMPTS:-5}"
BASE_SLEEP_SECONDS="${CI_SEED_BASE_SLEEP_SECONDS:-5}"
ECR_LIBRARY="public.ecr.aws/docker/library"

# --- retry: transient / rate-limit docker errors ----------------------------
is_retryable() {
  local text="$1"
  [[ "$text" == *toomanyrequests* ]] \
    || [[ "$text" == *"Rate exceeded"* ]] \
    || [[ "$text" == *"rate limit"* ]] \
    || [[ "$text" == *"Too Many Requests"* ]] \
    || [[ "$text" == *"connection reset"* ]] \
    || [[ "$text" == *"Client.Timeout"* ]] \
    || [[ "$text" == *"TLS handshake timeout"* ]] \
    || [[ "$text" == *"i/o timeout"* ]] \
    || [[ "$text" == *"temporary failure"* ]] \
    || [[ "$text" == *"EOF"* ]]
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

# --- step: pull ECR Public mirror and retag as Hub-facing name --------------
image_present() {
  docker image inspect "$1" >/dev/null 2>&1
}

mirror_ecr_library() {
  local ecr_tag="$1" local_tag="$2"
  local src="${ECR_LIBRARY}/${ecr_tag}"
  if image_present "$local_tag"; then
    echo "already present: $local_tag"
    return 0
  fi
  echo "pull $src → tag $local_tag"
  retry_docker docker pull "$src"
  docker tag "$src" "$local_tag"
}

seed_nginx() {
  mirror_ecr_library "nginx:alpine" "nginx:alpine"
}

seed_redis() {
  # One ECR pull; several Hub-facing tags E2E / fixtures may request.
  mirror_ecr_library "redis:7-alpine" "redis:7-alpine"
  mirror_ecr_library "redis:7-alpine" "redis:alpine"
  mirror_ecr_library "redis:7-alpine" "redis:latest"
  mirror_ecr_library "redis:7-alpine" "redis"
}

# --- step: local http-echo stand-in (same listen port / default text) -------
http_echo_already_seeded() {
  local tag
  for tag in \
    hashicorp/http-echo:1.0.0 \
    hashicorp/http-echo:latest \
    hashicorp/http-echo
  do
    image_present "$tag" || return 1
  done
}

write_http_echo_sources() {
  local dir="$1"
  cat >"$dir/main.go" <<'EOF'
package main

import (
	"flag"
	"fmt"
	"net/http"
)

func main() {
	listen := flag.String("listen", ":5678", "")
	text := flag.String("text", "hello-world", "")
	flag.Parse()
	http.HandleFunc("/", func(w http.ResponseWriter, r *http.Request) {
		fmt.Fprint(w, *text)
	})
	_ = http.ListenAndServe(*listen, nil)
}
EOF
  cat >"$dir/Dockerfile" <<'EOF'
FROM public.ecr.aws/docker/library/golang:1.22-alpine AS build
WORKDIR /src
COPY main.go .
RUN CGO_ENABLED=0 go build -o /http-echo main.go
FROM public.ecr.aws/docker/library/alpine:3.20
COPY --from=build /http-echo /http-echo
ENTRYPOINT ["/http-echo"]
EOF
}

build_http_echo() {
  local dir
  dir="$(mktemp -d)"
  trap 'rm -rf "$dir"' RETURN
  write_http_echo_sources "$dir"
  echo "build local hashicorp/http-echo stand-in"
  retry_docker docker build -t hashicorp/http-echo:1.0.0 "$dir"
  docker tag hashicorp/http-echo:1.0.0 hashicorp/http-echo:latest
  docker tag hashicorp/http-echo:1.0.0 hashicorp/http-echo
}

seed_http_echo() {
  if http_echo_already_seeded; then
    echo "already present: hashicorp/http-echo"
    return 0
  fi
  build_http_echo
}

# --- main -------------------------------------------------------------------
main() {
  seed_nginx
  seed_redis
  seed_http_echo
  echo "docker image seed complete"
}

main "$@"
