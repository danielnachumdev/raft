# AGENTS.md

Instructions for coding agents (and humans) changing **raft**. The GitHub-facing pitch is [`README.md`](README.md).

---

## What this repo is

Public product: CLI + Compose/nginx templates + tests. Operators typically run [`install.sh`](install.sh) (`uv tool install` from GitHub; no lasting clone by default) so `raft` is on `PATH`. **Durable operator data lives under `~/.raft/`** (override with `RAFT_DATA_HOME`), not in an install checkout.

Desired apps are **not** a committed inventory. Operators `apply` App manifests; registry files live in `~/.raft/state/apps/*.yaml`.

User-facing samples live under **[`examples/`](examples/)**: operator settings (`examples/settings.yaml`) and named service scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`, `grouped-volume-app`).

**Shipped:** App `volumes` / `envFile` / `group` / `expose: none` (required for multi-App stacks).

**Shipped:** App-manifest `${VAR}` / `${VAR:-default}` expansion at `raft apply` (one template for Dev/Prod; registry stores expanded YAML). Expansion runs on the **entire** manifest text (including comments) before YAML parse — escape demo placeholders as `$${NAME}` or omit them from comments. Bridge CI values into the container via `spec.env` / `spec.envFile` placeholders (`DATABASE_URL: ${CI_DATABASE_URL}`).

**Shipped:** Per-app scale-to-zero via `spec.scaling` (all fields required; omit = off). HTTP + `publicHost` only. Gate holding page + wake; controller idle-stop; healer skips intentional `scaledToZero`. Healing stays separate (`healing:` in settings).

---

## Architecture (hard rules)

```text
gate (public edge listeners from settings) → router (Host routing) → apps
```

| Layer | Role | Redeploy |
|-------|------|----------|
| **gate** | Outer nginx; http + stream; offline page when router/apps fail; holding page + wake for `spec.scaling` apps at zero | **`raft redeploy gate` refuses**; **reload** on generated TLS/http/stream change; **`raft gate recreate`** only for published edge ports |
| **router** | Inner nginx; Host → upstream | `raft redeploy router` |
| **apps** | One Compose service per applied App | `raft redeploy <name>` (tmp cutover) |

Cutover reloads **router** nginx. Render reloads **gate** nginx when on-disk `gate-{tls,http,stream}` differs from the last reload stamp (`state/gate-nginx.fingerprint`) and gate is running — so stale nginx (files already written, process never reloaded) is recovered on the next apply/render. Never use `redeploy` for gate — published-port changes need `gate recreate` (brief edge downtime).

### Concurrent apply / redeploy

nginx reload and `docker compose up` alone are **not** enough for correctness. Overlapping cutovers share tmp container names, upstream files, and `generated/` compose/nginx. A slow older deploy that finishes last can overwrite a newer one's image/upstream (last-finisher wins incorrectly). A second app's `render` mid-cutover rewrites all upstreams back to steady Compose names and tears live traffic.

**Intended behavior:** serialize mutative work with `flock` under `~/.raft/state/locks/`:

| Lock | Held by | Guarantees |
|------|---------|------------|
| `app-<name>.lock` | `apply` (registry + deploy), `redeploy` / `ensure_app_deployed`, `delete app` | One mutative pipeline per app; later-started waits then runs → newer deploy wins |
| `stack.lock` | render, sync, cutover, compose up/recreate, gate recreate, up/down | No torn `generated/` or mid-cutover upstream reset across apps |

Wait up to `RAFT_LOCK_TIMEOUT_SECONDS` (default **300**), then `OperatorError` with a Fix CTA. Contended waiters log `waiting for … lock`, then `acquired … lock`. Same-process nesting (redeploy → sync → render) re-enters safely. `doctor` / `status` do not take these locks.

### Ports and TLS

- Each app declares `spec.ports[]` with `expose: http | stream | host | none`.
- `expose: http` → Host routing via router (needs `publicHost`).
- `expose: stream` → gate `stream {}` (port must be declared in settings `edge.streams`).
- `expose: host` → app publishes the host port itself (gate not involved).
- `expose: none` → Compose `expose` only (internal); no host publish; no router; no `publicHost` required.
- Optional multi-app stacks: `spec.group`, `spec.dependsOn`, `spec.envFile` / `spec.env`, `spec.volumes`.
- `spec.tls`: **`off` (default)** or **`origin`**. HTTP-only apps need no PEMs. `tls: origin` requires `~/.raft/certs/<app>/origin.{pem,key}` and `edge.https`.
- Gate published ports come from `~/.raft/settings.yaml` `edge:` (`http`, `https`, `streams[]`), rendered into `generated/compose.edge.yaml`.

### Data home vs product templates

| Path | Role |
|------|------|
| `compose.yaml`, `nginx/` (`src/raft/share/`) | Product templates; synced into the data home on use |
| `~/.raft/settings.yaml` | Operator settings (logging + **edge** + optional **healing**); see [`examples/settings.yaml`](examples/settings.yaml) |
| `~/.raft/state/apps/*.yaml` | Applied desired state |
| `~/.raft/generated/` | Compose apps + compose.edge + router hosts + gate-http/stream/tls + **upstreams** |
| `~/.raft/apps/` | Sync checkouts |
| `~/.raft/deploy/` | Image/ref pins from sync/cutover |
| `~/.raft/state/locks/` | `flock` files serializing apply/redeploy/render (`app-<name>.lock`, `stack.lock`) |
| `~/.raft/state/scaling/` | Per-app scale-to-zero JSON + gate marker files (when `spec.scaling` is set) |
| `~/.raft/state/metrics/` | Controller resource samples (`resources.jsonl`); batched append for trends |
| `~/.raft/certs/` | Origin PEMs (only for `tls: origin`) |
| `~/.raft/logs/` | Structured log file (default) |

Do not commit consumer-specific upstreams, hosts, or manifests into this repo.

---

## Operator loop

1. `install.sh` (or `uv sync` in a clone; Python **3.8+**).
2. Private git apps: `raft auth setup <name> --repo git@host:owner/repo.git` (works before apply) → paste pubkey as read-only deploy key (`~/.ssh/raft/`). Then `raft auth test <name> --repo …` and `raft apply --git …`.
3. **Recommended ship path:** `raft apply --file …` or `raft apply --git …` with deploy **on** (default). Writes `~/.raft/state/apps/<name>.yaml`, then `ensure_app_deployed`: cutover if the Compose service is already running, start that service if the gate is up, else full stack `up`. Pass `--ref SHA` (and optional `--env-file` / `--env`) so CI first-boot and later cutovers share one command. Do **not** default to `--no-deploy` + `sync` + `redeploy` — `redeploy` requires the app service to already be running and fails on a new App with `service '…' is not running — bring the stack up first`.
4. If any app uses `tls: origin`, install PEMs under `~/.raft/certs/<name>/` **before** first deploy (apply-with-deploy or `raft up`).
5. `--no-deploy` only when you intentionally register desired state without bringing the app live (e.g. apply several manifests, then one `raft up`; or register before Origin PEMs exist). After that, deploy with `raft apply …` again (deploy on) or `raft up` / `raft redeploy` as appropriate.
6. Manual cold start when apps are already applied: `raft up` (refuses if stack already up; `down` first).
7. `raft doctor` before trusting the site (certs only for `tls: origin`; gate drift → `raft gate recreate`). Doctor is group-first: built-in **`raft`** (edge services; healthy docker/compose/generated/stack/port probes stay hidden), then App `spec.group` (at most one); ungrouped apps appear without a heading. Member labels drop the `{group}-` prefix under a group heading (Compose ids stay `raft-gate` / `raft-router` / `GROUP-NAME` for Docker; doctor shows `gate` / `router` under `raft`). Healthy OK lines append ports in use (gate: published host ports; apps/router: contract / listen ports).
8. `raft status` (optional `--json`, or `--live` to refresh the human table until Ctrl+C) for a point-in-time host + container CPU/memory/uptime snapshot — declared Compose limits vs live `docker stats` usage. Human NAME column drops `{group}-` (edge: `gate` / `router` with GROUP `raft`); JSON keeps Compose service ids. The always-on **controller** also samples the same plane each loop tick and **batch-appends** JSONL under `~/.raft/state/metrics/resources.jsonl` (flush every 10 samples or 60s); trend display is a separate serve-UI ticket.
9. Updates: prefer `raft apply … --ref …` again (handles first-boot and cutover). Use `raft redeploy <app>` only when the app Compose service is **already running** and you want cutover without re-writing the registry (optional `--ref` / `--force-sync`). `raft redeploy router` for the inner nginx. New edge listeners: `raft gate recreate`.
10. Tear down: `raft down`.

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
  group: demo               # optional; at most one group
  dependsOn: [other-app]        # optional
  envFile: /home/raft/.raft/demo.env
  env: { KEY: value }           # overrides envFile on clash
  volumes:
    - hostPath: /mnt/data/x
      containerPath: /data
      readOnly: false
  ports:
    - name: http
      containerPort: 80
      expose: http
    - name: smtp
      containerPort: 25
      expose: stream            # or host | none
      publicPort: 25
      protocol: tcp
  readiness:
    type: http                  # http | tcp | none
    port: http                  # port name
    path: /
    # Optional timing (defaults shown). timeoutSeconds must cover
    # startPeriodSeconds + retries×intervalSeconds (+ buffer).
    # timeoutSeconds: 120
    # startPeriodSeconds: 45
    # intervalSeconds: 2
    # probeTimeoutSeconds: 2
    # retries: 15
  resources:                    # optional; rendered as Compose deploy.resources
    limits:                     # ceiling (cpus / memory)
      cpu: "0.50"               # → deploy.resources.limits.cpus
      memory: 128M              # → deploy.resources.limits.memory
    reservations:               # floor / alias: requests
      cpu: "0.10"               # → deploy.resources.reservations.cpus
      memory: 32M               # → deploy.resources.reservations.memory
  # Optional scale-to-zero (omit = no scaling). When present, ALL fields required:
  # scaling:
  #   idleSeconds: 300          # stop after this much idle (HTTP activity via gate)
  #   wakeTimeoutSeconds: 60    # holding page → timeout page if wake exceeds this
  #   minUpSeconds: 60          # do not idle-stop until this long after wake/start
  # Requires at least one expose: http + publicHost (not stream/host/none alone).
  # Idle stop + gate holding/wake ship together. Holding hits do not count as
  # activity. Healer skips intentional scaledToZero. Healing is separate
  # (settings healing:); see examples/settings.yaml.
```

`apply --git` clones briefly, reads `.raft/app.yaml`, copies into `~/.raft/state/apps/`. `sync` refreshes sources then `render` regenerates `~/.raft/generated/`.

### `spec.scaling` (scale-to-zero)

Omit `spec.scaling` → no scaling. When present, **every** field is required (no defaults):

| Field | Role |
|-------|------|
| `idleSeconds` | Stop the Compose service after this much idle (activity recorded via gate on real proxied traffic) |
| `wakeTimeoutSeconds` | Holding page → timeout page if wake exceeds this |
| `minUpSeconds` | Do not idle-stop until this long after wake/start |

Eligible only with ≥1 `expose: http` port and `publicHost`. Not for stream/host/none-only apps. Controller idle-stops and wakes; gate serves a holding page (meta-refresh) and calls an internal wake API; holding-page reloads do not reset the idle timer. State under `~/.raft/state/scaling/`. Independent of `healing:` in settings — healer skips apps marked `scaledToZero`.

### `spec.resources` → Compose

App manifests declare CPU/memory under `spec.resources`. `raft render` emits Compose Swarm-style `deploy.resources` (same shape as Compose `limits` / `reservations`):

| App (`spec.resources`) | Compose (`deploy.resources`) | Role | Defaults |
|------------------------|------------------------------|------|----------|
| `limits.cpu` | `limits.cpus` | Ceiling — max CPU cores | `"0.50"` |
| `limits.memory` | `limits.memory` | Ceiling — max RAM | `128M` |
| `reservations.cpu` (or `requests.cpu`) | `reservations.cpus` | Floor — guaranteed CPU share | `"0.10"` |
| `reservations.memory` (or `requests.memory`) | `reservations.memory` | Floor — guaranteed RAM | `32M` |

Omit `resources` to get the defaults. Flat keys `cpus_limit` / `memory_limit` / `cpus_reservation` / `memory_reservation` under `resources` are also accepted. `raft status` shows these allocated limits next to live usage.

Private remotes stay as `git@github.com:…` in the manifest; auth rewrites clone URLs to `Host` aliases (`github.com-raft-<service>`).

---

## CLI surface (Fire)

Top-level **commands** (not nested groups, except `auth` and `gate`):

| Command | Purpose |
|---------|---------|
| `apply` | `--file` or `--git` (+ `--ref`, `--no-deploy`, `--force-sync`, `--env-file`, repeatable `--env`) — default **deploys** via `ensure_app_deployed`; `--no-deploy` registers only; `--env*` expand `${VAR}` in the manifest text (incl. comments) |
| `get` | `get apps` / `get app NAME` |
| `delete` | `delete app NAME` |
| `up` / `down` | Stack bring-up / tear-down (when apps already applied; not the usual CI path) |
| `sync` / `render` | Sources / regenerate `~/.raft/generated/` |
| `redeploy` | Cutover for an **already-running** app, or recreate `router` (`gate` refused). Fails if the app service is not up — use apply-with-deploy (or `raft up`) for first boot |
| `gate recreate` | Recreate gate for new published edge ports |
| `doctor` | Health + fix hints |
| `status` | Host + container resource usage (point-in-time; `--json` or `--live`) |
| `update` | Re-install CLI from GitHub (`install.sh`) |
| `uninstall` | Full removal (`--yes`; optional `--uv` to remove uv too) |
| `auth` | `setup` / `list` / `show` / `test` / `remove` |

Entry: `raft` console script → `raft.cli:run`. Prefer `install.sh` / `uv tool install` so `raft` is on `PATH`; in a bare checkout `uv run raft …` still works.

---

## Package map

| Path | Notes |
|------|-------|
| `src/raft/cli/` | Fire root + auth + gate; `deps.py` patched in tests |
| `src/raft/config/` | `~/.raft` paths, `settings.yaml` (logging + edge + healing), logging setup |
| `src/raft/models/` | Types + parse/registry: `App`, `AppSpec`, `AppDocument` / fields, `AppRegistry`, `PortSpec`, `Stack`, `ScalingSpec` |
| `src/raft/adapters/` | `shell`; `docker/` (`DockerStack` + edge/images/inspect); nginx upstreams; HTTP probe; host |
| `src/raft/services/apply/` | `AppApply`, `manifest_env` (`${VAR}` at apply) |
| `src/raft/services/auth/` | `GitAuthManager` + ssh/urls helpers |
| `src/raft/services/sync/` | `SourceSync` |
| `src/raft/services/render/` | `StackRenderer`, `compose_apps`, `gate_nginx`, `edge` handlers, `scaling_gate` (holding/wake snippets) |
| `src/raft/services/deploy/` | orchestrator, cutover, wait, locking, readiness |
| `src/raft/services/ops/` | doctor, status, uninstall, update, certs |
| `src/raft/controller/` | Always-on Compose `raft-controller` (smoke; heal when `healing.enabled`; idle-stop + wake when `spec.scaling`; metrics batch JSONL under `state/metrics/`; healer skips `scaledToZero`) |
| `src/raft/errors/` | Operator errors + CTAs |
| `src/raft/share/` | Product Compose + nginx templates (synced into data home) |
| `tests/` | `unit/` (100% cov), `integration/` (render artifacts), `meta/` (size/body guards), `e2e/` (Docker Compose) |

Compose mounts `generated/nginx/upstreams` into the router. Upstream files are keyed by app + port name (`<app>-<port>.conf`).

---

## Multi-repo responsibilities

| Repo | Role |
|------|------|
| **raft** (this) | Product + **Test** CI (Py 3.8–3.13). No Terraform here. |
| **Private ops** | GCP/VM + SSH job that pulls this repo onto the VPS |
| **Service repos** | Own `.raft/app.yaml` + their CI. **CI should** `raft apply --file .raft/app.yaml --ref $SHA --env …` (deploy on). Avoid `--no-deploy` + `raft redeploy` as the default pipeline — that breaks on a new App. |

Gate is never auto-recreated by service CI.

---

## Secrets on a VPS

If the host is rooted, container-readable secrets are burned. Prefer external store → inject on redeploy into **tmpfs** mounted only by the app. Avoid `.env` next to Compose, secrets in git/images. Gate/router must not receive DB secrets.

---

## Code style / structure

Enforceable defaults when adding or reshaping code under `src/raft/`:

- **File size:** aim for **~200 lines**; treat **300+** as a smell — split by responsibility before growing further.
- **Method size:** methods/functions **max ~20 lines**. Longer bodies **must delegate** to private helpers (`_…`) with **declarative names**.
- **Class-first:** prefer **almost no module-level functions**. Behavior lives on classes with a small, declarative public surface; helpers are **private** methods or composed collaborators.
- **SRP:** one class, one reason to change. Prefer inherit or **compose** over god-objects; extract when a module mixes parse/I/O/orchestration/diagnostics.
- **No re-export shims:** do not add functions that only forward to logic another module owns. Callers import the **owning** class/module directly (`AppDocument`, `AppRegistry`, …).
- **Imports:** all `import` / `from … import` at **module scope** (no function-local imports; fix cycles by restructuring).
- **Renames:** `git mv` when the path is already in git.

Exceptions: tiny pure helpers (e.g. path constants) and `@dataclass` field types — not compatibility wrappers.

---

## Tests & commits

- `uv sync --extra dev` (or `--group dev`) then:
 - `uv run pytest tests/unit` — **100%** branch coverage (`-n auto` + cov via pyproject)
 - `uv run pytest` — unit + integration + **meta** (default)
 - `uv run pytest tests/meta --no-cov` — codebase-as-artifact guards only (`@pytest.mark.meta`; file < 300 lines, bodies ≤ 20)
 - `uv run pytest tests/e2e -m e2e --no-cov -n0` — Docker required; serial; all CI Py versions
- Only commit when asked. Prefer `git mv` for renames.
- Do not reintroduce committed consumer app names, upstreams, or PEMs.
