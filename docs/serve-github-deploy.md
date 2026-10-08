# Serve: temporary GitHub deploy assist (v1)

From `raft serve` (localhost / SSH tunnel), an admin can **temporarily** sign in
with GitHub, pick one repository, and let raft drive apply/deploy. Anything raft
cannot safely automate (secrets, host volumes, DNS/TLS, deploy-key paste) shows
in an **Additional steps** panel afterward.

This is **not** a public multi-user console and **not** a full App lifecycle UI.

## Mock mode (local / screenshots / CI)

No GitHub App registration required:

```yaml
# ~/.raft/settings.yaml
github:
  mock: true
```

Or:

```bash
export RAFT_GITHUB_MOCK=1
raft serve
```

Mock login creates a short-lived session as `mock-operator` and lists fixture
repos shipped under `share/serve/mock-github/` (`demo/http-only-site` has a
valid `.raft/app.yaml`; `demo/no-manifest` demonstrates the missing-manifest
error).

## Real GitHub OAuth App

1. Create an OAuth App on GitHub (Developer settings).
2. **Authorization callback URL:** `http://127.0.0.1:<port>/api/github/callback`
   (default port **8787**).
3. Configure:

```yaml
github:
  mock: false
  clientId: Iv1.example
  clientSecret: ghs_example   # prefer env in real hosts
  sessionTtlSeconds: 3600     # default 1h; min 60
```

Env overrides (preferred for secrets):

- `RAFT_GITHUB_CLIENT_ID`
- `RAFT_GITHUB_CLIENT_SECRET`
- `RAFT_GITHUB_SESSION_TTL_SECONDS`
- `RAFT_GITHUB_MOCK`

### Scopes (v1)

| Scope | Why |
|-------|-----|
| `read:user` | Identify the signed-in login |
| `repo` | List private repositories the identity can access |

Deploy keys are **not** installed via the GitHub API in v1 (no
`admin:public_key`). Raft generates a local deploy key, shows the **public**
key + fingerprint in the UI, and asks the operator to paste it on GitHub.

## Token storage and retention

| Item | Location | Mode |
|------|----------|------|
| OAuth / mock access token | `~/.raft/state/serve/github-session.json` | `0600` |

- Not written into `generated/`, git, or world-readable dumps.
- Cleared on **Log out**, process expiry (`sessionTtlSeconds`), or corrupt file.
- Serve binds `127.0.0.1` only; treat tunnel access like host admin access.

## API (serve)

| Method | Path | Role |
|--------|------|------|
| `GET` | `/api/github/session` | Auth status + hint |
| `GET` | `/api/github/login` | Start OAuth or mock callback |
| `GET` | `/api/github/callback` | Finish login → redirect `/deploy` |
| `POST` | `/api/github/logout` | Clear session file |
| `GET` | `/api/github/repos?q=` | List / search repos |
| `POST` | `/api/github/deploy` | `{full_name, ref}` → job |
| `GET` | `/api/github/deploy/{id}` | Poll progress / next steps |

Manifest path for v1: **`.raft/app.yaml` only**.

## UI flow

1. Open `http://127.0.0.1:8787/deploy` (or **Deploy from GitHub** on the dashboard).
2. Sign in (mock or real).
3. Search, select exactly one repo, optional ref override (default branch).
4. Confirm → progress steps poll until succeeded/failed.
5. Read **Additional steps** (DNS, TLS, env file, volumes, deploy key).
