# App secrets on the host

Shrink **App↔App** and **disk/backup** blast radius for env material. This does **not** defeat a rooted VPS or `docker.sock` compromise — anything a container needs can still be read from that container after a host break.

## Current vs recommended

| Approach | Path example | Risk |
|----------|--------------|------|
| Flat / shared (legacy) | `~/.raft/demo.env` used by several Apps | One readable file exposes every App’s secrets |
| **Recommended** | `~/.raft/secrets/<app>/env` | Per-App directory (`0700`) + file (`0600`) |

Keep Compose `spec.envFile` as the injection mechanism — point it at the per-App path.

```yaml
spec:
  envFile: /home/raft/.raft/secrets/demo-api/env
```

Optional shared credential for a `spec.group`: one file such as
`~/.raft/secrets/demo/shared.env` that each App’s `envFile` can reference.
Prefer per-App files unless several Apps truly share one secret.

## What raft creates

On `ensure_raft_home` / apply:

- `~/.raft/secrets/` (mode `0700`)
- `~/.raft/secrets/<app>/` (mode `0700`) when that App is applied

Raft does **not** write secret values into `env`. Operators (or a follow-on
materializer — see epic #143 / #176) create the file:

```bash
install -m 600 /dev/null ~/.raft/secrets/demo-api/env
# then edit: DATABASE_URL=… etc.
```

## Never store secret values in

- Git / images
- `spec.env` in the App manifest (use placeholders only)
- Applied registry (`~/.raft/state/apps/*.yaml`)
- `~/.raft/generated/`

`raft apply --env` / `--env-file` are for **non-secret** preprocess/CI strings
(stage flags, optional blocks). Bridge runtime secrets into the container by
materializing them in the per-App env file (or by resolving placeholders from
that file — not by baking secrets into registry YAML).

```yaml
# Prefer secret material in secrets/<app>/env, not in registry:
# DATABASE_URL=postgres://…
```

Gate and router must **never** mount App secret files or receive DB credentials.

## Migration from a flat shared `.env`

1. Create `~/.raft/secrets/<app>/` (apply does this) and copy only that App’s keys into `env` (`0600`).
2. Point `spec.envFile` at the new path; re-apply.
3. Repeat per App; remove the shared flat file when nothing references it.
4. Run `raft doctor` — group/world-readable env paths warn with a Fix CTA (exit code stays 0 on warnings).

## Doctor

For each App with `spec.envFile` set:

- Missing file → **warn** + Fix toward `secrets/<app>/env`
- File or parent directory group/world-readable (`mode & 0077`) → **warn** + `chmod` Fix

First ship uses **warn** (not hard-fail) so existing stacks keep migrating without a flag day.
