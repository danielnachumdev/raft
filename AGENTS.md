# AGENTS.md

Instructions for coding agents (and humans) changing **raft**. The GitHub-facing pitch is [`README.md`](README.md).

---

## What this repo is

Public product: CLI + Compose/nginx templates + tests. Operators typically run [`install.sh`](install.sh) (`uv tool install` from GitHub; no lasting clone by default) so `raft` is on `PATH`. **Durable operator data lives under `~/.raft/`** (override with `RAFT_DATA_HOME`), not in an install checkout.

Desired apps are **not** a committed inventory. Operators `apply` App manifests; registry files live in `~/.raft/state/apps/*.yaml`.

User-facing samples live under **[`examples/`](examples/)**: operator settings (`examples/settings.yaml`) and named service scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`, `grouped-volume-app`). Human-oriented App manifest + preprocess overview: [`docs/app-manifest.md`](docs/app-manifest.md) (this file stays the exhaustive contract).

**Shipped:** App `volumes` / `envFile` / `group` / `expose: none` (required for multi-App stacks).

**Shipped:** App-manifest apply preprocess (`ManifestPreprocessor`): resolve `${{ if … }}` / `${{ endif }}` (`==` `!=` `&&` `||`, nesting allowed; operands are quoted strings or `${VAR}` / `${VAR:-default}`), then expand remaining `${VAR}` in the kept text, then YAML parse. Full-line `#` comments are ignored by preprocess (so demos may use a single `$` under `#`). `--env*` supply **string values** only (any shape). Bridge CI values into the container via `spec.env` / `spec.envFile` placeholders (`DATABASE_URL: ${CI_DATABASE_URL}`).

**Shipped:** Per-app scale-to-zero via `spec.scaling` (`idleSeconds` + `minUpSeconds` required; `wakeTimeoutSeconds` defaults to **60**; omit the block = off). HTTP + `publicHost` only. Gate holding page + wake; controller idle-stop (co-stops `dependsOn` with `scaleWithParent` default true); healer skips intentional `scaledToZero`. Healing stays separate (`healing:` in settings). After the wake budget, the product timeout page shows an admin CTA plus a server-minted diagnostic id (same `id=` on controller wake/timeout logs).

**Shipped:** `raft serve` localhost ops UI — packaged React SPA (`share/serve/spa/`) + FastAPI JSON/actions/logs APIs; shared `StatusRead` / `MetricsRead` with CLI; trends from controller `resources.jsonl`. Source in `src/spa/`; not an edge listener.

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

- Each app declares `spec.ports[]` with `expose: http | stream | host | none`. Omit `ports` or use `ports: []` for **worker** Apps with no listeners (see below).
- `expose: http` → Host routing via router (needs `publicHost`).
- `expose: stream` → gate `stream {}` (port must be declared in settings `edge.streams`).
- `expose: host` → app publishes the host port itself (gate not involved).
- `expose: none` → Compose `expose` only (internal); no host publish; no router; no `publicHost` required.
- Optional multi-app stacks: `spec.group`, `spec.dependsOn`, `spec.envFile` / `spec.env`, `spec.volumes`.
- `spec.tls`: **`off` (default)**, **`origin`**, or **`acme`**. HTTP-only apps need no PEMs. `tls: origin` requires `~/.raft/certs/<app>/origin.{pem,key}` and `edge.https`. `tls: acme` requires `publicHost`, ≥1 `expose: http`, `edge.http` + `edge.https`, and `acme.email` in settings; live material is `~/.raft/certs/<app>/acme.{pem,key}` (never `origin.*`). Apply/`up` best-effort HTTP-01 after the gate is up (failures persist `lastError` under `state/acme/` and do **not** fail deploy). When live PEMs exist: gate SNI + HTTP→HTTPS redirect (challenge path carved out).
- Gate published ports come from `~/.raft/settings.yaml` `edge:` (`http`, `https`, `streams[]`), rendered into `generated/compose.edge.yaml`.

### Worker Apps (no listeners)

Background / worker Apps that only run a long-lived process may **omit `spec.ports`** or set `ports: []`. Happy path: `readiness.type: none` (default when ports are empty), `tls: off` (or omitted), no `scaling`. Do **not** invent a dummy port.

