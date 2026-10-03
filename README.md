# raft

**Kubernetes-ish behaviour with Docker and nginx — for hosts that can’t spare a full cluster.**

A small control plane on your VPS: a public **gate**, an inner **router**, and your apps. You describe each service in `.raft/app.yaml` and drive everything with a kubectl-style CLI.

```text
Internet  →  gate  →  router (Host:)  →  your apps
```

Services stay in their own repos. On the VPS you `apply` a manifest; raft syncs sources, renders Compose/nginx, and cutovers without taking the public edge down (except when you change published ports with `raft gate recreate`).

When you want a browser instead of only SSH and `docker stats`, run **`raft serve`**: a localhost ops dashboard for live status, service actions, logs, and resource trends — tunnel it from your laptop.

## Install

```bash
curl -fsSL https://raw.githubusercontent.com/danielnachumdev/raft/main/install.sh | bash
```

Needs **Python 3.8+**, Docker, and Compose. Operator data lives under **`~/.raft/`** (override with `RAFT_DATA_HOME`). Later: `raft update` to refresh the CLI, `raft uninstall --yes` to remove everything.

Copy ideas from [`examples/settings.yaml`](examples/settings.yaml) into `~/.raft/settings.yaml` (logging, edge listeners, optional healing / metrics). For HTTPS Origin TLS, put PEMs under `~/.raft/certs/<app>/` before the first deploy.

## Quick start

```bash
raft doctor
raft apply --file .raft/app.yaml --ref "$SHA"
# or: raft apply --git git@github.com:org/my-site.git --ref "$SHA"
raft get apps
raft status
raft serve   # then open via SSH tunnel — see below
```

`apply` registers the App and deploys by default — first boot and later releases use the same command. Pass `--env` / `--env-file` for `${VAR}` and `${{ if }}` (see [`examples/http-only-site/optional-block.snippet.yaml`](examples/http-only-site/optional-block.snippet.yaml) and `AGENTS.md`). Full-line `#` comments are not preprocessed.

## Ops dashboard (`raft serve`)

One process on the VM: a React SPA plus JSON APIs, bound to **`127.0.0.1` only** (never the public gate). From a terminal-only host, port-forward and open the UI on your laptop:

```bash
raft serve                 # default http://127.0.0.1:8787/
raft serve --port=8787     # optional
raft serve --stop          # stop an already-running serve on that port

# on your laptop (pick one):
ssh -L 8787:127.0.0.1:8787 USER@VM_HOST
gcloud compute ssh VM_NAME --zone=ZONE -- -L 8787:127.0.0.1:8787
```

Then open `http://127.0.0.1:8787/`. Stop with Ctrl+C or `raft serve --stop`.

**What you get:**

- **Live status tables** — host + control plane + apps; compact layout; column sort/filter; health and utilization color cues; Started beside Uptime; auto-refresh while the tab is visible
- **Quick actions** on each row (start / stop / redeploy / logs) with confirmations and toast feedback
- **Service detail** — public URLs when the app has a `publicHost`, Runtime metrics charts over time, start/stop/redeploy, and container logs (snapshot, live follow, expand/filter)
- **Trends** — CPU / memory history from the always-on controller (`~/.raft/state/metrics/resources.jsonl`), with time range and service filters

Same facts as `raft status` / `raft logs`, in a UI you can leave open while you operate.

## Common commands

| Command | When |
|---------|------|
| `raft apply --file …` / `--git …` | Register + deploy (default path) |
| `raft doctor` | Health check + fix hints |
| `raft status` | CPU/memory snapshot (`--live` to watch) |
| `raft serve` | Localhost ops dashboard (default `:8787`); `--stop` to terminate; SSH tunnel from your laptop |
| `raft logs [name…]` | Container stdout/stderr (`--tail N`; `-f` / `--follow`) |
| `raft redeploy <app>` | Cutover when the app is already running |
| `raft gate recreate` | After changing published edge ports in settings |
| `raft up` / `raft down` | Bring the whole stack up or tear it down |

## Examples

Copy-paste samples in **[`examples/`](examples/)**: operator settings and scenarios (`http-only-site`, `https-origin-site`, `http-plus-stream`, `host-published-ports`, `grouped-volume-app`).

## Develop

```bash
git clone https://github.com/danielnachumdev/raft.git && cd raft
uv sync --extra dev
uv run pytest
uv run raft -- --help
```

Dashboard UI source lives in **`web/`** (React + Vite). Runtime ships static files only — after FE changes: `cd web && npm ci && npm run build` (writes `src/raft/share/serve/spa/`). Working on the codebase? See **[AGENTS.md](AGENTS.md)**.
