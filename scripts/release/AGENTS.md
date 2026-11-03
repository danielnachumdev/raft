# AGENTS.md — scripts/release

Raft-specific Release wheel bake (SPA → version-aligned `.whl`).

Label-driven semver / GitHub Release publish lives in
`danielnachumdev/actions` (`semver-ci` / `semver-cd`); raft’s thin
`.github/workflows/semver.yml` + `cd.yml` call those. This folder only
keeps the bake script that CD passes as `build-command`.

| Script | Purpose |
|--------|---------|
| [build_release_wheel.sh](build_release_wheel.sh) | Bake SPA + build version-aligned wheel; asserts SPA assets in the wheel |

```bash
bash scripts/release/build_release_wheel.sh v0.1.1 dist
```
