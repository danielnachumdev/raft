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

## Install / update and `latest`

`install.sh` and `raft update` install from the **latest GitHub Release tag** by default (`uv tool install git+…@vX.Y.Z`). Override with an explicit ref:

```bash
curl -fsSL …/install.sh | bash -s -- --ref main
RAFT_REF=main bash install.sh
raft update --ref main
```

`RAFT_BRANCH` remains a deprecated alias for `RAFT_REF`. Local checkouts / `RAFT_KEEP_CHECKOUT=1` still editable-install from disk (ref only affects clone mode).

After #41 attaches wheel (+ baked SPA) assets to each Release:

1. Prefer the **latest** Release wheel asset.
2. Keep **git@tag** (then `--ref`) as fallback when no asset exists.

## Merge enforcement

PRs into `main` must pass the **Release label** check (exactly one of `bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`). A repository ruleset requires that status check before merge so unlabeled PRs cannot land silently.
