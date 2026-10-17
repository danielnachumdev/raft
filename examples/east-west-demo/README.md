# East-west demo (`demo-api` → `demo-redis`)

Two Apps in `spec.group: demo` on the shared Compose network:

| App | `metadata.name` | Compose DNS | Edge |
|-----|-----------------|-------------|------|
| API | `api` | `demo-api` | Host-routed HTTP (`expose: http`) |
| Redis | `redis` | `demo-redis` | Internal only (`expose: none`) |

The API dials `redis://demo-redis:6379` (set in `spec.env`). Secrets directories use **`metadata.name`** (`api` → `~/.raft/secrets/api/env`), while Compose DNS uses **`group-name`** (`demo-api`). See [`docs/secrets.md`](../../docs/secrets.md). Full guide: [`docs/east-west-networking.md`](../../docs/east-west-networking.md).

These manifests are **samples** — replace `publicHost`, image/ref, and secret paths before a real deploy. No live inventory.

## Apply

```bash
# Internal peer first (or apply both; dependsOn warns if redis is missing)
raft apply --file examples/east-west-demo/demo-redis/.raft/app.yaml --ref alpine
install -m 600 /dev/null ~/.raft/secrets/api/env
# optional: echo 'REDIS_PASSWORD=…' >> ~/.raft/secrets/api/env
raft apply --file examples/east-west-demo/demo-api/.raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default. Gate firewall rules do **not** govern `demo-api` → `demo-redis` traffic.
