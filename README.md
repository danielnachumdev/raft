# raft

**Kubernetes-ish behaviour with Docker and nginx — for hosts that can’t spare a full cluster.**

A small control plane on your VPS: a public **gate**, an inner **router**, and your apps. You describe each service in `.raft/app.yaml` and drive everything with a kubectl-style CLI.

```text
Internet  →  gate  →  router (Host:)  →  your apps
```

Services stay in their own repos. On the VPS you `apply` a manifest; raft syncs sources, renders Compose/nginx, and cutovers without taking the public edge down (except when you change published ports with `raft gate recreate`).

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh | bash
```

Needs **Python 3.8+**, Docker, and Compose. Operator data lives under **`~/.raft/`** (override with `RAFT_DATA_HOME`). Later: `raft update` to refresh the CLI, `raft uninstall --yes` to remove everything.

Copy ideas from [`examples/settings.yaml`](examples/settings.yaml) into `~/.raft/settings.yaml` (logging, edge listeners, optional healing). For HTTPS Origin TLS, put PEMs under `~/.raft/certs/<app>/` before the first deploy.

## Quick start

```bash
raft doctor
raft apply --file .raft/app.yaml --ref "$SHA"
# or: raft apply --git git@github.com:org/my-site.git --ref "$SHA"
raft get apps
```

`apply` registers the App and deploys by default — first boot and later releases use the same command. Pass `--env` / `--env-file` when the manifest uses `${VAR}` placeholders (see [`examples/`](examples/)).

## Common commands

| Command | When |
|---------|------|
| `raft apply --file …` / `--git …` | Register + deploy (default path) |
| `raft doctor` | Health check + fix hints |
| `raft status` | CPU/memory snapshot (`--live` to watch) |
| `raft serve` | Localhost SSR UI (default `:8787`); SSH tunnel from your laptop |
| `raft logs [name…]` | Container stdout/stderr (`--tail N`; `-f` / `--follow`) |
| `raft redeploy <app>` | Cutover when the app is already running |
| `raft gate recreate` | After changing published edge ports in settings |
| `raft up` / `raft down` | Bring the whole stack up or tear it down |

### Viewing `raft serve` from your laptop

The UI binds **`127.0.0.1` only** (not the public gate). On a terminal-only VM, port-forward then open the URL locally:

```bash
raft serve                 # default http://127.0.0.1:8787/
raft serve --port=8787     # optional

# on your laptop (pick one):
ssh -L 8787:127.0.0.1:8787 USER@VM_HOST
gcloud compute ssh VM_NAME --zone=ZONE -- -L 8787:127.0.0.1:8787
```

Then open `http://127.0.0.1:8787/` in your laptop browser. Stop with Ctrl+C.

## Examples

Copy-paste samples in **[`examples/`](examples/)**: operator settings and scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`, `grouped-volume-app`).

## Develop

```bash
git clone https://github.com/danielnachumdev/raft.git && cd raft
uv sync --extra dev
uv run pytest
uv run raft -- --help
```

Working on the codebase? See **[AGENTS.md](AGENTS.md)**.
