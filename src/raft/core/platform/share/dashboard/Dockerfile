# Build context is ~/.raft/dashboard (Dockerfile + pyproject.toml + copied ``raft`` package).
# nginx terminates auth (password / oauth2-proxy / external) before the SPA.
FROM python:3.12-slim

ARG TARGETARCH

RUN set -eux; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl nginx-light; \
    case "${TARGETARCH}" in \
      amd64) DOCKER_ARCH=x86_64; COMPOSE_ARCH=x86_64; OAUTH_ARCH=amd64 ;; \
      arm64) DOCKER_ARCH=aarch64; COMPOSE_ARCH=aarch64; OAUTH_ARCH=arm64 ;; \
      *) echo "unsupported TARGETARCH=${TARGETARCH}" >&2; exit 1 ;; \
    esac; \
    DOCKER_VERSION=27.3.1; \
    COMPOSE_VERSION=5.5.1; \
    OAUTH2_PROXY_VERSION=7.8.1; \
    curl -fsSL \
      "https://download.docker.com/linux/static/stable/${DOCKER_ARCH}/docker-${DOCKER_VERSION}.tgz" \
      | tar -xz -C /tmp; \
    mv /tmp/docker/docker /usr/local/bin/docker; \
    mkdir -p /usr/local/lib/docker/cli-plugins; \
    curl -fsSL \
      "https://github.com/docker/compose/releases/download/v${COMPOSE_VERSION}/docker-compose-linux-${COMPOSE_ARCH}" \
      -o /usr/local/lib/docker/cli-plugins/docker-compose; \
    curl -fsSL \
      "https://github.com/oauth2-proxy/oauth2-proxy/releases/download/v${OAUTH2_PROXY_VERSION}/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-${OAUTH_ARCH}.tar.gz" \
      | tar -xz -C /tmp; \
    mv /tmp/oauth2-proxy-v${OAUTH2_PROXY_VERSION}.linux-${OAUTH_ARCH}/oauth2-proxy \
      /usr/local/bin/oauth2-proxy; \
    chmod +x /usr/local/bin/docker /usr/local/lib/docker/cli-plugins/docker-compose \
      /usr/local/bin/oauth2-proxy; \
    apt-get purge -y curl; \
    apt-get autoremove -y; \
    rm -rf /var/lib/apt/lists/* /tmp/docker /tmp/oauth2-proxy-*

COPY --from=ghcr.io/astral-sh/uv:0.8.22 /uv /bin/uv
COPY pyproject.toml ./
RUN uv pip compile pyproject.toml -o /tmp/requirements.txt \
    && uv pip install --system --no-cache -r /tmp/requirements.txt \
    && rm -f /bin/uv /tmp/requirements.txt pyproject.toml

WORKDIR /opt
COPY raft/ /opt/raft/
COPY login.html /opt/dashboard/login.html
COPY unauthorized.html /opt/dashboard/unauthorized.html
COPY start.sh /start.sh
RUN chmod +x /start.sh
ENV PYTHONPATH=/opt

# Compose sets working_dir=/raft and RAFT_DATA_HOME=/raft.
# Entrypoint: app on loopback → wait ready → nginx auth edge.
ENTRYPOINT ["/start.sh"]
