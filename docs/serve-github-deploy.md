# Serve: add service from GitHub (v1)

From `raft serve` (localhost / SSH tunnel), an admin can add a service via the
Apps **`+`** control → **Add new service** → **Add from GitHub**. Raft opens
GitHub OAuth (required scopes), then the admin picks a repository and raft
drives apply/deploy. After apply, raft opens a PR that adds a GitHub Actions
workflow for push-based `raft apply` when secrets are configured.

Anything raft cannot safely automate (secrets, host volumes, DNS/TLS, deploy-key
paste, CI host secrets) shows in an **Additional steps** panel afterward.

This is **not** a public multi-user console and **not** a full App lifecycle UI.

## UI flow

1. Stack status → **Apps** → **`+`** → `/add-service`.
2. Choose **Add from GitHub** (GitHub icon) → `/deploy`.
3. Visits with **zero** connected accounts **auto-redirect** to
   `/api/github/login` (real OAuth authorize page when configured; mock callback
   only when `github.mock` / `RAFT_GITHUB_MOCK=1`). If expired account rows
   remain, the UI shows an account switcher + re-auth CTA instead of wiping
   them.
4. If OAuth is **not configured**, `/deploy` shows an ordered checklist (create
   OAuth App link + copyable field values) and paste-in controls for
   `clientId` / `clientSecret`. Saving writes `github:` into
   `~/.raft/settings.yaml` and reloads serve’s in-process config (no restart).
5. **Other OAuth failures** redirect to `/deploy?oauth_error=…` with a clear
   error and retry control (not a bare API error page).
6. Search, select one repo, optional ref → confirm → progress steps poll until
   succeeded/failed; **deployment logs** reuse the service logs UI when an app
   name is known.
7. Read **Additional steps** (DNS, TLS, env, volumes, deploy key, merge CI PR).

Deep link `/deploy` still works.

## Developer mock (settings / env only)

Fixture login is **not** offered in the serve UI. For local/CI only:

```yaml
# ~/.raft/settings.yaml
github:
  mock: true
```

Or `RAFT_GITHUB_MOCK=1`. That mints `mock-operator` and lists
`share/serve/mock-github/` fixtures (no GitHub write).

## Real GitHub OAuth App

Do these steps **in order** (default port **8787**; replace `<port>` if you
passed `--port`). The serve UI checklist on `/deploy` shows the same concrete
values for your bind.

