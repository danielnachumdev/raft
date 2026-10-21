# Always-on dashboard (`raft-dashboard`)

Optional first-party Compose service that hosts the same ops UI as `raft serve`,
without a long-lived SSH-held Python process.

Not an App YAML in operator repos. Config lives only under
`~/.raft/host/settings.yaml` `dashboard:` (Settings UI / `PUT /api/settings`).
Lifecycle is the same as other services: **Start / Stop / Redeploy**
(`raft start|stop|redeploy dashboard` or the serve UI). Saving settings alone
does not start or stop the container.

## Defaults (safe)

```yaml
dashboard:
  enabled: false
  port: 8787
  auth:
    mode: none
```

When `enabled: true`, render / `raft up` include `raft-dashboard` in Compose.
When `false`, it is omitted. Bring a running container up with Start or Redeploy
after enable + `raft render`. Redeploy while disabled refuses (enable in Settings
first — no silent enable).

When enabled, Compose publishes **localhost only**:
`127.0.0.1:<port>:<port>`. Tunnel with SSH the same way as `raft serve`.

## Public Host (optional)

```yaml
dashboard:
  enabled: true
  port: 8787
  publicHost: ops.example.com
  tls: acme          # off | origin | acme
  auth:
    mode: password   # password | oauth | external (required when publicHost is set)
```

Rules:

- `auth.mode: none` cannot set `publicHost`.
- `publicHost` requires `auth.mode` `password`, `oauth`, or `external`, and `tls` set.
- Origin PEMs: `~/.raft/services/raft-dashboard/certs/origin.{pem,key}`.
- ACME uses the same HTTP-01 path as Apps; synthetic target name
  `raft-dashboard` (set `acme.email`).
- Firewall service id is `raft-dashboard` when `publicHost` is set.

Gate / router treat the dashboard like any other Host → upstream (TLS on the
gate when configured). **Authentication is an implementation detail inside the
dashboard container**: the image entrypoint starts the app on loopback, waits
until it listens, then runs nginx with `auth_request` in front. Unauthenticated
clients get a relative sign-in redirect (`absolute_redirect off`) and never
receive SPA bytes.

### Password auth

In Settings → Dashboard, set `auth.mode: password` and enter a plaintext password
in the password-hash field (≥8 characters); Save hashes it
(`pbkdf2_sha256$…`). Leave the redaction mask (`***`) to keep the stored hash.
Then enable, `raft render`, and Start or Redeploy.

In-container nginx uses `auth_request` against `/api/dashboard/auth`. Browsers
without a session cookie get `/login` (static HTML in the image). Login posts to
`/api/dashboard/login`; a signed session cookie (PBKDF2 hash in settings) unlocks
the SPA. Mutative API calls need the CSRF cookie value in `X-CSRF-Token`.
The SPA top bar shows **Log out** (clears the session and returns to `/login`).

### OAuth auth (provider catalog)

First-party OAuth edge via **oauth2-proxy** in the dashboard image. Provider is
a catalog field under `auth.oauth` — not a separate mode per IdP.

```yaml
dashboard:
  enabled: true
  publicHost: ops.example.com
  tls: acme
  auth:
    mode: oauth
    identityHeader: X-Raft-Identity
    oauth:
      provider: google   # google | oidc
      # oidc also needs: issuerUrl: https://login.example.com/
      redirectPath: /oauth2/callback
      allowlistFile: host/secrets/dashboard/oauth-allowlist.txt
```

Secrets stay under the data home (never in git / PR bodies):

| File | Role |
|------|------|
| `~/.raft/host/secrets/dashboard/oauth.env` | `OAUTH2_PROXY_CLIENT_ID`, `CLIENT_SECRET`, `COOKIE_SECRET`, `REDIRECT_URL` (0600) |
| `~/.raft/host/secrets/dashboard/oauth-allowlist.txt` | One allowed identity per line |

Create the env file and allowlist under `host/secrets/dashboard/`, set
`auth.mode: oauth` + `enabled: true` in Settings, then `raft render` and Start
or Redeploy. Redirect URL is typically
`https://<publicHost>/oauth2/callback`.

Runtime shape:

