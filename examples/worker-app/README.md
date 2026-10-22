# Worker App

Background job / queue consumer with **no public ports** (`ports: []`). No Host routing, no gate upstreams — Compose service only.

## When to use

- Workers, cron-like containers, or sidecars that never listen publicly
- Pair with an HTTP App in the same `group` / `dependsOn` chain when needed

## Constraints

- `tls: off` only
- `readiness: none` (default when ports are empty)
- No `spec.scaling` (scale-to-zero needs `expose: http` + `publicHost`)

## Apply

```bash
raft apply --file examples/worker-app/.raft/app.yaml --ref "$SHA"
raft doctor
```

Replace `image` / `ref` / `metadata.name` before a real deploy. Optional secrets: create `~/.raft/services/<name>/secrets/env` (0600) and set `spec.envFile`.
