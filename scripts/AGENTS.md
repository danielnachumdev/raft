# AGENTS.md — scripts/

Small helpers that are **not** part of the `raft` CLI.

## Layout

| Path | Purpose |
|------|---------|
| [setup/](setup/AGENTS.md) | Contributor setup — prerequisites + capa install |
| [release/](release/AGENTS.md) | CD semver + Release wheel bake (`release_semver.py`, `build_release_wheel.sh`) |
| [hosts/](hosts/AGENTS.md) | Temporary local hosts mappings for `publicHost` browser checks |
| [serve_demo/](serve_demo/AGENTS.md) | PII-safe demo data home + Docker-free `raft serve` for SPA screenshots |

## Common commands

```bash
./scripts/setup/setup.sh                 # full: prerequisites + capa install
./scripts/setup/prerequisites.sh         # tooling only
sudo python3 scripts/hosts/hosts.py hold
python3 scripts/serve_demo/seed_home.py /tmp/raft-demo/home
bash scripts/release/build_release_wheel.sh v0.0.0 dist   # CI / local wheel check
```
