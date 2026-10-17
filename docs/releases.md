# Releases and semver labels

Operator-facing versions come from **GitHub Releases** (`vX.Y.Z` tags). CI does **not** bot-commit bumps into `pyproject.toml` for day-to-day merges; the Release publish job sets the wheel version from the tag when building the artifact.

## Labels (exact names)

Every PR into `main` must carry **exactly one** of:

| Label | Effect on merge to `main` |
|-------|---------------------------|
| `bumpMajor` | Create Release `v(X+1).0.0` |
| `bumpMinor` | Create Release `vX.(Y+1).0` |
| `bumpPatch` | Create Release `vX.Y.(Z+1)` |
| `noBump` | No Release / no tag |

- **Missing label:** the `Release label` check fails (no silent patch default).
- **Multiple labels:** fail closed with a clear error.
- **Base version:** latest GitHub Release tag; if none exist yet, treat as `0.0.0`.

Logic lives in [`scripts/release_semver.py`](../scripts/release_semver.py); workflow: [`.github/workflows/release.yml`](../.github/workflows/release.yml). Dry-run via **Actions → Release → Run workflow**.

## Release bake (SPA + wheel)

On each bump publish (not `noBump`, not dry-run), the Release job:

1. Runs `cd src/spa && npm ci && npm run build` into `src/raft/core/platform/share/serve/spa/` (transient; **not** committed).
2. Sets `pyproject.toml` `version` to the Release semver (tag without `v`).
3. Builds a wheel via [`scripts/build_release_wheel.sh`](../scripts/build_release_wheel.sh) and **fails the job** if bake/build fails or the wheel lacks SPA assets.
4. Creates the GitHub Release and attaches the `.whl` (no JSON placeholder).

Hashed SPA files under `share/serve/spa/` stay **out of git** (`.gitkeep` + `.gitignore` only). FE PRs change `src/spa/` only.

## Install / update

`install.sh` and `raft update` (which re-runs `install.sh`):

1. Resolve the **latest** GitHub Release tag (or `--ref` / `RAFT_REF`).
2. Prefer the Release **wheel** asset when present (`uv tool install <wheel-url>`).
3. Fall back to `git+…@tag` (and keep local checkout / `RAFT_KEEP_CHECKOUT` editable paths).

```bash
curl -fsSL …/install.sh | bash
curl -fsSL …/install.sh | bash -s -- --ref main
RAFT_REF=v0.11.0 bash install.sh
RAFT_PREFER_WHEEL=0 bash install.sh   # force git+ even when a wheel exists
raft update --ref main
```

`RAFT_BRANCH` remains a deprecated alias for `RAFT_REF`. VMs stay **Node-free** on the wheel path. Contributors with an editable checkout still run `npm run build` locally so `raft serve` has UI assets.

After install, `install.sh` prints the resolved source (Release tag + wheel asset, or `git+…@ref`). When replacing an existing install, it also prints `PREVIOUS → CURRENT` version lines (same shape as `raft update`). Check anytime with `raft --version` (package semver; includes git ref/commit or wheel name when `direct_url.json` is present).

## Merge enforcement

PRs into `main` must pass the **Release label** check (exactly one of `bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`). A repository ruleset requires that status check before merge so unlabeled PRs cannot land silently.
