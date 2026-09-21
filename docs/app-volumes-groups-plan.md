# App volumes, envFile, groups, dependsOn — implementation plan

Single source of truth for extending raft so **multi-service stacks** can be expressed as **N Apps** with shared operator control via **groups**.

**Consumer plan:** private ops `docs/cloud-sql-plan.md` Phase **Mr** / **M5** (deploy = consumer mail stack Apps `stack-*`, `spec.groups: [demo]`).

**Do not invent alternate field names mid-flight;** edit this file first.

---

## Roles (Who)

| Who | Means |
|-----|--------|
| **Me** | Coding agent in this raft checkout |
| **You** | Review PRs, paste Sanity / test output, merge |

---

## Goals

1. Apps can mount host paths (`volumes`) — required for shared data mounts.
2. Apps can load a shared env file and/or inline env — required for shared env + DB URI on multi-app stacks.
3. Apps declare **group membership**; doctor (and later CLI) can list/act by group.
4. Optional `dependsOn` for documentation + future ordered group actions (render may emit Compose `depends_on` between apps).
5. Keep **one Compose service per App**; no multi-service App YAML.
6. **100% test coverage** remains (`--cov-fail-under=100`).

## Non-goals (this plan)

- Full Kubernetes-like Controllers / Deployments.
- Network aliases / fixed container IPs (consumer unbound resolver) — defer; revisit if front cannot resolve peers by Compose service name.
- Implementing the consumer mail git repo (private ops Phase M5).
- Group actions beyond doctor listing in v1 (define stubs / CLI shape only if cheap).

---

## Locked schema (draft)

Canonical file remains **`.raft/app.yaml`** per App path (`apply --git … --path apps/stack-front`).

```yaml
apiVersion: raft/v1
kind: App
metadata:
  name: stack-front          # Compose service name; prefer a shared prefix per stack
spec:
  groups: [demo]            # NEW — non-empty strings; order preserved; dedupe
  dependsOn: [stack-smtp, stack-imap, stack-admin]  # NEW — other App names; optional
  envFile: /home/raft/.raft/demo.env               # NEW — absolute or ~/.raft-relative; optional
  env:                       # NEW — optional map; overrides envFile keys if both set
    SOME_FLAG: "1"
  volumes:                   # NEW — optional list
    - name: certs
      hostPath: /mnt/raft-data/demo/certs
      containerPath: /certs
      readOnly: true
  # … existing fields: publicHost, tls, source, image, ref, ports, readiness, resources
```

### Field rules

| Field | Rules |
|-------|--------|
| `groups` | List of strings `[a-z][a-z0-9-]*`; empty/omit = ungrouped; app may be in multiple groups |
| `dependsOn` | List of App names that must exist in registry when deploying group actions; **warn** on apply if missing (v1); render emits Compose `depends_on` with `condition: service_started` (not healthy — peers may lack healthchecks) |
| `envFile` | Single path string; must be readable at **render/deploy** time on the VPS; rendered as Compose `env_file: […]` |
| `env` | Map string→string; rendered as Compose `environment:`; **wins over** envFile for same key |
| `volumes[].hostPath` | Absolute path **or** path under data home; reject `..` traversal |
| `volumes[].containerPath` | Absolute container path |
| `volumes[].readOnly` | bool, default false |
| `volumes[].name` | Optional label for humans; not required by Compose bind syntax |

### Example (minimal docker App with volume + group)

```yaml
apiVersion: raft/v1
kind: App
metadata:
  name: stack-redis
spec:
  groups: [demo]
  source: docker
  image: redis
  ref: alpine
  path: apps/stack-redis
  envFile: /home/raft/.raft/demo.env
  volumes:
    - hostPath: /mnt/raft-data/demo/redis
      containerPath: /data
  ports:
    - name: redis
      containerPort: 6379
      expose: http   # or a new expose mode? → use expose that doesn't need publicHost
```

**Port note:** internal-only services today still need a `ports[]` entry for `expose` / health. Prefer `expose: http` only when routed; for redis use **`readiness.type: tcp`** and a port with **`expose: host` forbidden**. Check current model: if every port must be http|stream|host, we may need **`expose: none`** (internal only → Compose `expose:` without `ports:`).

### Locked addition: `expose: none` (or `internal`)

| Value | Compose |
|-------|---------|
| `http` | router Host routing (unchanged) |
| `stream` | gate stream (unchanged) |
| `host` | publish host port (unchanged) |
| **`none`** | **NEW** — container `expose` only; no host publish; no router; **no** `publicHost` required |

Internal smtp/imap/redis/antispam-style services use `expose: none`. Front uses `host` for 25/465/587/993. Admin uses `http` + `tls: origin`.

---

## Architecture impact

| Area | Change |
|------|--------|
| `models/ports.py` | Allow `expose: none` |
| `models/manifest.py` | Parse `groups`, `dependsOn`, `envFile`, `env`, `volumes`; store on `AppSpec` |
| `models/app.py` / registry | Persist new fields through apply → state YAML round-trip |
| `services/render.py` | Emit `env_file`, `environment`, `volumes`, per-app `depends_on` |
| `services/doctor.py` | Section or grouping by `groups`; list ungrouped separately |
| `cli` (`get apps`) | Show group column / filter `--group` |
| `AGENTS.md` + `examples/` | Document fields; add `examples/grouped-volume-app/` |
| Tests | Parse, render snapshots, doctor grouping, reject bad paths |

Router `depends_on` all apps (existing) stays. App→app `dependsOn` is additive under each service.

---

## Master step table

