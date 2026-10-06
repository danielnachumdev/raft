# HTTPS ACME site

Direct public HTTPS on the gate via `tls: acme` (Let's Encrypt HTTP-01). The App stays HTTP to the router; the **gate** answers challenges and terminates TLS.

## When to use

- Browser (or any client) hits the VPS on :443 — no Cloudflare Origin / upstream TLS proxy
- You want raft to issue and renew certs (no PEMs to paste)

For Cloudflare Origin PEMs, use [`../https-origin-site/`](../https-origin-site/) (`tls: origin`) instead.

## Checklist

1. DNS A/AAAA for `publicHost` (and every `extraHosts` name) → this VPS
2. TCP **80** and **443** reachable (keep `edge.http` / `edge.https` in settings)
3. Uncomment / set `acme.email` in `~/.raft/settings.yaml` (see [`../settings.yaml`](../settings.yaml))
4. Optional labs: set `acme.directory` to Let's Encrypt **staging**
5. Apply, then `raft doctor` / `raft doctor https-acme-site`

Renewal is the controller (`acme:<name>` jobs). Gate reloads nginx only — never `raft gate recreate` for cert rotation.

**Not shipped:** DNS-01 / wildcards. If port 80 cannot be opened, use `tls: origin` behind a proxy or terminate TLS elsewhere.

## Apply

```bash
# settings: acme.email + edge.http/https (defaults 80/443)
raft apply --file examples/https-acme-site/.raft/app.yaml --ref "$SHA"
raft doctor https-acme-site
```

Issuance is best-effort after the gate is up — apply does not fail if ACME is slow; doctor reports cert health / `lastError`.
