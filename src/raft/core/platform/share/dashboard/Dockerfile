# Build context is ~/.raft/dashboard (Dockerfile + pyproject.toml + copied ``raft`` package).
# Same package as host CLI / controller — process is ``raft serve``.
FROM python:3.12-slim

ARG TARGETARCH

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl; \
    case "${TARGETARCH}" in \
      amd64) DOCKER_ARCH=x86_64; COMPOSE_ARCH=x86_64 ;; \
      arm64) DOCKER_ARCH=aarch64; COMPOSE_ARCH=aarch64 ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    DOCKER_VERSION=27.3.1; \
    COMPOSE_VERSION=5.5.1; \
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

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /bin/uv
COPY pyproject.toml ./
RUN uv pip compile pyproject.toml -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm -f /bin/uv /tmp/requirements.txt pyproject.toml

WORKDIR /opt
COPY raft/ /opt/raft/
ENV PYTHONPATH=/opt

# Compose sets working_dir=/raft and RAFT_DATA_HOME=/raft.
CMD ["python", "-m", "raft.services.dashboard"]
