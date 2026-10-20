# Releases and semver labels

Operator-facing versions come from **GitHub Releases** (`vX.Y.Z` tags). CI does **not** bot-commit bumps into `pyproject.toml` for day-to-day merges; the CD **semver** job sets the wheel version from the tag when building the artifact.

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

Logic lives in [`scripts/release_semver.py`](../scripts/release_semver.py). Top-level workflows: [`.github/workflows/ci.yml`](../.github/workflows/ci.yml) (validation only) and [`.github/workflows/cd.yml`](../.github/workflows/cd.yml) (label check + **semver**). The **semver** job runs only after **CI** succeeds for a `push` to `main` (`workflow_run` gate) — it cannot create a tag/Release/wheel while tests are still failing. Dry-run via **Actions → CD → Run workflow**. Label checks cancel superseded runs for the same PR; **semver** publish does not cancel in progress so a late label event cannot kill SPA bake / wheel attach. Re-running CI on an already-tagged commit is a no-op (idempotent).

### CI pre-merge vs post-merge

Branch protection requires the aggregate **CI** check. That check is the same job name on PRs and on `main`; the **Unit+Integration** matrix width differs:

| Job / step | Pull request (pre-merge) | Push to `main` (post-merge, gates CD) |
|------------|--------------------------|----------------------------------------|
| Path filter | yes | yes |
| Meta | yes (python paths) | yes (python paths) |
| SPA install / test / build | yes (spa paths) | yes (spa paths) |
| Unit+Integration (bake SPA → unit → integration) | **Py 3.9–3.13** (full) | **Py 3.9 + 3.13** |
| E2E (Py 3.9, after Meta, parallel with Unit) | yes (python paths) | yes (python paths) |
| Aggregate `CI` | yes | yes |
| Release label (`cd.yml`) | yes | n/a |
| semver / Release wheel (`cd.yml`) | no | yes (after CI success) |

Middle Python versions (3.10–3.12) still run every step on the PR before merge; they are not deleted — only kept off `main` so post-merge / CD finish sooner after the thorough pre-merge gate.

## Release bake (SPA + wheel)

On each bump publish (not `noBump`, not dry-run), the **semver** job:

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

Use **`RAFT_REF`** or `--ref` only (`RAFT_BRANCH` is removed). VMs stay **Node-free** on the wheel path. Contributors with an editable checkout still run `npm run build` locally so `raft serve` has UI assets.

After install, `install.sh` prints the resolved source (Release tag + wheel asset, or `git+…@ref`). When replacing an existing install, it also prints `OK: <previous> → <current>` (same shape as `raft update`). Check anytime with `raft --version` (package semver; includes git ref/commit or wheel name when `direct_url.json` is present).

## Upgrade notes (cleanup / breaking removals)

When a release ships deprecation cleanup (see issue #312), operators should:

1. **Backup** `~/.raft/` (especially `settings.yaml`, `host/firewall/`, `services/`, leftover `state/acl/` if present).
2. **Before upgrade** (recommended): open serve **Settings → Firewall** and **Save** once so durable `host/firewall/rules.yaml` exists. Flat ACL migrate-on-load is removed — leftover `acl.gate` / `state/acl/` is ignored.
3. **Upgrade** (`raft update` / install from latest Release wheel). Replace automation using **`RAFT_BRANCH`** with **`RAFT_REF`** / `--ref`.
4. Re-save **Settings** once (drops any leftover `acl:` key from `settings.yaml`). Confirm GitHub assist uses OAuth accounts only (`github-accounts.json`; old `github-session.json` is no longer migrated — re-login if needed).
5. Trends: only `raft-serve-trends-dashboards` is read; clear stale `raft-serve-trends-views` localStorage if desired.
6. Run **`raft doctor`** / **`raft status`**; prefer gate **reload** unless published edge ports changed (`raft gate recreate`).

## Merge enforcement

PRs into `main` must pass the **Release label** check (exactly one of `bumpMajor` / `bumpMinor` / `bumpPatch` / `noBump`). A repository ruleset requires that status check before merge so unlabeled PRs cannot land silently.
