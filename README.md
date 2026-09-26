# raft

**Kubernetes-ish behaviour with Docker and nginx — built to reduce resource use under constrained hosting.**

`raft` is a small control plane — a stable public **gate**, an inner **router**, and your apps — driven by App manifests and a kubectl-style CLI (`apply`, `get`, `up`, `redeploy`).

```text
Internet  →  gate (edge: http/https/streams)  →  router (Host:)  →  your apps
```

You keep writing services in their own repos. On the VPS you **apply** a `.raft/app.yaml`, and raft syncs sources, renders Compose/nginx, and cutovers without taking the public edge down — except when you deliberately run `raft gate recreate` to change published ports.

## Why it exists

An attempt to learn the problems Kubernetes solved by tackling them without a full cluster: desired-state apps, a boring operator CLI, and cutover that does not take the public edge down. Docker and nginx keep the footprint small enough for constrained hosting; Compose alone does not give you a registry, zero-downtime cutover, or that CLI. raft does — and stays readable.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh | bash
```

Operator data lives under **`~/.raft/`**. Override with `RAFT_DATA_HOME`. Refresh the CLI later with `raft update`. Remove everything with `raft uninstall --yes` (add `--uv` only if you also want the uv installer gone).

```bash
raft doctor
# Then apply an App (deploy on by default), e.g.:
#   raft apply --file .raft/app.yaml --ref "$SHA"
```

## Feel of the CLI

**Recommended (CI and operators):** one `apply` with deploy on (the default). That registers the App and calls `ensure_app_deployed` — cutover if the service is already running, start it if the gate is up, else bring the stack up. Same command for first boot and later releases:

```bash
raft apply --file .raft/app.yaml --ref "$SHA" --env CI_DATABASE_URL=…
# or: raft apply --git git@github.com:org/my-site.git --ref "$SHA"
raft doctor
raft get apps
```

Do **not** use `--no-deploy` + `raft sync` + `raft redeploy` as the default pipeline. `redeploy` requires the app Compose service to already be running; on a **new** App it fails with `service '…' is not running — bring the stack up first`.

```bash
# Optional: cutover only (app already running; registry unchanged)
raft redeploy my-site --ref "$SHA"

# Only when edge: published ports change
raft gate recreate
```

`--no-deploy` is for register-only (several apps then one `raft up`, or apply before Origin PEMs exist). Afterwards deploy with apply again (deploy on) or `raft up`.

One committed App manifest can serve Dev and Prod via `${VAR}` / `${VAR:-default}` placeholders. Expansion runs at `raft apply` on the **entire** manifest text — including comments — (process env → optional `--env-file` → repeatable `--env`; later wins). Registry stores expanded YAML. Escape literal demo placeholders in comments as `$${NAME}`.

To pass a CI value into the **container**, declare the Docker name in `spec.env` (or path in `spec.envFile`) and template the CI name:

```yaml
spec:
  envFile: ${CI_ENV_FILE}
  env:
    DATABASE_URL: ${CI_DATABASE_URL}   # container key ← apply-time template
```

Then: `raft apply --file .raft/app.yaml --env CI_DATABASE_URL=…` (or export it in the job). CLI `--env` alone does not inject Compose env without that bridge.

Apps own their contract (`.raft/app.yaml`). Optional `spec.resources.limits` / `reservations` (alias `requests`) become Compose `deploy.resources` — see [`examples/http-only-site/.raft/app.yaml`](examples/http-only-site/.raft/app.yaml) and [`AGENTS.md`](AGENTS.md). The VPS stores applied desired state under `~/.raft/state/apps/` and generated Compose/nginx under `~/.raft/generated/`. Settings: `~/.raft/settings.yaml` (logging + **edge** listeners + optional **healing**).

The Compose stack always runs **`raft-controller`**. Phase 1 self-heal is **off** by default; enable `healing:` in settings (keys/defaults in [`examples/settings.yaml`](examples/settings.yaml)). When enabled: observe apps → after `failThreshold`, one Compose restart/start → one cutover/redeploy (`ensure_app_deployed`) → give up until the controller restarts. Apps only — never gate.

## Examples

See **[`examples/`](examples/)** for copy-paste samples: operator [`settings.yaml`](examples/settings.yaml) and named scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`, `grouped-volume-app`).

## Requirements

- **Python 3.8+** (CI: 3.8–3.13); uv can fetch an interpreter when needed  
- Runtime settings: `~/.raft/settings.yaml` (logging + edge + optional healing); template in [`examples/settings.yaml`](examples/settings.yaml)  
- Docker + Compose on the host  
- For HTTPS: set `tls: origin` on the App and install Cloudflare Origin PEMs under `~/.raft/certs/<name>/` (HTTP-only apps need no certs)

## Develop

```bash
git clone https://github.com/danielnachumdev/raft.git && cd raft
uv sync --extra dev
uv run pytest                              # unit + integration + meta (-n auto, 100% cov)
uv run pytest tests/unit                   # unit only (same defaults)
uv run pytest tests/meta --no-cov          # codebase size/body guards
uv run pytest tests/e2e -m e2e --no-cov -n0  # needs Docker; serial; all CI Py versions
uv run raft -- --help  # or re-run ./install.sh / uv tool install --force -e .
```

Working on the codebase? See **[AGENTS.md](AGENTS.md)** (package map under `src/raft/`).
