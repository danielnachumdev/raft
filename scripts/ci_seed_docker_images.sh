#!/usr/bin/env bash
# Pre-seed images E2E needs so compose does not hit Docker Hub anonymous
# rate limits (toomanyrequests). Library images come from Amazon ECR Public;
# hashicorp/http-echo is a tiny local stand-in (same listen port / default text).
set -euo pipefail

mirror() {
  local src="$1" dest="$2"
  if docker image inspect "$dest" >/dev/null 2>&1; then
    echo "already present: $dest"
    return 0
  fi
  echo "pull $src → tag $dest"
  docker pull "$src"
  docker tag "$src" "$dest"
}

mirror public.ecr.aws/docker/library/nginx:alpine nginx:alpine
mirror public.ecr.aws/docker/library/redis:7-alpine redis:7-alpine
mirror public.ecr.aws/docker/library/redis:7-alpine redis:alpine
mirror public.ecr.aws/docker/library/redis:7-alpine redis:latest
mirror public.ecr.aws/docker/library/redis:7-alpine redis

_seed_http_echo() {
  local tag
  for tag in hashicorp/http-echo:1.0.0 hashicorp/http-echo:latest hashicorp/http-echo; do
    if ! docker image inspect "$tag" >/dev/null 2>&1; then
      _build_http_echo
      return 0
    fi
  done
  echo "already present: hashicorp/http-echo"
}

_build_http_echo() {
  local dir
  dir="$(mktemp -d)"
  trap 'rm -rf "$dir"' RETURN
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
  echo "build local hashicorp/http-echo stand-in"
  docker build -t hashicorp/http-echo:1.0.0 "$dir"
  docker tag hashicorp/http-echo:1.0.0 hashicorp/http-echo:latest
  docker tag hashicorp/http-echo:1.0.0 hashicorp/http-echo
}

_seed_http_echo
echo "docker image seed complete"