**Health model:** no Host / TCP probe and no edge exposure. Health is Docker process liveness + the always-on healer + doctor runtime checks. `raft status` / metrics / `raft serve` still sample the Compose service like any other app. Deploy does **not** wait-until-running for `readiness: none`. Scale-to-zero and `tls: origin|acme` are not eligible (need `expose: http` / ports).

### Data home vs product templates

| Path | Role |
|------|------|
| `compose.yaml`, `nginx/` (`src/raft/share/`) | Product templates; synced into the data home on use |
| `~/.raft/settings.yaml` | Operator settings (logging + **edge** + optional **healing** / **metrics** / **acme**); see [`examples/settings.yaml`](examples/settings.yaml) |
| `~/.raft/state/apps/*.yaml` | Applied desired state |
| `~/.raft/generated/` | Compose apps + compose.edge + router hosts + gate-http/stream/tls + **upstreams** |
| `~/.raft/apps/` | Sync checkouts |
| `~/.raft/deploy/` | Image/ref pins from sync/cutover |
| `~/.raft/state/locks/` | `flock` files serializing apply/redeploy/render (`app-<name>.lock`, `stack.lock`) |
| `~/.raft/state/serve/` | Per-port `raft serve` flock + pid (`port-<port>.lock`); used by start / `--stop` |
| `~/.raft/state/scaling/` | Per-app scale-to-zero JSON + gate marker files (when `spec.scaling` is set) |
| `~/.raft/state/metrics/` | Controller resource samples (`resources.jsonl`); batched append; daily + size-split rotation like logs (`resources.jsonl.YYYY-MM-DD[.N]`); `metrics.retentionMaxAgeDays` / `retentionMaxBytes` |
| `~/.raft/state/acme/` | ACME account + HTTP-01 webroot + per-app state JSON (when using `tls: acme`) |
| `~/.raft/certs/` | Origin PEMs (`origin.*` for `tls: origin`) and ACME live material (`acme.*` for `tls: acme`) |
| `~/.raft/logs/` | Structured log file (default); daily + size-split rotation via `logging.retentionMaxAgeDays` / `retentionMaxBytes` (at CLI `setup_logging`) |

Do not commit consumer-specific upstreams, hosts, or manifests into this repo.

---

## Operator loop

1. `install.sh` (or `uv sync` in a clone; Python **3.9+**).
2. Private git apps: `raft auth setup <name> --repo git@host:owner/repo.git` (works before apply) → paste pubkey as read-only deploy key (`~/.ssh/raft/`). Then `raft auth test <name> --repo …` and `raft apply --git …`.
3. **Recommended ship path:** `raft apply --file …` or `raft apply --git …` with deploy **on** (default). Writes `~/.raft/state/apps/<name>.yaml`, then `ensure_app_deployed`: cutover if the Compose service is already running, start that service if the gate is up, else full stack `up`. Pass `--ref SHA` (and optional `--env-file` / `--env`) so CI first-boot and later cutovers share one command. Do **not** default to `--no-deploy` + `sync` + `redeploy` — `redeploy` requires the app service to already be running and fails on a new App with `service '…' is not running — bring the stack up first`.
4. **TLS before trusting HTTPS:**
   - `tls: acme` (direct browser → VPS): DNS A/AAAA for `publicHost` + each `extraHosts` name; TCP 80 + 443 open; set `acme.email` in settings; then apply. **Do not paste PEMs** — live material is written under `certs/<name>/acme.*` by apply/controller. Staging directory for labs; production is the settings default. DNS-01 / wildcards are **not** shipped.
   - `tls: origin` (Cloudflare Origin / upstream proxy): install `~/.raft/certs/<name>/origin.{pem,key}` **before** first deploy.
