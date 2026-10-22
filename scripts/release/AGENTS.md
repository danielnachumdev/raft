# AGENTS.md — scripts/release

CI / CD helpers for GitHub Releases (label-driven semver + wheel bake).

| Script | Purpose |
|--------|---------|
| [release_semver.py](release_semver.py) | Label-driven next tag (`bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`) |
| [build_release_wheel.sh](build_release_wheel.sh) | Bake SPA + build version-aligned wheel; asserts SPA assets in the wheel |

```bash
python3 scripts/release/release_semver.py --latest-tag v0.1.0 --labels-json '["bumpPatch"]'
bash scripts/release/build_release_wheel.sh v0.1.1 dist
```