1. Open the create form:
   [github.com/settings/applications/new](https://github.com/settings/applications/new)
   (serve builds this link with best-effort `oauth_application[…]` query params;
   GitHub documents URL prefills for **GitHub Apps** only — if fields are empty,
   copy from the steps below).
2. **Application name** = `raft serve`
3. **Homepage URL** = `http://127.0.0.1:<port>/`
4. **Application description** = `Localhost raft serve ops UI — temporary GitHub login to pick a repo and deploy.`
5. **Authorization callback URL** = `http://127.0.0.1:<port>/api/github/callback`
6. **Enable Device Flow** = **off (unset)** — raft uses the browser redirect
   flow, not device codes.
7. **Expire user access tokens** = **off (unset)** (GitHub may label this
   **Expire user authorization tokens**). GitHub enables expiry by default;
   raft keeps a short-lived serve session file and does **not** refresh expiring
   GitHub user tokens yet, so leave this unchecked.
8. Click **Register application**, then configure credentials via **either**:
   - **Serve UI** (recommended when you hit the not-configured state): paste
     Client ID + Client Secret on `/deploy` → Save (writes `github:` and reloads).
   - **settings.yaml / env** as below.

Authorize later requests scopes `read:user repo workflow` (not set on the
create-app form).

```yaml
github:
  mock: false
  clientId: Iv1.example
  clientSecret: ghs_example   # prefer env in real hosts
  sessionTtlSeconds: 3600     # default 1h; min 60
```

Env overrides (preferred for secrets on long-lived hosts):

- `RAFT_GITHUB_CLIENT_ID`
- `RAFT_GITHUB_CLIENT_SECRET`
- `RAFT_GITHUB_SESSION_TTL_SECONDS`
- `RAFT_GITHUB_MOCK`

Note: env overrides win over `settings.yaml`. If `RAFT_GITHUB_*` is set in the
serve process environment, the UI paste path still updates the file, but env
values take precedence until unset.

### Scopes (v1)

| Scope | Why |
|-------|-----|
| `read:user` | Identify the signed-in login |
| `repo` | List private repos; create branch / contents / pull requests |
| `workflow` | Create or update `.github/workflows/*` via the Contents API |

Deploy keys are **not** installed via the GitHub API (no `admin:public_key`).
Raft generates a local deploy key, shows the **public** key + fingerprint, and
asks the operator to paste it on GitHub.

## CI workflow PR

After a successful apply path, raft ensures
`.github/workflows/raft-apply.yml` on a branch `raft/ci-apply` and opens a PR
against the repo default branch when the file is missing.

The workflow SSHes to the raft host and runs:

`raft apply --git <ssh_url> --ref $GITHUB_SHA`

After merge, set repository secrets: `RAFT_SSH_HOST`, `RAFT_SSH_USER`,
`RAFT_SSH_KEY`. If the workflow already exists on the default branch, raft
skips creating a PR and notes that in next steps. CI PR failures do **not**
fail the deploy job; they appear as a failed step + next-step guidance.

## Connected accounts (multi-account)

One OAuth App in settings (`github.clientId` / `clientSecret`). Many GitHub user
identities can be connected; the UI selects the **active** account for repo list
and deploy. Pending OAuth CSRF state is stored separately and must not wipe
existing accounts. Mock mode stays settings/env only (at most one mock account).
Token refresh is not shipped in this version.

## Token storage and retention

| Item | Location | Mode |
|------|----------|------|
| Connected accounts + pending OAuth | `~/.raft/state/serve/github-accounts.json` | `0600` |

- Legacy `github-session.json` migrates to one account on first load, then is deleted.
- Public session JSON never includes `access_token` or client secrets.
- Not written into `generated/`, git, or world-readable dumps.
- Per-account logout removes that row; active falls back to another account when present.
- Serve binds `127.0.0.1` only; treat tunnel access like host admin access.

## API (serve)

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/github/session` | Multi-account public snapshot + active `authenticated`/`login` + hint |
| `GET` | `/api/github/config` | OAuth setup status (no secrets) + callback / docs links |
| `POST` | `/api/github/config` | `{clientId, clientSecret}` → write settings + reload |
| `GET` | `/api/github/login` | Start OAuth or mock callback (add account; preserves others) |
| `GET` | `/api/github/callback` | Finish login → upsert account, set active → `/deploy` |
| `POST` | `/api/github/logout` | Logout **active** account (compat) |
| `POST` | `/api/github/accounts/select` | `{account_id}` → set active |
| `POST` | `/api/github/accounts/{id}/logout` | Logout one account |
| `GET` | `/api/github/repos?q=` | List / search repos (active token) |
| `POST` | `/api/github/deploy` | `{full_name, ref}` → job (apply + CI PR step) |
| `GET` | `/api/github/deploy/{id}` | Poll progress / `ci_pr` / next steps |

Manifest path for v1: **`.raft/app.yaml` only**.

## Invalid App YAML

Bad manifests are **rejected at deploy/apply** with a clear error (job step /
`OperatorError` Fix CTA). They must not cascade-fail the rest of the stack:

- `AppRegistry.load` / `Stack.load_apps` **skip** unreadable or invalid
  `state/apps/*.yaml` files and record them as `registry_issues`.
- `GET /api/status` includes `registry_issues: [{file, error}, …]`.
- Stack status shows an **Invalid App manifests** panel when any issues exist.

Fix or remove the bad file under `~/.raft/state/apps/`, then refresh.
