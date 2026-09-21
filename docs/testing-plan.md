# Raft testing tiers — unit / integration / e2e

Living plan for how tests are laid out and what each tier owns.

## Tiers

| Tier | Path | What it proves | Docker? | Coverage |
|------|------|----------------|---------|----------|
| **unit** | `tests/unit/` | Parsers, services, CLI with mocks | No | **100%** branch (`--cov-fail-under=100`) |
| **integration** | `tests/integration/` | `app.yaml` → apply/render → compose + nginx files match intent | No | Not gated |
| **e2e** | `tests/e2e/` | Rendered apps Compose actually runs; containers behave | Yes | Not gated |

Default local/CI: **unit + integration**. E2E runs in CI on **every Python matrix version** when Docker is available; locally skipped if Docker is missing.

**Doctor groups:** built-in group `raft` (edge services; healthy host/platform probes hidden); App `spec.group` (at most one). Ungrouped apps have no heading. Member labels are Compose service ids: ungrouped `{name}`, grouped `{group}-{name}`; edge is `raft-gate` / `raft-router` (containers `raft-{service}-1` via project `raft`). OK lines append ports in use for every service.

## Layout

```text
tests/
  shared/                 # cross-tier helpers only
  fixtures/               # static App YAML trees
  unit/                   # former tests/ tree
  integration/
  e2e/
```

Markers: `unit`, `integration`, `e2e`.

## Commands

```bash
uv sync --extra dev
uv run pytest tests/unit --cov=raft --cov-fail-under=100   # coverage gate
uv run pytest tests/unit tests/integration -q              # default
uv run pytest tests/e2e -m e2e                             # needs Docker
uv run pytest -q                                           # unit + integration (see pyproject)
```

## Integration matrix

| Test ID | Fixture | Asserts |
|---------|---------|---------|
| `int_http_only` | single http App | compose apps, hosts.conf, upstream |
| `int_http_plus_stream` | http + stream | stream gate + router http only |
| `int_host_publish` | `expose: host` | host port publish in compose |
| `int_expose_none_volume` | none + volume + env | expose only, bind, env_file/environment |
| `int_multi_app_group` | groups + dependsOn | per-service depends_on |
| `int_tls_origin` | tls origin | gate-tls fragments |
| `int_edge_settings` | edge settings | compose.edge.yaml ports |

## E2E matrix (v1 — apps Compose only)

| Test ID | Asserts |
|---------|---------|
| `e2e_single_http_echo` | container up; HTTP 200 |
| `e2e_expose_none_not_published` | no host publish; TCP on network |
| `e2e_volume_bind` | host bind visible in container |
| `e2e_depends_on_order` | depends_on + both up |
| `e2e_multi_app_same_project` | DNS by metadata.name |

**Phase 2 (not yet):** gate/router cutover, certs, git apply.

## E2E setup / teardown

1. Session: detect Docker; skip e2e if missing (local). CI always has Docker.
2. Per test: temp `RAFT_DATA_HOME` → apply fixtures → render → apps-only compose overlay (`compose.e2e.yaml`, router stub + healthchecks stripped, ephemeral `127.0.0.1::port` for probes) → `docker compose -p raft-e2e-<id> up -d`.
3. Always teardown: `down -v --remove-orphans` + remove project-labeled containers; delete temp home.
4. Tiny images only (`hashicorp/http-echo`, `redis:alpine`).
5. No pytest-xdist for e2e; compose CLI (not testcontainers) for Python 3.8–3.13.

## CI

- Matrix job (Py 3.8–3.13): unit (coverage 100%) + integration.
- Parallel matrix job (Py 3.8–3.13): `pytest tests/e2e -m e2e` with Docker socket.
