# App manifests

How a `.raft/app.yaml` becomes desired state — including apply-time env and conditional blocks.

Canonical path in a service repo: **`.raft/app.yaml`**. Shape: `apiVersion: raft/v1`, `kind: App`, `metadata`, `spec`. Copy-paste scenarios live under [`examples/`](../examples/). Exhaustive field rules for agents: [`AGENTS.md`](../AGENTS.md).

## What you declare

Typical `spec` concerns (omit what you do not need):

| Area | Examples |
|------|----------|
| Source | `local` / `git` / `docker` + `ref` |
| Exposure | `ports[]` with `expose: http \| stream \| host \| none`; `publicHost` when any port is `http`; omit / `ports: []` for workers (see below) |
| Host aliases | `extraHosts` — additional Host names for router + ACME SANs; `www.<publicHost>` is **not** automatic — list it here if you want it |
| TLS | `tls: off` (default), `origin` (operator PEMs), or `acme` (public Let's Encrypt on the gate) — see **TLS modes** below |
| Runtime | `env` / `envFile`, `volumes`, `group`, `dependsOn`, `resources`, `readiness` |
| Scaling | `scaling` (`idleSeconds`/`minUpSeconds` required; `wakeTimeoutSeconds` defaults to 60; HTTP + `publicHost` only) |

## Worker Apps (no listeners)

Background workers that only run a process (no HTTP/stream/host listeners) may **omit `spec.ports`** or set `ports: []`. Defaults when ports are empty: `readiness.type: none`, `tls: off`. Do not invent a placeholder port.

```yaml
apiVersion: raft/v1
kind: App
metadata:
  name: worker
spec:
  source: docker
  image: ghcr.io/example/worker
  ref: latest
  # ports omitted or ports: []
  readiness:
    type: none
  tls: off
```

**Health:** no Host/TCP probe and no edge route. Raft treats the container as healthy when Docker reports it running; the healer restarts exited/dead services; doctor reports runtime status. `raft status`, controller metrics, and `raft serve` still include the service. There is no deploy-time wait-until-running for `readiness: none`. Not eligible for `scaling` or `tls: origin|acme`.

**Breaking change:** Unknown `spec` / `metadata` keys fail apply (allowlist). Hostnames are `publicHost` + `extraHosts` only — put former `www` aliases in `extraHosts` (e.g. `www.<publicHost>`).

## TLS modes

| Mode | When | Operator action |
|------|------|-----------------|
| `tls: off` | HTTP only (or TLS terminated elsewhere) | None |
| `tls: acme` | Browser hits the VPS on :443 (direct HTTPS) | DNS A/AAAA for `publicHost` + each `extraHosts` entry → VPS; TCP **80** and **443** open; set `acme.email` in settings; apply. **Do not paste PEMs.** |
| `tls: origin` | Upstream proxy (e.g. Cloudflare) presents the browser cert; gate uses Origin PEMs | Install `~/.raft/certs/<name>/origin.{pem,key}` **before** deploy |

### `tls: acme` checklist

1. Point DNS A/AAAA for `publicHost` (and every `extraHosts` name) at the VPS.
2. Keep `edge.http` (default 80) and `edge.https` (default 443) published — HTTP-01 is answered by the **gate**, not the App (works while scale-to-zero).
3. Set `acme.email` in `~/.raft/settings.yaml` (see [`examples/settings.yaml`](../examples/settings.yaml)). Production directory is the default; use the Let's Encrypt **staging** URL for labs.
4. `raft apply …` (deploy on). Issuance is best-effort after the gate is up — apply does **not** fail if ACME is slow/down; check `raft doctor` / `raft doctor <name>`.
5. Renewal is the always-on controller (`acme:<name>` jobs). Gate reloads nginx only — never `raft gate recreate` for cert rotation.

**Not shipped:** DNS-01 / wildcards. If port 80 cannot be opened to the public internet, use `tls: origin` behind a proxy, or terminate TLS elsewhere — do not expect raft to issue via DNS-01 in v1.

Sample App: [`examples/https-acme-site/`](../examples/https-acme-site/).

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
