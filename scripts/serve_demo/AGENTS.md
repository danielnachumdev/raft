# AGENTS.md — scripts/serve_demo

PII-safe demo data home + Docker-free `raft serve` for SPA screenshots (UI PR Proof). Bake the SPA first (`cd src/spa && npm run build`).

```bash
python3 scripts/serve_demo/seed_home.py /tmp/raft-demo/home
RAFT_DATA_HOME=/tmp/raft-demo/home uv run python scripts/serve_demo/serve.py --port 8821 &
scripts/serve_demo/screenshots.sh /tmp/raft-demo/shots light dark   # needs agent-browser
```

`seed_home.py` writes `demo-*` Apps, firewall, alerts, notifications, events, metrics, and an access log. `serve.py` fakes container status so no Docker is required. Never point `RAFT_DATA_HOME` at a real operator home.
