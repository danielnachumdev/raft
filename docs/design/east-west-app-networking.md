# Research: east-west App networking

Status: **research note** for [#219](https://github.com/danielnachumdev/raft/issues/219).
Implementation child: [#220](https://github.com/danielnachumdev/raft/issues/220).

Audience: product maintainers deciding ship shape. Operator how-to (if this note’s recommendation ships as docs) lives separately under `docs/` + `examples/` — not in this file.

PII-safe placeholders only: `demo-api`, `demo-redis`, `192.0.2.0/24`.

---

## Recommendation

**docs-only** — fill the operator documentation and examples gap; **no product code** in this track.

Compose already gives stable DNS, a shared project network, `expose: none` for internal listeners, `group` / `dependsOn` for naming and start/wake order, and `env` / `envFile` for peer connection strings. Inventing mesh-lite, peer-URL injection, or east-west network policy would add surface without solving a correctness gap the edge plane does not already own.

**Not chosen:**

| Option | Why not |
|--------|---------|
| Small product ship | Env injection of peer URLs, network segmentation, and serve “internal endpoint” chrome are conveniences; Compose DNS + secrets already work. Segmentation would fight the flat `raft` project (router must reach every App). |
| No-ship (Compose is enough) | Functionally true, but operators lack a single place that names DNS ids, `expose: none`, and the gate-ACL boundary — that gap is real. |
| Defer with triggers | Unnecessary when the docs gap is cheap to close now. Product triggers listed at the end if demand appears later. |

---

## Boundary: east-west vs gate ACL

| Plane | Path | Policy surface | Product |
|-------|------|----------------|---------|
| **North-south** | Client → **gate** → router → App (`expose: http` / stream / host) | Ordered firewall on the **gate** ([#207](https://github.com/danielnachumdev/raft/issues/207) / [#211](https://github.com/danielnachumdev/raft/issues/211)); Serve HTTP inspection | Shipped |
| **East-west** | App → App on the Compose network (e.g. `demo-api` → `demo-redis`) | None in raft today — Docker/Compose connectivity only | Document; do not add a middle hop |

**Hard lock:** do **not** propose a middle `raft-firewall` service or hop. Edge policy stays policy-on-gate. East-west traffic never enters gate Host routing when the peer uses `expose: none` or is a worker (`ports: []`).

Gate rules that mention a service or CIDR (including documentation CIDRs like `192.0.2.0/24`) apply to **edge** clients hitting published listeners — not to container-to-container packets on `raft_default`.

---

## Research answers

### 1. What works today?

| Building block | Behavior operators can rely on |
|----------------|--------------------------------|
| Compose project | Fixed name `raft` ([`COMPOSE_PROJECT`](../../src/raft/core/core/models/app.py)); default network `raft_default`. All applied Apps + gate/router/controller share it unless Docker is customized outside raft. |
| DNS hostname | Compose service id = `metadata.name`, or `{spec.group}-{metadata.name}` when `group` is set (`compose_service_id`). Example: group `demo`, name `redis` → peers dial `demo-redis:6379`. |
| `expose: none` | Port is listed under Compose `expose:` only — no host publish, no router upstream, no gate Host server ([`NoneEdge`](../../src/raft/core/lifecycle/render/edge/strategies/none.py)). |
| `expose: http` / stream / host | North-south paths; peers *can* still use Compose DNS to the same container port, but public Host routing is a separate concern. |
| Workers (`ports: []`) | No listeners; no Host→router path; still on the same network (outbound only). |
| `spec.group` | Naming / UI grouping only for Compose id — **not** a separate Docker network. |
| `spec.dependsOn` | Compose `depends_on` (started) + wake/heal/idle co-stop ordering. Does not open or restrict ports. |
| `spec.env` / `spec.envFile` | How apps learn peer URLs and credentials (operator-written). |
| Example | [`examples/grouped-volume-app/`](../../examples/grouped-volume-app/) — internal Redis-shaped App (`expose: none`); does not yet show a caller App. |

Fabricated stack: `demo-api` (HTTP + `publicHost`) sets `REDIS_URL=redis://demo-redis:6379` via `~/.raft/secrets/demo-api/env`; `demo-redis` uses `expose: none` and never appears on the gate Host map.

### 2. Discovery & ergonomics

**Compose DNS + manifest fields are enough** for v1 ergonomics.

Stable contract to document:

1. Dial **`compose_id:containerPort`** (not the registry `metadata.name` alone when `group` is set).
2. Put non-secret host/port in `spec.env` or secrets file; put passwords only in `~/.raft/secrets/<app>/env` ([`docs/secrets.md`](../secrets.md)).
3. Prefer the same `spec.group` for stacks that talk to each other so DNS ids stay predictable (`demo-api`, `demo-redis`).

**Not recommended as product work now:** auto-injecting `RAFT_PEER_*` / generated peer URL env vars, or a serve panel that invents “internal endpoints” as a second source of truth. Those duplicate Compose DNS and drift when operators rename `group` or ports.

### 3. Network policy / isolation

**Stay flat Compose network + operator discipline.**

- Unrelated Apps on one VPS already share `raft_default`; isolation today is “don’t dial peers you weren’t given credentials/URLs for” plus per-App secrets blast-radius practice.
- Optional deny-by-default between groups would require custom networks, break router→App reachability assumptions, and reopen middle-hop temptation — reject for this track.
- Interaction with gate ACL: **none**. [#207](https://github.com/danielnachumdev/raft/issues/207) does not and should not filter east-west.

### 4. Firewall implications

| Concern | Belongs in |
|---------|------------|
| Who may hit `publicHost` / edge ports | Gate ordered firewall ([`docs/serve-firewall.md`](../serve-firewall.md)) |
| Whether `demo-redis` is reachable from the internet | Manifest: `expose: none` (and no `host` publish) — not a firewall rule |
| Whether `demo-api` may dial `demo-redis` | Docs + secrets; not a raft firewall feature |

Product east-west firewall: **none**. Docs must say so explicitly so operators do not file gate rules expecting container traffic to match.

### 5. Serve UX

“Internal only” today means: no public Host route for that port (`expose: none` or worker). Consequences already true by design:

- No edge HTTP request inspection rows for that App (gate access log is north-south).
- TLS origin/acme and scaling affordances do not apply to workers / non-HTTP internal sidecars (existing manifest rules).

**Docs should state that**, including that an empty HTTP-requests panel for an internal App is expected — not a bug.

**Do not** resume aborted “hide HTTP requests for internal apps” product work as part of #220. Optional later polish (label badge “internal” when all ports are `none` / empty) is a separate UX ticket if operators ask; not required to close the east-west gap.

### 6. Mesh-lite / sidecars

**Out of raft’s scope** for the foreseeable future (no mTLS mesh, no sidecar identity plane). Operators who need App↔App encryption use application TLS, host network policy outside raft, or an external mesh — not a raft-generated hop.

### 7. Secrets & blast radius

Align with [#143](https://github.com/danielnachumdev/raft/issues/143) / [#176](https://github.com/danielnachumdev/raft/issues/176) and [`docs/secrets.md`](../secrets.md) without expanding materialization here:

- Peer **connection strings** with credentials live in `~/.raft/secrets/demo-api/env` (0600), not in `state/apps` / `generated/` / git.
- Optional shared group file (`~/.raft/secrets/demo/shared.env`) only when several Apps truly share one secret; prefer per-App files.
- Gate/router must never mount App secret files (already documented).
- Discovery hostname (`demo-redis`) is not secret; the password is.

### 8. Docs vs code

| Prefer now | Defer |
|------------|--------|
| Operator guide: Compose DNS, `expose: none`, `dependsOn`, boundary vs gate ACL | Peer URL env injection |
| Multi-App example: `demo-api` → `demo-redis` | Compose network segmentation / per-group networks |
| Cross-links from [`docs/app-manifest.md`](../app-manifest.md), [`examples/README.md`](../../examples/README.md), secrets, firewall docs | Serve “internal endpoint” chrome; mesh |

---

## Proposed #220 acceptance (docs delivery)

Concrete, testable criteria for the implementation child when this recommendation is accepted:

1. Add an operator-facing doc (e.g. `docs/east-west-networking.md`) covering Compose DNS (`NAME` / `GROUP-NAME`), shared `raft_default`, `expose: none`, workers, `dependsOn`, peer URLs via `env`/`envFile`, and the east-west vs gate ACL boundary (no middle hop).
2. Ship a PII-safe multi-App example (`demo-api` + `demo-redis`) under `examples/` showing internal dial + secrets path; index it from `examples/README.md`.
3. Cross-link from `docs/app-manifest.md`, `docs/secrets.md`, and `docs/serve-firewall.md` (short “not this plane” pointers where useful).
4. No lifecycle/serve/Compose product features; no gate/router redesign; no middle `raft-firewall` hop.
5. Proof: doc + example review; no new unit surface required unless examples trip meta guards.

---

## Triggers to reopen product work

Revisit a **small product ship** only if one of these becomes concrete:

- Operators repeatedly mis-wire `group` vs DNS and ask for generated peer URL env vars after docs land.
- A hard multi-tenant isolation requirement appears that Compose networks can meet without a middle proxy hop (design would still need a separate research note).
- Serve UX research shows operators cannot tell internal vs edge Apps apart after docs + labels in copy alone.

Until then, keep #220 scoped to documentation and examples.

---

## Related

- Research: [#219](https://github.com/danielnachumdev/raft/issues/219)
- Implementation child: [#220](https://github.com/danielnachumdev/raft/issues/220)
- Edge firewall (north-south): [#207](https://github.com/danielnachumdev/raft/issues/207), [#211](https://github.com/danielnachumdev/raft/issues/211), [`docs/serve-firewall.md`](../serve-firewall.md)
- Secrets blast radius: [#143](https://github.com/danielnachumdev/raft/issues/143), [#176](https://github.com/danielnachumdev/raft/issues/176), [`docs/secrets.md`](../secrets.md)
- Manifest / multi-app: [`docs/app-manifest.md`](../app-manifest.md), [`examples/grouped-volume-app/`](../../examples/grouped-volume-app/)
- Architecture locks: [`AGENTS.md`](../../AGENTS.md) (`gate → router → apps`; no middle firewall hop)