- nginx `auth_request` → oauth2-proxy `/oauth2/auth`
- unauthenticated → relative `302 /oauth2/start?rd=…`
- identity not on allowlist → `/unauthorized` (static HTML in the image)
- SPA **Log out** → `/oauth2/sign_out?rd=/`

`provider: oidc` uses the same binary with `issuerUrl` plus the same env secrets
and allowlist. Operators who already run Authentik / Cloudflare Access / custom
verify should use **`external`** instead (below) — fully open, zero catalog
coupling.

### External auth (BYO)

In-container nginx uses `auth_request` to your `verifyUrl`. On success, the
identity header is forwarded to the dashboard process, which requires that
header. Unauthenticated clients are redirected to `signInUrl`.

```yaml
dashboard:
  enabled: true
  publicHost: ops.example.com
  tls: acme
  auth:
    mode: external
    verifyUrl: http://auth.demo.example/verify
    signInUrl: https://auth.demo.example/sign-in
    identityHeader: X-Raft-Identity
```

## Lifecycle

```bash
# After enabling in Settings:
raft render
raft start dashboard          # Compose up --no-build (Restart = stop→start)
raft stop dashboard
raft redeploy dashboard       # rebuild image (picks up host install stamp)
```

`enabled: true` only includes the service in render / `raft up`. Start and
Redeploy do **not** mutate `dashboard:` settings or secrets. Redeploy while
`enabled: false` refuses with a CTA to enable in Settings.

When enabled, `raft doctor` lists `dashboard` under the `raft` group with the
other control-plane members (gate / router / controller).

### UI self-Redeploy (always-on dashboard)

Redeploy from inside `raft-dashboard` cannot rebuild in-process: the API runs
in the container being rebuilt. Serve detects the dashboard container
(`RAFT_DASHBOARD_APP_PORT`), enqueues a **detached host Docker one-shot**
(`docker run -d` → host `raft redeploy dashboard` with `HOME` + `docker.sock`),
and returns **202** `{ started: true, job_id }` immediately. The SPA shows
“Redeploying…”, polls until the service is healthy again, then soft-reloads
with a success toast. On timeout it points at Events / host CLI. Host
`raft serve` and CLI Redeploy stay **in-process** (sync). Restart remains
`--no-build` (stop→start).

Shared runner: `HostOneshot` under `platform/adapters/docker/` (also used by
Settings → Update). Preflight refuses clearly when `RAFT_HOST_HOME`, the
Docker socket, or the `docker` CLI is missing.

### Version badge

The SPA top bar shows the same install identity as `raft version` on the host.
Template sync stamps that identity into `~/.raft/dashboard/raft/` (and the
controller build context) before Compose builds the image, because the
container loads raft via `PYTHONPATH` without wheel dist-info. After
`raft update`, **Redeploy** the dashboard so the image rebuilds with the new
stamp — do not flip `dashboard.enabled` off and on.

## Settings → Update raft

Check-for-updates works in the dashboard (GitHub Release vs stamped version).
**Update** reinstalls the **host** uv-tool `raft` CLI (same `install.sh` /
Release wheel path as `raft update`) via the shared host one-shot
(`HostOneshot.run`, sync wait, no docker.sock inside the install container):
Compose injects `RAFT_HOST_HOME`, the dashboard mounts host `~/.local`
read-only for identity checks, and apply uses `docker.sock` on the dashboard
to launch `buildpack-deps:bookworm-scm` (`curl`+`bash`+`git`). Nginx allows
up to 600s for `/api/update` (image pull + install). After a successful
update, Redeploy the dashboard so the image rebuilds with the new install
stamp:

```bash
raft redeploy dashboard
raft doctor
```

See [`docs/serve-settings.md`](serve-settings.md).

## Relationship to `raft serve`

`raft serve` remains a foreground localhost helper (useful for development).
When the always-on service is up, `raft serve` also prints its local/public URLs
when starting. Prefer the always-on service for day-to-day visibility.

## See also

- [`examples/settings.yaml`](../examples/settings.yaml) — commented `dashboard:` block
- [`docs/serve-firewall.md`](serve-firewall.md) — service scope `raft-dashboard`
