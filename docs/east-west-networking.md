# East-west App networking

How raft Apps talk **to each other** on the Compose network (container → container), separate from the public edge path `gate → router → apps`.

Research background: [`docs/design/east-west-app-networking.md`](design/east-west-app-networking.md) (#219). Edge firewall (north-south only): [`docs/serve-firewall.md`](serve-firewall.md). Secrets: [`docs/secrets.md`](secrets.md).

Examples use `demo-api`, `demo-redis`, and documentation CIDRs such as `192.0.2.0/24` only.

---

## Two planes

| Plane | Traffic | Policy |
|-------|---------|--------|
| **North-south** | Internet / LAN client → **gate** → router → App | Ordered firewall on the gate (#207 / #211). Serve HTTP inspection is edge-only. |
| **East-west** | `demo-api` → `demo-redis` on the Compose network | Compose connectivity + operator discipline. **Not** gate firewall rules. |

There is **no** middle `raft-firewall` hop. Do not add gate rules expecting them to match container-to-container packets.

---

## What you get from Compose

All applied Apps (and gate / router / controller) run in Compose project **`raft`** on the default network **`raft_default`**.

| Concept | Contract |
|---------|----------|
| DNS hostname | Compose service id: `metadata.name`, or `{spec.group}-{metadata.name}` when `group` is set |
| Container name | `raft-{compose_id}-N` (project prefix) — prefer the **service DNS** name in URLs, not the container name |
| Internal listen | `ports[].expose: none` → Compose `expose` only (no host publish, no Host routing) |
| Workers | `ports: []` (or omit) — no listeners; outbound only |
| Start / wake order | `spec.dependsOn` — Compose `depends_on` plus scale/heal co-stop; does **not** open ports |
| Group | `spec.group` sets the DNS prefix and UI grouping — **not** a separate Docker network |

Fabricated dial:

```text
demo-api  →  redis://demo-redis:6379  →  demo-redis (expose: none)
```

With `spec.group: demo`, `metadata.name: api` → DNS `demo-api`; `metadata.name: redis` → DNS `demo-redis`.

---

## Recommended stack pattern

1. Put peers that talk to each other in the **same** `spec.group` so DNS ids stay obvious.
2. Mark data / sidecar listeners `expose: none` (or use a worker with no ports).
3. Point the caller at `compose_id:containerPort` via `spec.env` or `spec.envFile`.
4. Keep credentials in `~/.raft/secrets/<app>/env` (mode `0600`) — see [`secrets.md`](secrets.md).
5. Use `dependsOn` so deploy / wake starts the dependency first (optional `scaleWithParent`).

Pasteable manifests: [`examples/east-west-demo/`](../examples/east-west-demo/).

Caller env (non-secret host is fine in `spec.env`; password belongs in the secrets file):

```yaml
# demo-api manifest fragment
spec:
  group: demo
  dependsOn:
    - redis
  env:
    REDIS_URL: redis://demo-redis:6379
  # secrets dir uses metadata.name (api), not Compose DNS (demo-api)
  envFile: /home/raft/.raft/secrets/api/env
```

```bash
# ~/.raft/secrets/api/env  (0600) — fabricated
REDIS_PASSWORD=replace-me
```

Apply dependency first (or apply both; `dependsOn` warns if the peer is not registered yet):

```bash
raft apply --file examples/east-west-demo/demo-redis/.raft/app.yaml --ref alpine
install -m 600 /dev/null ~/.raft/secrets/api/env
raft apply --file examples/east-west-demo/demo-api/.raft/app.yaml --ref "$SHA"
raft doctor
```

---

## Internal-only and Serve

- Apps with only `expose: none` (or workers) have **no** public Host route — by design.
- Gate HTTP request inspection covers **edge** Host traffic only. An empty inspection panel for an internal App is expected.
- Gate firewall rules and documentation CIDRs (`192.0.2.0/24`) apply to **clients hitting the edge**, not to east-west dials.

---

## What raft does not do (by design)

- Auto-inject peer URL environment variables
- Per-group Docker networks or deny-by-default between unrelated Apps
- mTLS mesh / sidecars between Apps
- East-west enforcement via the gate ordered firewall

If you need stronger isolation than a single-VPS Compose network, that is outside this guide (host firewall, separate hosts, or an external mesh) — not a raft middle proxy.

---

## Related

| Topic | Link |
|-------|------|
| Manifest fields | [`docs/app-manifest.md`](app-manifest.md) |
| Grouped volume + `expose: none` sample | [`examples/grouped-volume-app/`](../examples/grouped-volume-app/) |
| Multi-App east-west sample | [`examples/east-west-demo/`](../examples/east-west-demo/) |
| Secrets blast radius | [`docs/secrets.md`](secrets.md) (#143 / #176) |
| Gate firewall | [`docs/serve-firewall.md`](serve-firewall.md) |
| Architecture locks | [`AGENTS.md`](../AGENTS.md) |
