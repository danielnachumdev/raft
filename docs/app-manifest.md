# App manifests

How a `.raft/app.yaml` becomes desired state — including apply-time env and conditional blocks.

Canonical path in a service repo: **`.raft/app.yaml`**. Shape: `apiVersion: raft/v1`, `kind: App`, `metadata`, `spec`. Copy-paste scenarios live under [`examples/`](../examples/). Exhaustive field rules for agents: [`AGENTS.md`](../AGENTS.md).

## What you declare

Typical `spec` concerns (omit what you do not need):

| Area | Examples |
|------|----------|
| Source | `local` / `git` / `docker` + `ref` |
| Exposure | `ports[]` with `expose: http \| stream \| host \| none`; `publicHost` when any port is `http` |
| Host aliases | `extraHosts` — additional Host names for router (and future ACME SANs); `www.<publicHost>` is **not** automatic — list it here if you want it |
| TLS | `tls: off` (default) or `origin` (needs PEMs under `~/.raft/certs/<app>/`) |
| Runtime | `env` / `envFile`, `volumes`, `group`, `dependsOn`, `resources`, `readiness` |
| Scaling | `scaling` (`idleSeconds`/`minUpSeconds` required; `wakeTimeoutSeconds` defaults to 60; HTTP + `publicHost` only) |

**Breaking change:** `spec.www` was removed. Routing hostnames are `publicHost` + `extraHosts` only. If you previously relied on the default `www: true`, add `www.<your-publicHost>` to `extraHosts`.

## Apply-time preprocess

`raft apply` runs on the **raw** manifest text **before** YAML parse:

1. Resolve `${{ if expr }}` … `${{ endif }}` (full-line `#` comments skipped).
2. Expand remaining `${NAME}` / `${NAME:-default}` in non-comment text.
3. Parse YAML → registry (concrete; no placeholders left).

Feed values with repeatable `--env KEY=value` and/or `--env-file`. Values are strings (any shape). Render / redeploy / doctor never re-run this pipeline.

### Optional blocks

Keep optional keys out of the committed shape when a predicate is false:

```yaml
${{ if ${INCLUDE_SCALING} == 'true' }}
scaling:
  idleSeconds: ${SCALE_IDLE_SECONDS}
  wakeTimeoutSeconds: ${SCALE_WAKE_TIMEOUT_SECONDS}
  minUpSeconds: ${SCALE_MIN_UP_SECONDS}
${{ endif }}
```

Pasteable version: [`examples/http-only-site/optional-block.snippet.yaml`](../examples/http-only-site/optional-block.snippet.yaml).

```bash
raft apply --file .raft/app.yaml --ref "$SHA" \
  --env INCLUDE_SCALING=true \
  --env SCALE_IDLE_SECONDS=300 \
  --env SCALE_WAKE_TIMEOUT_SECONDS=60 \
  --env SCALE_MIN_UP_SECONDS=60
```

In `expr`: quoted strings or `${VAR}` / `${VAR:-default}` only; `==` / `!=`; `&&` binds tighter than `||`; parentheses and nested `if` are supported.

### `--env` vs `spec.env` / `spec.envFile`

| Mechanism | When it runs | What it is for |
|-----------|--------------|----------------|
| `--env` / `--env-file` on `apply` | Preprocess (manifest text) | Stage flags, optional blocks, filling placeholders in the YAML itself |
| `spec.env` / `spec.envFile` | Rendered into Compose for the container | Runtime config inside the app |

Bridge CI/host values into the container with placeholders in `spec.env`:

```yaml
spec:
  env:
    DATABASE_URL: ${CI_DATABASE_URL}
```

```bash
raft apply --file .raft/app.yaml --ref "$SHA" \
  --env CI_DATABASE_URL="$DATABASE_URL"
```

## Ship path

```bash
raft apply --file .raft/app.yaml --ref "$SHA" --env KEY=value
```

Same command for first boot and later cutovers. Depth and edge cases: [`AGENTS.md`](../AGENTS.md) (App manifest model + ManifestPreprocessor).

## Scale-to-zero (`spec.scaling`)

Omit the whole `scaling` mapping → the App is not scaled. When present, `idleSeconds` and `minUpSeconds` are required. **`wakeTimeoutSeconds` may be omitted and defaults to 60**; set it on the App to override.

After the wake budget, the product `holding-timeout.html` page asks visitors to contact the administrator and shows a **server-minted** diagnostic id (not a browser UUID). The same id is on controller log lines (`id=`). Successful wakes within budget never show the timeout page. The holding page stays “Just a moment” + auto-refresh.
