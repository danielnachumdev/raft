# Releases and semver labels

Operator-facing versions come from **GitHub Releases** (`vX.Y.Z` tags). CI does **not** bot-commit bumps into `pyproject.toml` (that file stays a packaging placeholder until wheel install from release assets lands with SPA bake — [#41](https://github.com/danielnachumdev/raft/issues/41)).

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

## Install / update and `latest` (forward path)

Today `install.sh` / `raft update` still use `uv tool install git+…@main` (unchanged). After #41 attaches real wheel (and baked SPA) assets to each Release:

1. Prefer the **latest** GitHub Release asset (e.g. `gh release download -R … -p '*.whl'`).
2. Keep a **git fallback** when no Release asset exists (dev checkouts, broken publish, first boot).

Until then, do not gate install on Releases — tags/notes alone are enough for the semver pipeline.

## Merge enforcement

PRs into `main` must pass the **Release label** check (exactly one of `bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`). A repository ruleset requires that status check before merge so unlabeled PRs cannot land silently.