5. `--no-deploy` only when you intentionally register desired state without bringing the app live (e.g. apply several manifests, then one `raft up`; or register before Origin PEMs exist). After that, deploy with `raft apply …` again (deploy on) or `raft up` / `raft redeploy` as appropriate.
6. Manual cold start when apps are already applied: `raft up` (refuses if stack already up; `down` first).
7. `raft doctor` before trusting the site (certs for `tls: origin` / `tls: acme`; gate drift → `raft gate recreate`). Doctor is group-first: built-in **`raft`** (edge services; healthy docker/compose/generated/stack/port probes stay hidden), then App `spec.group` (at most one); ungrouped apps appear without a heading. Member labels drop the `{group}-` prefix under a group heading (Compose ids stay `raft-gate` / `raft-router` / `GROUP-NAME` for Docker; doctor shows `gate` / `router` under `raft`). Healthy OK lines append ports in use (gate: published host ports; apps/router: contract / listen ports). File log records per-suite start/done with `elapsed_ms` plus a compose-call summary (`total` / `ps`) for diagnosing slow doctor runs.
8. `raft status` (optional `--json`, or `--live` to refresh the human table until Ctrl+C) for a point-in-time host + container CPU/memory/uptime/started snapshot — declared Compose limits vs live usage via `ContainerRuntimeGateway`. Human NAME column drops `{group}-` (edge: `gate` / `router` with GROUP `raft`); JSON keeps Compose service ids. The always-on **controller** also samples the same plane on a metrics job interval (default 60s; settings `metrics:`) and **batch-appends** JSONL under `~/.raft/state/metrics/resources.jsonl` (flush every 10 samples or 60s; seals on day change / `retentionMaxBytes` like `raft.log`; defaults 30 days / 100 MiB). `raft serve` Trends + service Runtime charts read that history via `/api/metrics`.
9. `raft serve` (optional `--port`, default **8787**) — localhost-only ops UI (`127.0.0.1`) for applied apps + gate/router/controller. One FastAPI process: packaged SPA + status/metrics/service/actions/logs APIs. Prints bind URL + a generic SSH port-forward example on start; Ctrl+C or `raft serve --stop` stops. A second start on the same port fails fast with an already-running CTA. **Not** an edge listener. See **Serve / ops UI** below.
10. `raft logs [name…]` for container stdout/stderr (not `~/.raft/logs/raft.log`). Snapshot by default (`--tail N`, default 100); `-f` / `--follow` streams until Ctrl+C. Names: applied app, `gate` / `router` / `controller`, or Compose ids (`raft-gate`, `GROUP-NAME`); omit names for all core services. Unknown / missing containers → OperatorError with Fix CTA. Serve detail reuses the same `Logs` path (snapshot + SSE follow).
11. Updates: prefer `raft apply … --ref …` again (handles first-boot and cutover). Use `raft redeploy <app>` only when the app Compose service is **already running** and you want cutover without re-writing the registry (optional `--ref` / `--force-sync`). `raft redeploy router` for the inner nginx. New edge listeners: `raft gate recreate`.
12. Tear down: `raft down`.

Useful checks: `curl -H 'Host: <publicHost>' http://127.0.0.1/`. Optional local hosts: `sudo python3 scripts/hosts.py hold` (reads applied `publicHost` values; errors if none applied). See [`scripts/README.md`](scripts/README.md).

Logging: `~/.raft/settings.yaml` `logging:`; default active file `~/.raft/logs/raft.log`; override dir with `RAFT_LOG_DIR`. Terminal stays plain; file is structured and includes a per-invocation `tid` (UUID) via `TraceContext` so one `raft …` run correlates in the log file (`-` when no scope). Rotation (not a full-file rewrite): at local day boundary the active file is sealed as `raft.log.YYYY-MM-DD`; if a single day's active segment reaches `retentionMaxBytes` (default 100 MiB), further same-day parts are `raft.log.YYYY-MM-DD.2`, `.3`, …. `retentionMaxAgeDays` (default 30) deletes sealed archives older than that many calendar days (by the date suffix). Cheap prepare + rollover run when the host CLI configures logging (not the controller — it logs to stdout only).

---

## App manifest model

Canonical path in a service repo: **`.raft/app.yaml`** only. Shape: `apiVersion: raft/v1`, `kind: App`, `metadata`, `spec`.

