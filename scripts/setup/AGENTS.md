# AGENTS.md — scripts/setup

Contributor bootstrap for raft tooling and agent capabilities.

| Script | Purpose |
|--------|---------|
| [setup.sh](setup.sh) | Full setup: runs prerequisites, then `capa install` from `capabilities.yaml` |
| [prerequisites.sh](prerequisites.sh) | Install/verify `gh`, `uv`, Node/npm, `agent-browser`, `capa`; verify `docker` |

```bash
./scripts/setup/setup.sh
./scripts/setup/prerequisites.sh
```

Optional env: **`NODE_VERSION`**, **`NO_COLOR`**, **`CAPA_INSTALL_ARGS`** (extra flags for `capa install`, e.g. `-e`).

Do not hand-edit generated `.cursor/` / `.claude/` provider files — edit `capabilities.yaml` and re-run setup.
