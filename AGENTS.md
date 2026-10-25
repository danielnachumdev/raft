# AGENTS.md

Implementation guide for coding agents changing **raft**. Operator pitch and feature status table: [`README.md`](README.md). App manifest / preprocess contract lives in code under `core/models/` (do not invent parallel schema docs).

---

## Orientation (read this first)

| Question | Answer |
|----------|--------|
| What ships to operators? | CLI + Compose/nginx templates + tests. Install via [`install.sh`](install.sh) / `uv tool install` from the **latest GitHub Release wheel** by default (git@tag fallback; `--ref` / `RAFT_REF` / local checkout / `RAFT_KEEP_CHECKOUT`) — **no lasting clone**. |
| Where is durable state? | **`~/.raft/`** (`RAFT_DATA_HOME`). Never put operator inventory, upstreams, or PEMs in this git repo. |
| Where is product code? | `src/raft/services/` = runnable fronts (cli, serve, controller). `src/raft/core/` = libraries (models, lifecycle, platform, observe). |
| Where is the SPA? | Source `src/spa/` only in git. Bake is **Release CD** (and local/CI `npm run build`) into `share/serve/spa/` — hashed assets are **not** committed (`.gitkeep` + gitignore). Operators get UI from the wheel. |
| Human samples? | [`examples/`](examples/). |
| Agent capabilities (capa)? | [`capabilities.yaml`](capabilities.yaml) — install via [`scripts/setup/setup.sh`](scripts/setup/setup.sh) (prereqs: [`scripts/setup/prerequisites.sh`](scripts/setup/prerequisites.sh); [capa.sh](https://capa.sh/)). Do not hand-edit generated `.cursor/` / `.claude/`. |
| Package layout convention? | Class-first, ~200-line files, ≤20-line methods; see **Code style** and the writing-python skill. |

**CI order:** Meta → then Unit+Integration and E2E **in parallel** (SPA job parallel with Meta when spa paths change). Path filters skip Python vs SPA sides when irrelevant; concurrency cancels superseded PR/main runs; every `runs-on` job has `timeout-minutes`. Fresh-install e2e installs from the **workspace** build context after SPA bake (`RAFT_E2E_REF=workspace`); operators stay on Release wheels.

**Pre-merge vs post-merge (same steps, different triggers):** PRs run Meta + SPA (path-filtered) + the **full** Unit+Integration matrix **Py 3.9–3.13** + E2E **Py 3.9** (thorough merge gate). Push to `main` / `workflow_dispatch` runs Unit+Integration on **Py 3.9 + 3.13** bookends only (plus the same Meta / SPA / E2E) so post-merge and CD stay short. CD **semver** still waits for successful CI on `main` (bookend smoke after the PR already proved the full matrix). No steps removed — middle Python versions are PR-only.

---

## Hard architecture (do not “simplify” away)

```text
gate → router → apps
```

| Layer | Compose id (typical) | Role | Mutative ops |
|-------|----------------------|------|----------------|
| **gate** | `raft-gate` | Public listeners from settings; TLS; ACME HTTP-01; offline; scale holding/wake; **ordered edge firewall**; HTTP access log + stub_status | **reload** when generated gate nginx changes; **`raft redeploy gate`** only for published ports (brief edge downtime) |
| **router** | `raft-router` | Host → upstream | `raft redeploy router` / reload on cutover |
| **apps** | `GROUP-NAME` / name | One Compose service per applied App | `apply` / `redeploy <name>` |

- **Stream** / **host** / **workers** do not use Host→router the same way (stream: gate→app; host: app publishes; workers: no ports). Do not invent dummy ports for workers.
- **No middle `raft-firewall` hop.** Edge firewall is **policy-on-gate** (design lock #208 / epic #207). A dedicated hop was explicitly rejected.
- Cutover reloads **router**. Render reloads **gate** when `host/gate-nginx.fingerprint` ≠ on-disk generated gate fragments and gate is running; reloads **router** when `host/router-nginx.fingerprint` ≠ on-disk `router/hosts.conf` + `upstreams/*` and router is running.
- Firewall / TLS fragment changes: **render + nginx reload**, never gate container restart for policy-only edits.

### Locks (correctness, not optional)

Overlapping apply/redeploy/render tears tmp names, upstreams, and `generated/`. Serialize under `~/.raft/host/locks/`:

| Lock | Held by | Guarantees |
|------|---------|------------|
| `app-<name>.lock` | apply, redeploy / `ensure_app_deployed`, delete app | One mutative pipeline per app; later waiter wins after wait |
| `stack.lock` | render, sync, cutover, compose up/recreate, redeploy gate, up/down, purge | No torn `generated/` / mid-cutover upstream reset |
| `acl.lock` | serve firewall writes (before render/reload) | Firewall persist does not race another firewall writer |
| `alerts.lock` | CLI/serve writes to `host/alerts/rules.yaml` | Alert rules document writers do not tear each other |
| `settings.lock` | full settings document, notification channels, github OAuth settings writers | No torn `host/settings.yaml` |
| `dashboard.lock` | Dashboard settings helpers writing `host/settings.yaml` `dashboard:` | Dashboard settings writers do not tear each other |
| `fifo-<kind>/` (ticket FCFS) | `FifoLock` — `update` (`SelfUpdate`); short claim for host-job flights | True arrival-order grant (not plain flock); mint tickets under `seq.lock` |
| `host-job-<kind>.flight.json` | `HostOneshotFlight` (dashboard self-redeploy oneshot) | Coalesce concurrent detached starts to one in-flight `job_id` |

Wait up to `RAFT_LOCK_TIMEOUT_SECONDS` (default **300**). Nesting in-process re-enters. `doctor` / `status` do not take these locks.

**Host oneshot / self-redeploy deadlock rule:** claim flight under a short `FifoLock`, record/`docker run -d`, **release before** the child takes `stack.lock`. Never hold `fifo-host-job-*` across a rebuild. Concurrent in-dashboard Redeploy returns the same `job_id` (`coalesced`) while the oneshot container is alive — SPA busy-state is UX only. GitHub assist deploys coalesce per `full_name` in-process (one pending/running job).

---

## Invariants you cannot infer from a quick skim

1. **Ship path:** default `raft apply` **deploys**. Do not teach `--no-deploy` + `redeploy` as the happy path — `redeploy` fails if the service is not already running.
2. **Gate redeploy ≠ reload:** published `edge:` ports → `raft redeploy gate` (brief downtime). Everything else gate-related that only changes generated nginx → **reload**.
3. **Packaged templates path:** product share lives at `src/raft/core/platform/share/`. `[tool.setuptools.package-data]` **must** list `core/platform/share/**` (not legacy `raft/share/`). Wrong globs → wheels without `compose.yaml` → every CLI command dies (including `raft update`). Meta guard: `tests/meta/test_package_data.py`. Recovery on a broken host: `curl …/install.sh | bash` (update cannot self-heal if stack load fails).
4. **Console entry:** `raft` → `raft.services.cli.__main__:main`. Also `python -m raft.services.serve` / controller `__main__` where present.
5. **Registry load is lenient; apply write is strict:** invalid `services/<name>/app.yaml` skipped at load (`registry_issues`); apply still rejects bad manifests.
6. **Name vs source:** `metadata.name` owned by durable source identity (`local`+path, `git`+normalized remote SSH≡HTTPS, `docker`+image; not `ref`). Same → update; different → `OperatorError` (no `--force` — delete then re-apply).
7. **ACME failures do not fail deploy:** best-effort HTTP-01; errors under `host/acme/` / `services/<name>/acme/`.
8. **Healing ≠ scaling:** `healing:` in settings; `spec.scaling` is per-App. Healer skips intentional `scaledToZero`.
9. **Serve binds localhost only** (`127.0.0.1`). Not an edge listener. Mutative serve actions use the same flock rules as CLI; gate redeploy matches CLI (edge-downtime warning).
10. **SPA poll:** status ~2s while tab visible; `/api/status` reloads registry every call (`refresh_apps=True`).
11. **No PII / no live inventory in fixtures, screenshots, or PR bodies** — use `demo-api`, `192.0.2.0/24`, etc.
12. **UI PRs need screenshots** (agent-browser + `gh pr edit --attach`) — unit tests alone are not Proof for visible SPA changes.
13. **Desired apps are not in git** — only examples under `examples/`.

---

## Feature status (implementation)

Align with the README table; detail for agents:

| Area | Status | Notes for implementers |
|------|--------|------------------------|
| Manifest apply + deploy / cutover | **Shipped** | `seamless` default; `inplace` optional |
| Manifest preprocess `${VAR}` / `${{ if }}` | **Shipped** | Apply-time only; not re-run on render |
| TLS `off` / `origin` / `acme` | **Shipped** | ACME = HTTP-01 only; no DNS-01/wildcards |
| Scale-to-zero | **Shipped** | HTTP + `publicHost`; holding on gate; wake diagnostic id |
| Multi-app `group` / `dependsOn` / volumes / `envFile` / `expose: none` | **Shipped** | |
| Worker Apps (`ports: []`) | **Shipped** | `readiness: none`; no scaling/TLS origin\|acme |
| Doctor / status / logs / purge | **Shipped** | |
| Metrics JSONL + Trends (resources + HTTP aggregate) | **Shipped** | Controller scrape; `http.jsonl` via `core/observe/read/metrics/` (`HttpMetricsRead`); CLI `raft metrics history|catalog|export_*` |
| `raft serve` ops UI | **Shipped** | FastAPI + packaged SPA |
| Full operator settings UI (`settings.yaml` / `RaftConfig`) | **Shipped** | `OperatorSettingsService` + `GET/PUT /api/settings` + SPA `/settings`. Edge port changes note `raft redeploy gate`. |
| Settings → Check for updates | **Shipped** | `UpdateCheck` + `SelfUpdate` via `GET/POST /api/update`; same GitHub Release wheel SoT as `raft update` / `install.sh` |
| HTTP request inspection (per App) | **Shipped** | Gate access log → `/api/service/{name}/http-requests` + `raft http_requests show`. |
| Flat gate / App IP ACL (allow/deny lists) | **Retired** | Removed; firewall SoT only. Leftover `acl.gate` / `state/acl/` ignored. |
| **Ordered firewall rules** (CIDR, port, protocol, service, action) | **Shipped** | Epic [#207](https://github.com/danielnachumdev/raft/issues/207), [#211](https://github.com/danielnachumdev/raft/issues/211); CLI [#258](https://github.com/danielnachumdev/raft/issues/258) (`raft firewall …`). On gate; Save/CLI → compile → reload; import/export; recommendations. |
| Inspection → add firewall rule | **Shipped** | [#198](https://github.com/danielnachumdev/raft/issues/198); row actions → `#211` model; prepend + reload |
| GitHub add-service assist | **Shipped (v1)** | Serve + `raft github …` via `GithubAssistService`; known gap [#200](https://github.com/danielnachumdev/raft/issues/200) |
| Notifications channels | **Shipped** | Strategy catalog + channel CRUD + test-send (serve + `raft notifications …`). |
| Healing | **Shipped** | Settings `healing:`; separate from scaling |
| Secrets baseline (`~/.raft/services/<app>/secrets/env`) | **Shipped** | External materialization epic [#143](https://github.com/danielnachumdev/raft/issues/143) / [#176](https://github.com/danielnachumdev/raft/issues/176) |
| Past logs when container off | **Shipped** | Retained under `services/<name>/logs/` (edge: `host/logs/services/`); shipper + drain-before-rm. |
| Trends dashboards (multi-graph) | **Shipped** | [#238](https://github.com/danielnachumdev/raft/issues/238) supersedes #202 named views (migrate removed). Shared range + one fetch per plane fanned out to `TrendsGraph`s; browser-local (`raft-serve-trends-dashboards`); overview embeds the dashboard kit; `src/spa/src/trends/dashboard/`. |
| Per-service Trends (default graphs) | **Shipped** | Service inspection uses the same multi-graph UX, pinned to that service; browser-local `raft-serve-service-trends`; `src/spa/src/trends/service/` (kit migration follow-on for [#249](https://github.com/danielnachumdev/raft/issues/249)) |
| Reusable dashboard kit (Trends shell / embed) | **Shipped (v1)** | [#249](https://github.com/danielnachumdev/raft/issues/249); `src/spa/src/dashboard-kit/`; timeseries panels + embed contract; browser-local persistence. |
| Alert rules engine (metrics/control-plane → notifications) | **Shipped** | [#236](https://github.com/danielnachumdev/raft/issues/236); dual-plane CLI+serve lock [#264](https://github.com/danielnachumdev/raft/issues/264); `AlertRulesService` / engine under `observe/alerts/` |
| Alert setup recommendations (OOM / not-running / high memory) | **Shipped** | Shared SPA `recommendations/` kit (firewall + alerts callbacks); catalog in `observe/alerts/recommendations/`; dismissals `host/alerts/dismissed-recommendations.json`; channels optional on apply |
| Operator system event timeline | **Shipped** | [#267](https://github.com/danielnachumdev/raft/issues/267); `host/events/ops.jsonl` dual-write with GraphEvents; `raft events` + serve `/events`. |
| Firewall-derived alert signals (`edge.denies`) | **Planned** | Observe gate outcomes only; no middle hop (#207) |
| Always-on Compose dashboard service | **Shipped** | [#36](https://github.com/danielnachumdev/raft/issues/36); `dashboard:` settings-only + `raft-dashboard` Compose; lifecycle via Up/Down/Redeploy ([#340](https://github.com/danielnachumdev/raft/issues/340)); optional `publicHost` + TLS + auth (`none`/`password`/`oauth`/`external`); OAuth via in-container oauth2-proxy + allowlist. |
| Automate SPA bake in CD | **Shipped** | [#41](https://github.com/danielnachumdev/raft/issues/41) — Release wheel + install.sh prefers `.whl`; SPA assets not committed |
| Middle nginx firewall hop | **Rejected** | Do not re-open without new engine requirements |

### Firewall

- **Ordered firewall (#211, shipped):** ordered rule table — **CIDR**, **port** (number or `any`), **protocol** (dropdown + other), **service** (dropdown + any), **action** (`deny` \| `permit` \| `drop`); Save → persist → compile → **gate nginx reload**; import/export; baseline recommendations (per-port permit + default deny). Flat ACL migrate path removed (#312).
- Flat ACL UI/API removed — not an operator path.
- **Never** require gate redeploy/restart for rule-only changes.

---

## Data home (roles)

Layout (#313): `host/` (control-plane) + `services/<SERVICE>/` (App-owned) + `generated/` + root `compose.yaml`.

| Path | Role |
|------|------|
| `raft.sqlite` | SQLite durable-state foundation (#317); Alembic schema; `raft db migrate` imports settings/apps/firewall (files remain live SoT until cutover #320) |
| `host/settings.yaml` | logging, edge, healing, metrics, serviceLogs, acme, github, notifications, dashboard, alerts cadence |
| `services/<name>/app.yaml` | Applied App registry |
| `generated/` | Compose + nginx (+ `gate-http/firewall/` includes) — **do not hand-edit as source of truth** |
| `host/locks/` | flock files |
| `host/firewall/rules.yaml` | Ordered firewall document (#211); always drives render |
| `host/firewall/dismissed-recommendations.json` | Dismissed baseline firewall suggestions |
| `host/metrics/`, `host/acme/`, `host/serve/`, `host/events/` | Shared control-plane state |
| `host/events/graph.jsonl` | Trends GraphEvents (chart markers) |
| `host/events/ops.jsonl` | Operator system event timeline (#267) |
| `host/alerts/rules.yaml`, `host/alerts/runtime.json` | Alert rules (desired) + evaluation runtime |
| `host/alerts/dismissed-recommendations.json` | Dismissed default alert-setup suggestions |
| `host/secrets/dashboard/` | Dashboard OAuth material |
| `host/logs/` | Host raft log + retained edge service stdout |
| `services/<name>/secrets/`, `certs/`, `checkout/`, `deploy/`, `scaling/`, `logs/`, `acme/` | Per-App durable artifacts |

Product templates sync from `src/raft/core/platform/share/` into the data home on bootstrap/use.

---

## Where to change what

| Change | Start here |
|--------|------------|
| CLI commands | `src/raft/services/cli/` |
| Serve API / actions | `src/raft/services/serve/` (thin FastAPI adapters only) |
| Controller jobs / wake | `src/raft/services/controller/` |
| Manifest parse / registry | `src/raft/core/core/models/` |
| Apply / sync / render / deploy / ACME | `src/raft/core/lifecycle/` |
| Docker / nginx adapters, share templates | `src/raft/core/platform/` |
| Doctor, status, logs, update | `src/raft/core/observe/` |
| **Shared mutative capabilities** (CLI + serve) | Business rules in `core/`; serve/CLI only invoke. New capabilities: put the service under the matching core area below, keep FastAPI/Fire as adapters. |
| Per-service up/down/redeploy/purge | `observe/ops/actions/` (`ServiceActions`); CLI `raft up|down [NAME]` + serve actions (`/up` `/down` `/redeploy`; deprecated `/start` `/stop` aliases); default `up NAME` brings up `dependsOn` (wake order), `--no-deps` skips; `redeploy gate` = edge container force-recreate; `redeploy controller` / `dashboard` = stamp rebuild ([#341](https://github.com/danielnachumdev/raft/issues/341) / [#340](https://github.com/danielnachumdev/raft/issues/340)); Restart stays `--no-build` |
| Ordered firewall (CRUD / recommendations / from-inspection) | `lifecycle/firewall/` + nginx compile in `lifecycle/render/firewall/`; serve adapter `services/serve/firewall/`; CLI `services/cli/commands/firewall.py` (`raft firewall …`); SPA `src/spa/src/firewall/` |
| Full operator settings (`settings.yaml`) | `core/config/settings/operator_service.py` (`OperatorSettingsService`); serve adapter `services/serve/settings/`; SPA `src/spa/src/settings/`. |
| Check for updates (Settings) | `observe/ops/update/` (`UpdateCheck`, `SelfUpdate`); serve `services/serve/update/`; SPA `src/spa/src/settings/sections/UpdatesSection.tsx` |
| Notification channel CRUD / test-send | `observe/notify/settings_write.py` + `tester.py`; serve adapter `services/serve/notifications/`; CLI `services/cli/commands/notifications.py` (`raft notifications …`); SPA `src/spa/src/notifications/` |
| GitHub OAuth / deploy assist | `platform/github/` (`GithubAssistService`); serve `services/serve/github/`; CLI `services/cli/commands/github.py` (`raft github …`) |
| Dashboard UI | `src/spa/` only (Release bakes; local `npm run build` for editable/`raft serve`) |
| Reusable dashboard kit (Trends / embeds) | `src/spa/src/dashboard-kit/`; Trends overview consumer in `trends/dashboard/ui/TrendsDashboard.tsx`. |
| Alert rules | `core/observe/alerts/` + `services/serve/alerts/` + `services/controller/jobs/alerts/` + SPA `src/spa/src/alerts/` |
| Setup recommendations (shared UI kit) | SPA `src/spa/src/recommendations/`; firewall + alerts plug in via callbacks; dismiss stores under `host/<area>/dismissed-recommendations.json` |
| Ops event timeline | `core/models/state/ops_event*` + `observe/ops/events/`; dual-write from `GraphEventStore`; serve `services/serve/events/`; CLI `services/cli/commands/events.py` (`raft events`); SPA `src/spa/src/events/` |
| Always-on dashboard | `lifecycle/dashboard/` + `share/dashboard/`; settings `dashboard:` (Settings UI); lifecycle Up/Down/Redeploy via `ServiceActions`; serve auth `services/serve/auth/`. |
| Notification strategies | `observe/notify/strategies/` + `catalogs.py`; SPA `src/spa/src/notifications/` |

Upstream files: `generated/nginx/upstreams/<app>-<port>.conf` mounted into the router.

---

## Packaging & install pitfalls

- **Release tags + wheels are the operator SoT** (`vX.Y.Z` GitHub Releases via PR labels `bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`). Publish bakes SPA and attaches a version-aligned `.whl`. Do not commit hashed `share/serve/spa/` assets.
- **`package-data`** must track `core/platform/share/…` (see `pyproject.toml`). Meta test fails if globs match nothing; Release/`scripts/release/build_release_wheel.sh` asserts the wheel contains SPA assets.
- **`raft update`** curls `install.sh` and prefers the **latest Release wheel** (same as bare `install.sh`; git@tag fallback). Use `raft update --ref <tag\|branch\|sha>` (or `RAFT_REF`) to pin. Broken wheel/package-data on a released tag bricks installs of that tag; recovery: `curl …/install.sh | bash -s -- --ref main` then fix forward.
- **Breaking cleanup (#312):** operator upgrade steps (backup → Firewall Save → update → doctor; `RAFT_REF` not `RAFT_BRANCH`; access-log rotate) live in [`README.md`](README.md) **Upgrade notes**. Do not resurrect a `docs/` tree for release checklists.
- Fresh-install e2e: `tests/e2e/fresh_install/` — bake SPA then `RAFT_E2E_REF=workspace` (CI and local packaging check).
- README demo video: GitHub only plays `<video>` when `src` is a **user-attachments** URL; keep `assets/raft-demo.mp4` as clone fallback. Do not call it “promo” in user-facing copy.

---

## Operator ship path (CI / service repos)

Service CI should:

```bash
raft apply --file .raft/app.yaml --ref "$SHA" --env …
```

(deploy on). Gate is **never** auto-recreated by service CI. Private git: `raft auth setup` before apply. Secrets: `spec.envFile` → `~/.raft/services/<app>/secrets/env` (0600); never bake DB passwords into manifests or `generated/`.

---

## Code style (enforceable)

Under `src/raft/`:

- ~200-line files; **300+** = split smell; methods **≤ ~20** lines (delegate to `_…` helpers).
- Class-first; package `__init__.__all__` eager exports; **no** lazy `__getattr__` barrels; **no** thin stub forwards.
- Imports at module scope only; `git mv` for renames.
- Tests: 100% unit branch coverage; meta size guards; e2e needs Docker (`-n0`).

---

## Tests (commands)

```bash
uv sync --extra dev
uv run pytest tests/unit # 100% cov
uv run pytest tests/meta --no-cov
uv run pytest tests/e2e -m e2e --no-cov -n0
```

Only commit when asked. No consumer app names, upstreams, or PEMs in the repo.