Unknown `spec` / `metadata` keys fail parse (`OperatorError` with Fix CTA). Host aliases use `extraHosts` (not a separate www flag).

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
  # extraHosts:                   # optional Host aliases (routed + ACME SANs)
  #   - www.app.example.com       # www is not automatic — list it when you need it
  #   - api.app.example.com
  tls: off                      # off | origin | acme
  # acme → gate HTTP-01 + live certs/<name>/acme.*; needs DNS, :80/:443, acme.email
  # origin → paste Origin PEMs at certs/<name>/origin.*; acme never uses origin.*
  group: demo               # optional; at most one group
  # dependsOn: optional. Strings or { name, scaleWithParent? }.
  # Compose / wake / heal use names only. When this app has spec.scaling,
  # idle-stop also stops transitive deps with scaleWithParent true (default).
  dependsOn:
    - other-app                   # ≡ { name: other-app, scaleWithParent: true }
    - name: some-sidecar
      scaleWithParent: false      # stay up when parent idle-stops
  envFile: /home/raft/.raft/demo.env
  env: { KEY: value }           # overrides envFile on clash
  volumes:
    - hostPath: /mnt/data/x
      containerPath: /data
      readOnly: false
  # ports: omit or [] for worker Apps (no listeners; readiness defaults to none)
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
  # Optional scale-to-zero (omit = no scaling). When present, idleSeconds and
  # minUpSeconds are required; wakeTimeoutSeconds defaults to 60 if omitted.
  # scaling:
  #   idleSeconds: 300          # stop after this much idle (HTTP activity via gate)
  #   wakeTimeoutSeconds: 60    # holding page → timeout page if wake exceeds this (default 60)
  #   minUpSeconds: 60          # do not idle-stop until this long after wake/start
  # Requires at least one expose: http + publicHost (not stream/host/none alone).
  # Idle stop + gate holding/wake ship together. Holding hits do not count as
  # activity. After wakeTimeoutSeconds the product timeout page includes an
  # admin CTA and a diagnostic id (grep controller logs for `id=`). Healing is
  # separate (settings healing:); see examples/settings.yaml.
```

### Apply-time preprocess (`ManifestPreprocessor`)

`raft apply` runs on the raw manifest text **before** YAML parse:

1. Resolve `${{ if expr }}` … `${{ endif }}` (full-line `#` comments skipped).
2. Expand remaining `${NAME}` / `${NAME:-default}` in non-comment text.
3. `yaml.safe_load` → `AppDocument` → registry (concrete; no placeholders/directives left).

In `expr`, operands are only quoted strings (`'…'` / `"…"`) or env refs (`${NAME}` / `${NAME:-default}` — same rules as body placeholders). No barewords. After resolve, comparisons are **string** equality (`==` / `!=`); combine with `&&` / `||` (`&&` binds tighter); parentheses group. Nested `${{ if }}` is supported. Env values may be any string (spaces, punctuation, etc.). Unmatched `if`/`endif`, leftover `${{`, undefined variables, or bad expressions → `OperatorError` with a Fix CTA. Render / redeploy / doctor never re-run the pipeline.

Optional keys (omit the whole mapping when the predicate is false):

```yaml
${{ if ${INCLUDE_SCALING} == 'true' }}
scaling:
  idleSeconds: ${SCALE_IDLE_SECONDS}
  wakeTimeoutSeconds: ${SCALE_WAKE_TIMEOUT_SECONDS}
  minUpSeconds: ${SCALE_MIN_UP_SECONDS}
${{ endif }}
```

`apply --git` clones briefly, reads `.raft/app.yaml`, copies into `~/.raft/state/apps/`. `sync` refreshes sources then `render` regenerates `~/.raft/generated/`.

### `spec.scaling` (scale-to-zero)

Omit `spec.scaling` → no scaling. When present, **`idleSeconds` and `minUpSeconds` are required**. **`wakeTimeoutSeconds` is optional** (omit → **60**; set on the App → that value). Same scaler, `.timeout` marker, and product `holding-timeout.html` swap.

| Field | Role |
|-------|------|
| `idleSeconds` | Stop the Compose service after this much idle (activity recorded via gate on real proxied traffic) |
| `wakeTimeoutSeconds` | Holding page → timeout page if wake exceeds this (default **60**) |
| `minUpSeconds` | Do not idle-stop until this long after wake/start |

