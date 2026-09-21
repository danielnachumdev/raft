# raft

**One cheap VPS. Many sites. No Kubernetes.**

`raft` is a small control plane for a single machine: a stable public **gate**, an inner **router**, and your apps — declared as App manifests and driven by a kubectl-ish CLI (`apply`, `get`, `up`, `redeploy`).

```text
Internet  →  gate (edge: http/https/streams)  →  router (Host:)  →  your apps
```

You keep writing services in their own repos. On the VPS you **apply** a `.raft/app.yaml`, and raft syncs sources, renders Compose/nginx, and cutovers without taking the public edge down — except when you deliberately run `raft gate recreate` to change published ports.

## Why it exists

Kubernetes (and most “platform” stacks) are overkill when you have one VM and a handful of sites. Compose alone does not give you a desired-state registry, zero-downtime app cutover, or a boring operator CLI. raft does — and stays readable.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh | bash
```

Operator data lives under **`~/.raft/`**. Override with `RAFT_DATA_HOME`. Refresh the CLI later with `raft update`.

```bash
raft doctor
raft up
```

## Feel of the CLI

```bash
raft apply --git git@github.com:org/my-site.git
raft up
raft doctor
raft redeploy my-site
raft gate recreate    # only when edge: published ports change
raft get apps
```

Apps own their contract (`.raft/app.yaml`). The VPS stores applied desired state under `~/.raft/state/apps/` and generated Compose/nginx under `~/.raft/generated/`. Settings: `~/.raft/settings.yaml` (logging + **edge** listeners).

## Examples

See **[`examples/`](examples/)** for copy-paste samples: operator [`settings.yaml`](examples/settings.yaml) and named scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`).

## Requirements

- **Python 3.8+** (CI: 3.8–3.13); uv can fetch an interpreter when needed  
- Runtime settings: `~/.raft/settings.yaml` (logging + edge); template in [`examples/settings.yaml`](examples/settings.yaml)  
- Docker + Compose on the host  
- For HTTPS: set `tls: origin` on the App and install Cloudflare Origin PEMs under `~/.raft/certs/<name>/` (HTTP-only apps need no certs)

## Develop

```bash
git clone https://github.com/danielnachumdev/raft.git && cd raft
uv sync --extra dev
uv run pytest                              # unit + integration
uv run pytest tests/unit --cov=raft --cov-fail-under=100
uv run pytest tests/e2e -m e2e             # needs Docker; all CI Py versions
uv run raft -- --help  # or re-run ./install.sh / uv tool install --force -e .
```

Working on the codebase? See **[AGENTS.md](AGENTS.md)** and **[docs/testing-plan.md](docs/testing-plan.md)**.
