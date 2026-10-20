# scripts/

Small helpers that are **not** part of the `raft` CLI.

- **`release_semver.py`** — CI helper for label-driven GitHub Releases (see [`docs/releases.md`](../docs/releases.md)).
- **`build_release_wheel.sh`** — bake SPA + build a version-aligned wheel for Release publish (#41).
- **`hosts.py`** — local `Host` routing for browser checks (below).
- **`serve_demo/`** — PII-safe demo data home + Docker-free `raft serve` for SPA screenshots (UI PR Proof):

```bash
python3 scripts/serve_demo/seed_home.py /tmp/raft-demo/home
RAFT_DATA_HOME=/tmp/raft-demo/home uv run python scripts/serve_demo/serve.py --port 8821 &
scripts/serve_demo/screenshots.sh /tmp/raft-demo/shots light dark   # needs agent-browser
```

Bake the SPA first (`cd src/spa && npm run build`). `seed_home.py` writes `demo-*` Apps, firewall, alerts, notifications, events, metrics, and an access log; `serve.py` fakes container status so no Docker is required.

## The problem

raft’s gate routes by `Host`. When you hit `http://127.0.0.1/` on a local machine, the browser sends that hostname — not your app’s `publicHost` — so the router never selects the right upstream.

You can always probe with an explicit header:

```bash
curl -H 'Host: <publicHost>' http://127.0.0.1/
```

Browsers don’t. That’s what `hosts.py` is for.

## What `hosts.py` does

CLI entry is `scripts/hosts.py` (split helpers: `hosts_plan.py`, `hosts_session.py`, `hosts_windows.py`). Reads applied Apps under `~/.raft/services/*/` (or `RAFT_DATA_HOME`), collects each `publicHost` and any `extraHosts`, and temporarily maps them to `127.0.0.1` in the local hosts file(s). On exit — Ctrl+C, signal, or command finish — it **always** restores the previous contents.

Targets:

- Linux: `/etc/hosts`
- Windows (from WSL, when present): `/mnt/c/Windows/System32/drivers/etc/hosts`

If nothing is applied, it errors — apply an App first, or pass `--entry`.

## Try it

```bash
# Hold mappings until Ctrl+C (needs write access / sudo on Linux)
sudo python3 scripts/hosts.py hold

# Patch only for the duration of a command
sudo python3 scripts/hosts.py run -- curl -I https://app.example.test/

# Explicit entries instead of applied apps
sudo python3 scripts/hosts.py --entry 127.0.0.1,app.example.test hold
```

Linux-only or Windows-only:

```bash
sudo python3 scripts/hosts.py --linux-only hold
python3 scripts/hosts.py --windows-only hold
```

## Notes

- Prefer `hold` while clicking around in a browser; use `run` for one-shot probes.
- On WSL, Windows writes may prompt for UAC elevation.
- Exit cleanly so restore runs. Managed markers look like `# >>> raft hosts BEGIN` … `# <<< raft hosts END`.