Eligible only with ≥1 `expose: http` port and `publicHost`. Not for stream/host/none-only apps. Controller idle-stops and wakes; gate serves a holding page (meta-refresh) and calls an internal wake API; holding-page reloads do not reset the idle timer. On wake, the controller starts the app’s full transitive `spec.dependsOn` chain (names only — ignore `scaleWithParent`), waits until each service is Compose `running` within `wakeTimeoutSeconds`, then marks the scaled app awake. On idle-stop, the controller also stops the **co-stop set**: transitive deps of the parent reached only via edges whose effective `scaleWithParent` is true (default; string form ≡ true). Stop order is deps-before-parent; co-stopped deps are marked intentional `scaledToZero` for healer skip even without their own `spec.scaling` (cleared when wake starts them). Opt out per dep with `scaleWithParent: false`. Activity is still recorded only on the edge app’s Host. State under `~/.raft/state/scaling/`. Independent of `healing:` in settings — healer skips apps marked `scaledToZero`. Before restart/escalate, healer starts transitive `spec.dependsOn` (same graph as Compose); defers if a dep is intentionally scaled to zero.

Wake requests mint an opaque diagnostic id (scaling JSON + `{app}.id` marker). Successful wakes within budget never show it. After the wake budget, the product timeout page shows “contact the administrator” plus that id (SSI). The same id is on controller log lines (`scale wake request` / `scale wake` / `scale wake timeout` … `id=`). Incomplete/timeout lines also include the last wake **stage** (`wait_running` / `wait_fetch` / `wait_host`, plus `service=` / `detail=` when known) so an operator can see where the chain stopped. Grep controller logs for `id=<code-from-page>`. The holding page stays “Just a moment” + auto-refresh (no admin CTA).

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

## Serve / ops UI

Localhost dashboard for operators (`raft serve`). **Hard rules:** bind `127.0.0.1` only; one process (FastAPI + static SPA); no WebSocket — status/metrics use HTTP poll; FE changes must rebuild into `src/raft/share/serve/spa/` before commit/release; mutative actions take the same `flock` locks as CLI deploy; gate start/stop/redeploy still refused where CLI refuses.

### Backend map

| Piece | Path / type | Role |
|-------|-------------|------|
| CLI entry | `raft serve` → `services/serve/service.py` | uvicorn on `--port` (default **8787**); prints tunnel CTAs; flock lease under `state/serve/`; `--stop` |
| App factory | `ServeAppFactory` | mounts `/assets`, SPA catch-all, registers `/api/*` |
| Page / routes | `ServePage` | status, metrics, service detail, logs, start/stop/redeploy |
| Downloads | `ServeDownloads` + `services/export/` | catalog-driven log/metrics file export (register an `Exporter`) |
| Actions | `ServeActions` | Compose start/stop; redeploy via `Orchestrator`; scaling mark/clear on stop/start |
| Logs bridge | `LogSseStream` + `ops/logs.Logs` | snapshot JSON + SSE follow (same follow path as CLI `-f`) |
| Read contracts | `services/read/` | `StatusRead`, `MetricsRead`, `ServeSnapshotView`, `ExternalUrlBuilder` |
| Runtime gather | `ContainerRuntimeGateway` (`adapters/docker/runtime.py`) | batched Engine `ps`/`inspect`/`stats` for status + controller metrics (not `compose ps`) |
| Packaged SPA | `src/raft/share/serve/spa/` | Vite build output shipped with the Python package |

### HTTP API

| Method | Path | Backing |
|--------|------|---------|
| `GET` | `/api/status` | `StatusRead` snapshot + `control_plane` / `apps` presentation (labels, started, external_urls) |
| `GET` | `/api/metrics` | `MetricsRead` over `state/metrics/resources.jsonl` (`window`, optional `since`, optional `services`) |
| `GET` | `/api/service/{name}` | one container + presentation row (404 if unknown) |
| `GET` | `/api/service/{name}/logs` | log snapshot (`tail`) |
| `GET` | `/api/service/{name}/logs/follow` | SSE live follow |
| `GET` | `/api/exports` | download format catalog (`logs` / `metrics` exporter ids) |
| `GET` | `/api/service/{name}/logs/download` | log snapshot file (`format`, `tail`) via export registry |
| `GET` | `/api/metrics/download` | metrics table file (`format`, `window`, optional `services`) |
| `POST` | `/api/service/{name}/start\|stop\|redeploy` | `ServeActions` |

Doctor JSON for the SPA is deferred (`DoctorRead.intended_payload_shape`).

### SPA source (`src/spa/`)

