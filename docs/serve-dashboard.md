# Always-on dashboard (`raft-dashboard`)

Optional first-party Compose service that hosts the same ops UI as `raft serve`,
without a long-lived SSH-held Python process.

Not an App YAML in operator repos. Controlled from `~/.raft/host/settings.yaml`
under `dashboard:` and the CLI `raft dashboard …`.

## Defaults (safe)

```yaml
dashboard:
  enabled: false
  port: 8787
  auth:
    mode: none
```

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

```bash
raft dashboard set-password
raft dashboard enable --public-host=ops.example.com --tls=acme --auth-mode=password
```

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

```bash
raft dashboard oauth init --provider=google
# fill client id/secret in the printed env path; redirect URL is printed
# add allowlist lines (example identity only in docs):
printf '%s\n' 'ops@example.com' > /tmp/dashboard-allowlist.txt
raft dashboard oauth allowlist-set --file=/tmp/dashboard-allowlist.txt
# or: echo ops@example.com | raft dashboard oauth allowlist-add
raft dashboard enable --public-host=ops.example.com --tls=acme --auth-mode=oauth
```

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

## CLI

```bash
raft dashboard status
raft dashboard enable
raft dashboard disable
raft dashboard set-password
raft dashboard oauth init
raft dashboard oauth allowlist-set --file=…
raft dashboard oauth allowlist-add
```

`enable` persists settings, runs `raft render` (which reloads gate/router nginx
when generated edge fragments changed), `compose up` for `raft-dashboard`, then
reloads the router and gate again so Compose DNS for the new service (and
gate→router) is fresh. A brief public 502/offline window during that join is
expected; if it persists, `raft render` then `raft doctor`. `disable` stops the
service and clears `enabled`.

When enabled, `raft doctor` lists `dashboard` under the `raft` group with the
other control-plane members (gate / router / controller).

## Version badge

The SPA top bar shows the same install identity as `raft version` on the host.
Template sync stamps that identity into `~/.raft/dashboard/raft/` (and the
controller build context) before Compose builds the image, because the
container loads raft via `PYTHONPATH` without wheel dist-info. After
`raft update`, re-enable or recreate the dashboard so the image rebuilds with
the new stamp.

## Settings → Update raft

Check-for-updates works in the dashboard (GitHub Release vs stamped version).
**Update** reinstalls the **host** uv-tool `raft` CLI (same `install.sh` /
Release wheel path as `raft update`) via a one-shot container: Compose injects
`RAFT_HOST_HOME`, the dashboard mounts host `~/.local` read-only for identity
checks, and apply uses `docker.sock` with `buildpack-deps:bookworm-scm`
(`curl`+`bash`+`git`; not the dashboard image). Nginx allows up to 600s for
`/api/update` (image pull + install). After a successful update, recreate the
dashboard so the image rebuilds with the new install stamp:

```bash
raft dashboard disable
raft dashboard enable
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
