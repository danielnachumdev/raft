# Example consumer app

Minimal service tree for raft: a dummy `Dockerfile` and an App contract at `.raft/app.yaml`.

Replace `publicHost`, `repo`, and `metadata.name` before using this on a real VPS.

## Manual deploy (CLI on the VPS)

1. Install raft (`install.sh`) and put Origin PEMs under `~/.raft/certs/example-app/` if you need HTTPS.
2. Apply from git (raft clones, registers the manifest, syncs, and renders):

```bash
raft apply --git git@github.com:example/consumer-app.git
```

Or, if the tree is already on the host, point at the contract file (and set `spec.source: local` / `spec.path` accordingly):

```bash
raft apply --file /path/to/consumer-app/.raft/app.yaml
```

3. Bring the stack up (first time) or cut over an already-running app:

```bash
raft up
# later updates:
raft redeploy example-app
raft doctor
```

## Automate in CI

Use the same commands from your service repo’s CI after a successful build (SSH to the VPS, or a runner that already has `raft` + Docker access):

```bash
raft apply --git git@github.com:example/consumer-app.git --ref "$GIT_SHA"
# or, when the app is already applied:
raft redeploy example-app --ref "$GIT_SHA"
```

Gate is never redeployed by app CI — only `raft redeploy <app>` (or `router` when needed).