Feature folders under `src/spa/src/` (`main.tsx` + lean `styles.css` for tokens/resets/shared primitives; each UI component co-locates `ComponentName.css`; shell under `shell/`):

| Area | Path | Notes |
|------|------|-------|
| Shell / routes | `shell/App.tsx`, `shell/Dashboard.tsx`, `main.tsx` | client routes; FastAPI serves `index.html` for non-`/api` paths |
| Shared | `shared/api.ts`, `shared/dashboardCache.ts`, `shared/ExternalUrlLinks.tsx` | typed `/api` client + status/metrics cache |
| Status tables | `status/` (`StatusTable`, column menus/filters, tones, `ServiceQuickActions`) | compact-only; Started column; row quick actions |
| Live chrome | `chrome/LiveIndicator.tsx` (+ `Modal` / `ConfirmPopup` / toasts) | auto-refresh while tab visible; **no** native `alert`/`confirm` |
| Service detail | `service/` (`ServicePage`, detail, actions) | lifecycle buttons; Runtime charts live under `trends/runtime/` |
| Logs | `logs/` (`ServiceLogs`, `LogLines`, `logParse`) | follow / expand / severity filter; catalog download |
| Trends | `trends/panel/`, `trends/chart/`, `trends/runtime/` (+ root `runtimeMetrics`, range controls) | historical series; sidebar filters; poll `/api/metrics`; catalog download; per-service Runtime charts |
| Export | `export/` (`DownloadMenu`, catalog/urls) | generic download links from `/api/exports` |

Develop: `cd src/spa && npm ci && npm run dev` (Vite `:5173`, proxies `/api` → `raft serve :8787`). Release FE: `npm run build` → updates `share/serve/spa/`. See [`src/spa/README.md`](src/spa/README.md).

### Metrics pipeline (CLI + serve + controller)

```text
ContainerRuntimeGateway / Status.collect
  → raft status (point-in-time)
  → raft serve /api/status (live tables)
  → controller metrics job → batch-append resources.jsonl
       → MetricsRead → /api/metrics → Trends + service Runtime charts
```

Retention: settings `metrics.retentionMaxAgeDays` / `retentionMaxBytes` (seal active segment like `raft.log`; age-delete sealed archives — no full-file rewrite). Host CPU in charts: load average ÷ CPU count; containers: sampled `cpu_percent` / memory percent.

---

## CLI surface (Fire)

Top-level **commands** (not nested groups, except `auth` and `gate`):

| Command | Purpose |
|---------|---------|
| `apply` | `--file` or `--git` (+ `--ref`, `--no-deploy`, `--force-sync`, `--env-file`, repeatable `--env`) — default **deploys** via `ensure_app_deployed`; `--no-deploy` registers only; `--env*` feed `ManifestPreprocessor` (`${VAR}` + `${{ if }}`; full-line `#` comments skipped) |
| `get` | `get apps` / `get app NAME` |
| `delete` | `delete app NAME` |
| `up` / `down` | Stack bring-up / tear-down (when apps already applied; not the usual CI path) |
| `sync` / `render` | Sources / regenerate `~/.raft/generated/` |
| `redeploy` | Cutover for an **already-running** app, or recreate `router` (`gate` refused). Fails if the app service is not up — use apply-with-deploy (or `raft up`) for first boot |
| `gate recreate` | Recreate gate for new published edge ports |
| `doctor` | Health + fix hints; optional `raft doctor [name]` filters to one App |
| `status` | Host + container resource usage (point-in-time; `--json` or `--live`; Started column beside Uptime) |
| `serve` | Localhost ops UI (`127.0.0.1`, default **8787**; optional `--port` / `--stop`); SPA + status/metrics/service/actions/logs APIs; SSH tunnel; Ctrl+C or `--stop` |
| `logs` | Container stdout/stderr (`--tail N` snapshot; `-f` / `--follow` until Ctrl+C). Names: app, `gate`/`router`/`controller`, or Compose ids; omit = all |
| `update` | Re-install CLI from GitHub (`install.sh`) |
| `uninstall` | Full removal (`--yes`; optional `--uv` to remove uv too) |
| `auth` | `setup` / `list` / `show` / `test` / `remove` |

Entry: `raft` console script → `raft.cli:run`. Prefer `install.sh` / `uv tool install` so `raft` is on `PATH`; in a bare checkout `uv run raft …` still works.

