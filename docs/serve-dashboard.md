# Always-on dashboard (`raft-dashboard`)

Optional first-party Compose service that hosts the same ops UI as `raft serve`,
without a long-lived SSH-held Python process.

Not an App YAML in operator repos. Controlled from `~/.raft/settings.yaml`
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
    mode: password   # password | external (required when publicHost is set)
```

Rules:

- `auth.mode: none` cannot set `publicHost`.
- `publicHost` requires `auth.mode` `password` or `external`, and `tls` set.
- Origin PEMs: `~/.raft/certs/raft-dashboard/origin.{pem,key}`.
- ACME uses the same HTTP-01 path as Apps; synthetic target name
  `raft-dashboard` (set `acme.email`).
- Firewall service id is `raft-dashboard` when `publicHost` is set.

Gate / router treat the dashboard like any other Host → upstream (TLS on the
gate when configured). **Authentication is an implementation detail inside the
dashboard container**: its image runs nginx in front of the SPA process and only
proxies after password or external auth succeeds — unauthenticated clients never
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
```

`enable` persists settings, runs `raft render` (which reloads gate/router nginx
when generated edge fragments changed), `compose up` for `raft-dashboard`, then
reloads the router again so the new Compose DNS name is picked up. `disable`
stops the service and clears `enabled`.

## Relationship to `raft serve`

`raft serve` remains a foreground localhost helper (useful for development).
When the always-on service is up, `raft serve` also prints its local/public URLs
when starting. Prefer the always-on service for day-to-day visibility.

## See also

- [`examples/settings.yaml`](../examples/settings.yaml) — commented `dashboard:` block
- [`docs/serve-firewall.md`](serve-firewall.md) — service scope `raft-dashboard`
