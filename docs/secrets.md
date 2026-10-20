# App secrets on the host

Shrink **App↔App** and **disk/backup** blast radius for env material. This does **not** defeat a rooted VPS or `docker.sock` compromise — anything a container needs can still be read from that container after a host break.

## Current vs recommended

| Approach | Path example | Risk |
|----------|--------------|------|
| Flat / shared (legacy) | `~/.raft/demo.env` used by several Apps | One readable file exposes every App’s secrets |
| **Recommended** | `~/.raft/services/<app>/secrets/env` | Per-App directory (`0700`) + file (`0600`) |

Keep Compose `spec.envFile` as the injection mechanism — point it at the per-App path.

```yaml
spec:
  envFile: /home/raft/.raft/services/demo-api/secrets/env
```

Optional shared credential for a `spec.group`: one file such as
`~/.raft/services/demo-api/secrets/shared.env` that each App’s `envFile` can reference.
Prefer per-App files unless several Apps truly share one secret.

Dashboard OAuth material is host-scoped: `~/.raft/host/secrets/dashboard/`.

## What raft creates

On `ensure_raft_home` / apply:

- `~/.raft/services/` (parent)
- `~/.raft/services/<app>/secrets/` (mode `0700`) when that App is applied

Raft does **not** write secret values into `env`. Operators (or a follow-on
materializer — see epic #143 / #176) create the file:

```bash
install -m 600 /dev/null ~/.raft/services/demo-api/secrets/env
# then edit: DATABASE_URL=… etc.
```

## Never store secret values in

- Git / images
- `spec.env` in the App manifest (use placeholders only)
- Applied registry (`~/.raft/services/<app>/app.yaml`)
- `~/.raft/generated/`

`raft apply --env` / `--env-file` are for **non-secret** preprocess/CI strings
(stage flags, optional blocks). Bridge runtime secrets into the container by
materializing them in the per-App env file (or by resolving placeholders from
that file — not by baking secrets into registry YAML).

```yaml
# Prefer secret material in services/<app>/secrets/env, not in registry:
# DATABASE_URL=postgres://…
```

Gate and router must **never** mount App secret files or receive DB credentials.

## Migration from a flat shared `.env`

1. Create `~/.raft/services/<app>/secrets/` (apply does this) and copy only that App’s keys into `env` (`0600`).
2. Point `spec.envFile` at the new path; re-apply.
3. Remove the shared flat file once nothing references it.

See also [`docs/data-home-migrate.md`](data-home-migrate.md) for the #313 layout cutover.
