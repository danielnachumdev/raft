# Serve GitHub deploy UI screenshots (issue #145)

Captured against local `raft serve` with `github.mock: true` / `RAFT_GITHUB_MOCK=1`
and Docker Compose (isolated `RAFT_DATA_HOME`).

| File | Step |
|------|------|
| `01-login.png` | Temporary GitHub login (mock CTA + scopes copy) |
| `02-signed-in-repos.png` | Signed in as `mock-operator`; fixture repos listed |
| `03-repo-selected.png` | Selected `demo/http-only-site` + ref |
| `04-deploy-started.png` | Deploy progress panel after confirm |
| `05-deploy-result.png` | Full page: **Status: succeeded** + Additional steps |
| `06-next-steps.png` | Same full-page capture (DNS next step visible) |
| `07-missing-manifest.png` | Clear failure when `.raft/app.yaml` is missing |

No OAuth tokens, client secrets, or private keys appear in these images.
