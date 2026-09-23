# HTTPS Origin site

Same shape as an HTTP site, but `tls: origin` so the gate terminates Cloudflare
Origin TLS for this hostname.

## When to use

- You want HTTPS on the VPS with Origin PEMs (Full / Full Strict at Cloudflare)
- `edge.https` is enabled in `~/.raft/settings.yaml` (default 443)

## Certs

Install PEMs **before** first deploy (apply-with-deploy or `raft up`):

```text
~/.raft/certs/https-origin-site/origin.pem
~/.raft/certs/https-origin-site/origin.key
```

`raft doctor` treats missing certs for `tls: origin` apps as failure.

If PEMs are not ready yet, register only with
`raft apply --file … --no-deploy`, install certs, then apply again **without**
`--no-deploy` (or `raft up`).

## Apply (recommended)

```bash
raft apply --file examples/https-origin-site/.raft/app.yaml
# or: raft apply --git git@github.com:example/https-origin-site.git --ref "$SHA"
raft doctor
```

Deploy is on by default (first boot or cutover). Prefer the same apply command in
CI rather than `--no-deploy` + `redeploy`.
