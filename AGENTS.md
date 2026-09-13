# AGENTS.md

Instructions for coding agents (and humans) changing **raft**. The GitHub-facing pitch is [`README.md`](README.md).

---

## What this repo is

Public product: CLI + Compose/nginx templates + tests. A VPS typically clones **this** repo (e.g. `~/raft`) and runs `uv run raft …` from that checkout. Private cloud/CI that only provisions the VM is **out of tree**.

Desired apps are **not** a committed inventory. Operators `apply` App manifests; registry files live in gitignored `state/apps/*.yaml`.

---

## Architecture (hard rules)

```text
gate (public :80/:443, stable) → router (Host routing) → apps
```

| Layer | Role | Redeploy |
|-------|------|----------|
| **gate** | Outer nginx; offline page when router/apps fail | **Never** via `raft redeploy` |
| **router** | Inner nginx; Host → upstream | `raft redeploy router` |
| **apps** | One Compose service per applied App | `raft redeploy <name>` (tmp cutover) |

Cutover reloads **router** nginx, not gate. Never `raft redeploy gate`.

### TLS (hard requirement)

- Per-app Cloudflare Origin PEMs: `certs/<app>/origin.pem` + `origin.key` (gitignored; VPS only).
- `raft render` writes gate TLS snippets under `.generated/nginx/gate-tls/`.
- Gate **includes** those snippets. Missing PEMs make nginx reject the config → **HTTP and HTTPS die**.
- Install PEMs before `up` / recreating gate. `raft doctor` treats missing certs as failure.

### Generated vs committed

| Path | Role |
|------|------|
| `compose.yaml`, `nginx/gate/`, `nginx/router/default.conf`, `nginx/errors/` | Committed product templates |
| `state/apps/*.yaml` | Applied desired state (gitignored) |
| `.generated/` | Compose apps + router hosts + gate-tls + **upstreams** (gitignored) |
| `apps/` | Sync checkouts (gitignored) |
| `.deploy/` | Image/ref pins from sync/cutover (gitignored) |
| `certs/` | Origin PEMs (gitignored) |

Do not commit consumer-specific upstreams, hosts, or manifests into this repo.

---

## Operator loop

1. `uv sync` (Python **3.11+** only).
2. Private git apps: `raft auth setup <service>` → paste pubkey as read-only deploy key (`~/.ssh/raft/`).
3. `raft apply --file …` or `raft apply --git …` → writes `state/apps/<name>.yaml`, optionally syncs + renders.
4. Origin PEMs in place → `raft up` (refuses if stack already up; `down` first).
5. `raft doctor` before trusting the site.
6. Updates: `raft redeploy <app>` or `raft redeploy router`.
7. Tear down: `raft down`.

Useful checks: `curl -H 'Host: <publicHost>' http://127.0.0.1/`. Optional local hosts: `sudo python3 scripts/hosts_manager.py hold` (reads applied `publicHost` values; errors if none applied).

Logging: `raft.toml` `[logging]`; default `logs/raft.log`; override dir with `RAFT_LOG_DIR`. Terminal stays plain; file is structured.

---

## App manifest model

Canonical path in a service repo: `.raft/app.yaml` (also accepts `.raft/service.yaml`). Shape: `apiVersion: raft/v1`, `kind: App`, `metadata`, `spec`.

### `spec.source`

| `source` | Meaning |
|----------|---------|
| `local` | Tree under `spec.path`; already on disk |
| `git` | `spec.repo` + `spec.ref` → clone/fetch; Compose `build:` from contract |
| `docker` | `spec.image` (no tag) + `spec.ref` as pin/tag; still set `repo`/`path` so apply can refresh the manifest from git |

`apply --git` clones briefly, reads `.raft/app.yaml`, copies into `state/apps/`. `sync` (end of many flows) refreshes sources then `render` regenerates `.generated/`.

Private remotes stay as `git@github.com:…` in the manifest; auth rewrites clone URLs to `Host` aliases (`github.com-raft-<service>`).

---

## CLI surface (Fire)

Top-level **commands** (not nested groups, except `auth`):

| Command | Purpose |
|---------|---------|
| `apply` | `--file` or `--git` (+ `--ref`, `--no-deploy`, `--force-sync`) |
| `get` | `get apps` / `get app NAME` |
| `delete` | `delete app NAME` |
| `up` / `down` | Stack bring-up / tear-down |
| `sync` / `render` | Sources / regenerate `.generated/` |
| `redeploy` | App cutover or `router` |
| `doctor` | Health + fix hints |
| `auth` | `setup` / `list` / `show` / `test` / `remove` |

Entry: `raft` console script → `raft.cli:run`. Prefer `uv run raft …`.

---

## Package map

| Path | Notes |
|------|-------|
| `src/raft/cli/` | Fire root + auth; `deps.py` patched in tests |
| `src/raft/models/` | `App` / `Stack`, contract load/validate, registry paths |
| `src/raft/adapters/` | shell, docker, nginx upstreams, HTTP probe |
| `src/raft/services/` | apply, auth, sync, render, cutover, orchestrator, doctor |
| `src/raft/config/` | `raft.toml` + logging setup |
| `tests/` | Mirrors packages (`test_*`); class-based; **`--cov-fail-under=100`** |

Compose mounts `.generated/nginx/upstreams` into the router. Upstream files are written by `NginxUpstreams` under `.generated/nginx/upstreams/`.

---

## Multi-repo responsibilities

| Repo | Role |
|------|------|
| **raft** (this) | Product + **Test** CI (Py 3.11–3.13). No Terraform here. |
| **Private ops** | GCP/VM + SSH job that pulls this repo onto the VPS |
| **Service repos** | Own `.raft/app.yaml` + their CI (apply/redeploy against the VPS) |

Gate is never auto-redeployed by service CI.

---

## Secrets on a VPS

If the host is rooted, container-readable secrets are burned. Prefer external store → inject on redeploy into **tmpfs** mounted only by the app. Avoid `.env` next to Compose, secrets in git/images. Gate/router must not receive DB secrets.

---

## Tests & commits

- `uv sync --extra dev` then `uv run pytest` — keep **100%** branch coverage.
- Only commit when asked. Prefer `git mv` for renames.
- Do not reintroduce committed consumer app names, upstreams, or PEMs.