---

## Package map

| Path | Notes |
|------|-------|
| `src/raft/cli/` | Fire root + auth + gate; `deps.py` patched in tests |
| `src/raft/config/` | `~/.raft` paths, `settings.yaml` (logging + edge + healing + metrics), logging setup |
| `src/raft/models/` | Types + parse/registry: `App`, `AppSpec`, `AppDocument` / fields, `AppRegistry`, `AppDependsGraph`, `PortSpec`, `Stack`, `ScalingSpec`. Import from owning modules — package `__init__` is not a re-export barrel. |
| `src/raft/models/state/` | Runtime JSON stores (`ScalingStore`, `GraphEventStore` + kinds/records) under `~/.raft/state/` |
| `src/raft/adapters/` | `shell`; `docker/` (`DockerStack`, `ContainerRuntimeGateway`, edge/images/inspect); nginx upstreams; HTTP probe; host |
| `src/raft/services/apply/` | `AppApply`, `manifest_preprocess` (`ManifestPreprocessor`), `manifest_env` (apply env + `${VAR}`), `manifest_expr` (directive predicates), `manifest_comments` (full-line `#` skip) |
| `src/raft/services/acme/` | `AcmePaths`, `AcmeEnsure` (HTTP-01 via official PyPI `acme`), `AcmeGateInstall` (render + nginx reload), `AcmeHttpRedirect` |
| `src/raft/services/auth/` | `GitAuthManager` + ssh/urls helpers |
| `src/raft/services/sync/` | `SourceSync` |
| `src/raft/services/render/` | `StackRenderer`, `FragmentCollector`, `compose_apps`, `gate_nginx`, `edge/` nginx fragments (http/stream/tls), `scaling_gate` (holding/wake snippets). Distinct from `adapters/docker/edge.py` (Compose edge service ops). |
| `src/raft/services/deploy/` | orchestrator, cutover, wait, locking, readiness |
| `src/raft/services/ops/` | doctor, **status collect/format** (Started + allocated limits), logs, uninstall, update, certs |
| `src/raft/services/read/` | Shared **CLI+serve contracts/presentation** over ops collectors (`StatusRead`, `MetricsRead`, `DoctorRead`, `ServeSnapshotView`, `ExternalUrlBuilder`) — not a second status collector |
| `src/raft/services/export/` | Open-closed download encoders (`ExportRegistry` + `Exporter` subclasses); serve catalogs/attachments |
| `src/raft/ui/` | Operator terminal output (`say`) + shared TTY `TerminalProgress` spinner (doctor, update; `current()` / `set_text` for inner frames; entered at CLI entry before stack/logging init) |
| `src/raft/services/serve/` | `raft serve`: FastAPI factory, `ServePage`, `ServeActions`, SSE log bridge, SPA paths/instructions |
| `src/raft/controller/` | Always-on Compose `raft-controller` (job orchestrator for heal + metrics + per-app `acme:<name>` when `tls: acme`; idle-stop + wake via side_ticks when `spec.scaling`; healer skips `scaledToZero`; metrics batch → `resources.jsonl`) |
| `src/raft/errors/` | Operator errors + CTAs (`cta`, `domain`, `docker_msgs`, …). Import from owning modules — package `__init__` is not a re-export barrel. |
| `src/raft/share/` | Product Compose + nginx templates (synced into data home); `share/serve/spa/` = packaged dashboard assets |
| `src/spa/` | Dashboard SPA source (React + Vite + TypeScript); build output → `share/serve/spa/`; see **Serve / ops UI** |
| `tests/` | `unit/` mirrors `src/raft/` packages (100% cov), plus `integration/`, `meta/`, `e2e/`, shared helpers under `tests/shared/`. Minimal Compose fixtures under `tests/fixtures/` are **not** the operator samples in `examples/`. |

Compose mounts `generated/nginx/upstreams` into the router. Upstream files are keyed by app + port name (`<app>-<port>.conf`).

---

## Multi-repo responsibilities

| Repo | Role |
|------|------|
| **raft** (this) | Product + **Test** CI (Py 3.9–3.13). No Terraform here. |
| **Private ops** | Host/VM + SSH job that pulls this repo onto the VPS |
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
