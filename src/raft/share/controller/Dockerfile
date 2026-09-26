# Build context is ~/.raft/controller (Dockerfile + copied ``raft`` package).
# Shared with the host CLI — same Python package, different process.
FROM python:3.12-slim

ARG TARGETARCH

# Docker CLI + Compose plugin (orchestrator shells out to ``docker`` / ``docker compose``).
RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    case "${TARGETARCH}" in \
      amd64) DOCKER_ARCH=x86_64; COMPOSE_ARCH=x86_64 ;; \
      arm64) DOCKER_ARCH=aarch64; COMPOSE_ARCH=aarch64 ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    DOCKER_VERSION=27.3.1; \
    COMPOSE_VERSION=2.29.7; \
    curl -fsSL \
      "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-${DOCKER_VERSION}.tgz" \
      | tar -xz -C /tmp; \
    mv /tmp/docker/docker /usr/local/bin/docker; \
    mkdir -p /usr/local/lib/docker/cli-plugins; \
    curl -fsSL \
      "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-${COMPOSE_ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose; \
    chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose; \
    apt-get purge -y curl; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/* /tmp/docker

WORKDIR /opt
COPY raft/ /opt/raft/
ENV PYTHONPATH=/opt

# Compose sets working_dir=/raft and RAFT_DATA_HOME=/raft (operator data home).
CMD ["python", "-m", "raft.controller"]
