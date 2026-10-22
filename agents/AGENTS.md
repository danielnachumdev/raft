# AGENTS.md — agents/

**Audience:** Contributors and automation authoring agent skills and Cursor rules.

Agent configuration is managed by **[capa](https://capa.sh/)** from the repo-root **[`capabilities.yaml`](../capabilities.yaml)**. Do **not** hand-edit `.cursor/` or `.claude/` provider dirs — `capa install` regenerates them.

| Path | Purpose |
|------|---------|
| [skills/](skills/) | Skill source trees (`SKILL.md`, scripts) — declare as `type: local` in `capabilities.yaml` |
| [rules/](rules/) | Cursor rule sources (`.mdc`) — declare as `type: local` in `capabilities.yaml` |

## Workflow

1. Add or edit skill/rule **content** under `agents/skills/` or `agents/rules/`.
2. Declare the entry in **`capabilities.yaml`**.
3. Run **`./scripts/setup/setup.sh`**.
4. Restart the coding agent so skills/rules reload.

Product guidance for raft itself stays in root [`AGENTS.md`](../AGENTS.md) — capa does not replace it.
