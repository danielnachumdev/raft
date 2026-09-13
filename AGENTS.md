# AGENTS.md

Instructions for coding agents (and humans) changing **raft**. The GitHub-facing pitch is [`README.md`](README.md).

---

## What this repo is

Public product: CLI + Compose/nginx templates + tests. Operators typically run [`install.sh`](install.sh) (`uv tool install` from GitHub; no lasting clone by default) so `raft` is on `PATH`. **Durable operator data lives under `~/.raft/`** (override with `RAFT_DATA_HOME`), not in an install checkout.

Desired apps are **not** a committed inventory. Operators `apply` App manifests; registry files live in `~/.raft/state/apps/*.yaml`.

User-facing samples live under **[`examples/`](examples/)**: operator settings (`examples/settings.yaml`) and named service scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`).

---

## Architecture (hard rules)

```text
gate (public edge listeners from settings) → router (Host routing) → apps
```

| Layer | Role | Redeploy |
|-------|------|----------|
| **gate** | Outer nginx; http + stream; offline page when router/apps fail | **`raft redeploy gate` refuses**; use **`raft gate recreate`** when published ports change |
| **router** | Inner nginx; Host → upstream | `raft redeploy router` |
| **apps** | One Compose service per applied App | `raft redeploy <name>` (tmp cutover) |

Cutover reloads **router** nginx, not gate. Never use `redeploy` for gate — only the deliberate `gate recreate` path (brief edge downtime).

### Ports and TLS

- Each app declares `spec.ports[]` with `expose: http | stream | host`.
- `expose: http` → Host routing via router (needs `publicHost`).
- `expose: stream` → gate `stream {}` (port must be declared in settings `edge.streams`).
- `expose: host` → app publishes the host port itself (gate not involved).
- `spec.tls`: **`off` (default)** or **`origin`**. HTTP-only apps need no PEMs. `tls: origin` requires `~/.raft/certs/<app>/origin.{pem,key}` and `edge.https`.
- Gate published ports come from `~/.raft/settings.yaml` `edge:` (`http`, `https`, `streams[]`), rendered into `generated/compose.edge.yaml`.

### Data home vs product templates

| Path | Role |
|------|------|
| `compose.yaml`, `nginx/` (`src/raft/share/`) | Product templates; synced into the data home on use |
| `~/.raft/settings.yaml` | Operator settings (logging + **edge**); see [`examples/settings.yaml`](examples/settings.yaml) |
| `~/.raft/state/apps/*.yaml` | Applied desired state |
| `~/.raft/generated/` | Compose apps + compose.edge + router hosts + gate-http/stream/tls + **upstreams** |
| `~/.raft/apps/` | Sync checkouts |
| `~/.raft/deploy/` | Image/ref pins from sync/cutover |
| `~/.raft/certs/` | Origin PEMs (only for `tls: origin`) |
| `~/.raft/logs/` | Structured log file (default) |

Do not commit consumer-specific upstreams, hosts, or manifests into this repo.

---

## Operator loop

1. `install.sh` (or `uv sync` in a clone; Python **3.8+**).
2. Private git apps: `raft auth setup <name> --repo git@host:owner/repo.git` (works before apply) → paste pubkey as read-only deploy key (`~/.ssh/raft/`). Then `raft auth test <name> --repo …` and `raft apply --git …`.
3. `raft apply --file …` or `raft apply --git …` → writes `~/.raft/state/apps/<name>.yaml`, optionally syncs + renders.
4. If any app uses `tls: origin`, install PEMs under `~/.raft/certs/<name>/`.
5. `raft up` (refuses if stack already up; `down` first).
6. `raft doctor` before trusting the site (certs only for `tls: origin`; gate drift → `raft gate recreate`).
7. Updates: `raft redeploy <app>` or `raft redeploy router`. New edge listeners: `raft gate recreate`.
8. Tear down: `raft down`.

Useful checks: `curl -H 'Host: <publicHost>' http://127.0.0.1/`. Optional local hosts: `sudo python3 scripts/hosts.py hold` (reads applied `publicHost` values; errors if none applied). See [`scripts/README.md`](scripts/README.md).

Logging: `~/.raft/settings.yaml` `logging:`; default `~/.raft/logs/raft.log`; override dir with `RAFT_LOG_DIR`. Terminal stays plain; file is structured.

---

## App manifest model

Canonical path in a service repo: **`.raft/app.yaml`** only. Shape: `apiVersion: raft/v1`, `kind: App`, `metadata`, `spec`.

### `spec.source`

| `source` | Meaning |
|----------|---------|
| `local` | Tree under `spec.path`; already on disk |
| `git` | `spec.repo` + `spec.ref` → clone/fetch; Compose `build:` from manifest |
| `docker` | `spec.image` (no tag) + `spec.ref` as pin/tag; still set `repo`/`path` so apply can refresh the manifest from git |

### Ports / TLS / readiness (canonical)

```yaml
spec:
  publicHost: app.example.com   # required when any port uses expose=http
  tls: off                      # off | origin
  ports:
    - name: http
      containerPort: 80
      expose: http
    - name: smtp
      containerPort: 25
      expose: stream            # or host
      publicPort: 25
      protocol: tcp
  readiness:
    type: http                  # http | tcp | none
    port: http                  # port name
    path: /
```

`apply --git` clones briefly, reads `.raft/app.yaml`, copies into `~/.raft/state/apps/`. `sync` refreshes sources then `render` regenerates `~/.raft/generated/`.

Private remotes stay as `git@github.com:…` in the manifest; auth rewrites clone URLs to `Host` aliases (`github.com-raft-<service>`).

---

## CLI surface (Fire)

Top-level **commands** (not nested groups, except `auth` and `gate`):

| Command | Purpose |
|---------|---------|
| `apply` | `--file` or `--git` (+ `--ref`, `--no-deploy`, `--force-sync`) |
| `get` | `get apps` / `get app NAME` |
| `delete` | `delete app NAME` |
| `up` / `down` | Stack bring-up / tear-down |
| `sync` / `render` | Sources / regenerate `~/.raft/generated/` |
| `redeploy` | App cutover or `router` (`gate` refused) |
| `gate recreate` | Recreate gate for new published edge ports |
| `doctor` | Health + fix hints |
| `update` | Re-install CLI from GitHub (`install.sh`) |
| `auth` | `setup` / `list` / `show` / `test` / `remove` |

Entry: `raft` console script → `raft.cli:run`. Prefer `install.sh` / `uv tool install` so `raft` is on `PATH`; in a bare checkout `uv run raft …` still works.

---

## Package map

| Path | Notes |
|------|-------|
| `src/raft/cli/` | Fire root + auth + gate; `deps.py` patched in tests |
| `src/raft/models/` | `App`, `AppSpec` (`manifest.py`), `PortSpec`, `Stack` (`stack.py`) |
| `src/raft/adapters/` | shell, docker, nginx upstreams, HTTP/TCP probe |
| `src/raft/services/` | apply, auth, sync, render, edge handlers, cutover, orchestrator, doctor |
| `src/raft/config/` | `~/.raft` paths, `settings.yaml` (logging + edge), logging setup |
| `src/raft/share/` | Product Compose + nginx templates (synced into data home) |
| `tests/` | Mirrors packages (`test_*`); class-based; **`--cov-fail-under=100`** |

Compose mounts `generated/nginx/upstreams` into the router. Upstream files are keyed by app + port name (`<app>-<port>.conf`).

---

## Multi-repo responsibilities

| Repo | Role |
|------|------|
| **raft** (this) | Product + **Test** CI (Py 3.8–3.13). No Terraform here. |
| **Private ops** | GCP/VM + SSH job that pulls this repo onto the VPS |
| **Service repos** | Own `.raft/app.yaml` + their CI (apply/redeploy against the VPS) |

Gate is never auto-recreated by service CI.

---

## Secrets on a VPS

If the host is rooted, container-readable secrets are burned. Prefer external store → inject on redeploy into **tmpfs** mounted only by the app. Avoid `.env` next to Compose, secrets in git/images. Gate/router must not receive DB secrets.

---

## Tests & commits

- `uv sync --extra dev` then `uv run pytest` — keep **100%** branch coverage.
- **No function-local imports** — all `import` / `from … import` belong at module scope (fix cycles by restructuring, not by lazy imports).
- Only commit when asked. Prefer `git mv` for renames.
- Do not reintroduce committed consumer app names, upstreams, or PEMs.