| # | Step | Who | Status |
|---|------|-----|--------|
| 0 | This plan + schema lock | Me / You approve | **done** (You approved 2026-09-21) |
| 1 | `expose: none` in ports model + tests | Me | **done** |
| 2 | Parse `groups` / `dependsOn` / `envFile` / `env` / `volumes` on `AppSpec` | Me | **done** |
| 3 | Registry round-trip (apply state YAML keeps new fields) | Me | **done** |
| 4 | Render Compose fragments | Me | **done** |
| 5 | Doctor + `get apps` group listing / `--group` | Me | **done** |
| 6 | Example manifest + AGENTS.md | Me | **done** |
| 7 | Full test suite green / coverage 100% | Me | **done** (`327 passed`, 100% cov) |
| 8 | Release / You merge; VPS `raft update` | You / Me | pending |

---

## Step details

### Step 0 — Approve schema

**Who:** **You**

Confirm locked field names above (`groups`, `dependsOn`, `envFile`, `env`, `volumes`, `expose: none`). Reply `Mr schema approved` or request renames **before** Step 1.

---

### Step 1 — `expose: none`

**Who:** Me

#### Execute

- Extend `PortSpec` / parser; forbid `publicPort` when `expose: none`.
- `publicHost` still required only if any port is `http` (or tls origin rules unchanged).

#### Sanity

```bash
cd /path/to/raft
uv run pytest tests/unit/test_models/ -q --tb=no
```

---

### Step 2 — AppSpec fields

**Who:** Me

#### Execute

- Add frozen fields on `AppSpec` with parsers validating paths and names.
- Reject relative `hostPath` with `..`; allow absolute paths for demo PD mounts.

#### Sanity

```bash
uv run pytest tests/unit/test_models/test_manifest.py -q
```

---

### Step 3 — Registry round-trip

**Who:** Me

#### Execute

- Ensure `apply` writes and reloads new fields from `~/.raft/state/apps/<name>.yaml`.
- Existing apps without fields keep defaults (empty groups, no volumes).

#### Sanity

```bash
uv run pytest tests/unit/test_services/test_apply.py tests/unit/test_models/ -q
```

---

### Step 4 — Render

**Who:** Me

#### Execute

Emit under each service (when set):

```yaml
    env_file:
      - /home/raft/.raft/demo.env
    environment:
      SOME_FLAG: "1"
    volumes:
      - /mnt/raft-data/demo/certs:/certs:ro
    depends_on:
      stack-smtp:
        condition: service_started
```

- Do not break router→apps healthy depends_on.
- Internal `expose: none` ports still appear under Compose `expose:`.

#### Sanity

```bash
uv run pytest tests/unit/test_services/ -q
uv run pytest tests/unit --cov=raft --cov-fail-under=100 -q
```

---

### Step 5 — Doctor + get

**Who:** Me

#### Execute

- `raft doctor`: group-first layout — heading `raft` (edge + host checks), then App groups (`demo`, …), then `ungrouped`; each member indented with status.
- `raft get apps [--group demo]`: filter; default table adds Groups column.
- Optional (if small): `raft redeploy --group demo` = redeploy each member in `dependsOn` topological order (defer if large).

#### Sanity

```bash
uv run pytest tests/unit/test_services/test_doctor.py tests/unit/test_cli.py -q
```

---

### Step 6 — Docs + example

**Who:** Me

#### Execute

- Update `AGENTS.md` App model tables.
- Add `examples/grouped-volume-app/.raft/app.yaml` (docker + volume + group + expose none/http as needed).
- README blurb if user-facing.

#### Sanity

You skim `AGENTS.md` diff.

---

### Step 7 — Coverage gate

**Who:** Me

```bash
cd /path/to/raft
uv run pytest tests/unit --cov=raft --cov-fail-under=100
```

**Expect:** pass.

---

### Step 8 — Ship

**Who:** You merge · Me tags/notes if needed · VPS upgrades via existing Update / `raft update`

#### Sanity (VPS, after upgrade)

```bash
sudo -u raft -H env HOME=/home/raft USER=raft LOGNAME=raft \
  PATH="/home/raft/.local/bin:/usr/local/bin:/usr/bin:/bin" \
  bash -lc 'raft doctor; raft get apps'
```

Sites must remain healthy (no demo Apps applied yet).

---

## Rollback

| Stage | Action |
|-------|--------|
| Before merge | Abandon branch |
| After merge, before demo apply | Pin previous raft on VPS; new fields unused by old manifests |
| After stack apps applied | `raft delete app stack-*` (order reverse of APPLY_ORDER); keep volumes on disk |

---

## Risks / open questions (resolve in Step 0 if possible)

1. **`envFile` path ownership** — file must be readable by Docker; mode 600 `raft:raft` is OK if compose runs as that user.
2. **Front vs raft gate on 80/443** — admin UI via gate; front must not host-publish 80/443 (private ops plan). Confirm the front image works with only mail ports published (may need overrides).
3. **Service DNS names** — Compose service name = `metadata.name` (`stack-front`). Consumer env often expects short hostnames like `front` / `admin`. May need `spec.hostnames` / network aliases later, or env overrides (`FRONT_ADDRESS=stack-front`). **Flag for M5:** set consumer env to raft service names.
4. **Group actions v1 scope** — doctor + get only in v1; `redeploy --group` deferred (You OK 2026-09-21).

---

## Progress log

| When | Note |
|------|------|
| 2026-09-21 | Plan created from vpsctl demo multi-App + groups decision |
| 2026-09-21 | Schema approved (You); `redeploy --group` deferred; start Step 1 |
| 2026-09-21 | Steps 1–7 implemented; `uv run pytest --cov=raft --cov-fail-under=100` green |

---

## Next command right now

**You:** review + commit/merge when ready, then VPS `raft update` (Step 8). No demo Apps yet.
