# Fresh operator-style install: ``uv tool install`` from the build context
# (after SPA bake) or from git. Operators on VMs use Release **wheels** via
# install.sh (Node-free); this image validates package-data / CLI smoke.
#
#   docker build -f tests/e2e/fresh_install/Dockerfile --build-arg RAFT_REF=workspace .
#
# ``RAFT_REF`` defaults to ``workspace``. CI bakes ``src/spa`` then passes
# ``workspace``. Use a git ref only when intentionally testing git+ install
# (hashed SPA assets are not in git).
FROM python:3.12-slim-bookworm

RUN apt-get update \
    && apt-get install -y --no-install-recommends ca-certificates curl git \
    && rm -rf /var/lib/apt/lists/*

RUN curl -LsSf https://astral.sh/uv/install.sh | sh
ENV PATH="/root/.local/bin:${PATH}"

ARG RAFT_REPO_URL=https://github.com/danielnachumdev/raft.git
ARG RAFT_REF=workspace

COPY pyproject.toml LICENSE README.md /tmp/raft-src/
COPY src /tmp/raft-src/src
COPY tests/e2e/fresh_install/smoke.sh /smoke.sh
COPY tests/e2e/fresh_install/fixture-app.yaml /opt/raft-fresh-fixture/.raft/app.yaml

RUN if [ "${RAFT_REF}" = "workspace" ]; then \
      test -f /tmp/raft-src/src/raft/core/platform/share/serve/spa/index.html \
        || { echo "SPA not baked; run: cd src/spa && npm ci && npm run build" >&2; exit 1; }; \
      uv tool install --force /tmp/raft-src; \
    else \
      uv tool install --force "git+${RAFT_REPO_URL}@${RAFT_REF}"; \
    fi \
    && rm -rf /tmp/raft-src \
    && chmod +x /smoke.sh

ENV RAFT_DATA_HOME=/tmp/raft-fresh-install
CMD ["/smoke.sh"]
