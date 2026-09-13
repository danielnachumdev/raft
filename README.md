# raft

**One cheap VPS. Many sites. No Kubernetes.**

`raft` is a small control plane for a single machine: a stable public **gate**, an inner **router**, and your apps — declared as App manifests and driven by a kubectl-ish CLI (`apply`, `get`, `up`, `redeploy`).

```text
Internet  →  gate (:80/:443)  →  router (Host:)  →  your apps
```

You keep writing services in their own repos. On the VPS you **apply** a `.raft/app.yaml`, and raft syncs sources, renders Compose/nginx, and cutovers without taking the public edge down.

## Why it exists

Kubernetes (and most “platform” stacks) are overkill when you have one VM and a handful of sites. Compose alone does not give you a desired-state registry, zero-downtime app cutover, or a boring operator CLI. raft does — and stays readable.

## Feel of the CLI

```bash
uv sync
uv run raft apply --git git@github.com:org/my-site.git
uv run raft up
uv run raft doctor
uv run raft redeploy my-site
uv run raft get apps
```

Apps own their contract (`.raft/app.yaml`). The VPS stores applied desired state under `state/apps/` (not committed). Generated Compose/nginx land in `.generated/` (also not committed).

## Requirements

- **Python 3.8+** (CI: 3.8–3.13)
- Runtime config: `raft.yaml` (logging); PyYAML
- Docker + Compose on the host
- For HTTPS: Cloudflare Origin PEMs per app under `certs/<name>/` (missing PEMs break the gate for HTTP too)

## Develop

```bash
uv sync --extra dev
uv run pytest          # 100% coverage required
uv run raft -- --help
```

Working on the codebase? See **[AGENTS.md](AGENTS.md)** for architecture rules, package map, and operator invariants.
