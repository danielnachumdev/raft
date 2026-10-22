# AGENTS.md — Agent skills (`agents/skills/`)

Canonical skill **content** lives here. Declare each skill in repo-root **[`capabilities.yaml`](../../capabilities.yaml)** as `type: local`; **[capa](https://capa.sh/)** installs into `.cursor/` / `.claude/` (gitignored).

No project-local skills yet — add a directory with `SKILL.md`, then register it in `capabilities.yaml` and run `./scripts/setup/setup.sh`.
