# HTTPS Origin site

Same shape as an HTTP site, but `tls: origin` so the gate terminates Cloudflare
Origin TLS for this hostname.

## When to use

- You want HTTPS on the VPS with Origin PEMs (Full / Full Strict at Cloudflare)
- `edge.https` is enabled in `~/.raft/settings.yaml` (default 443)

## Certs

Before `raft up` or any gate recreate:

```text
~/.raft/certs/https-origin-site/origin.pem
~/.raft/certs/https-origin-site/origin.key
```

`raft doctor` treats missing certs for `tls: origin` apps as failure.

## Apply

```bash
raft apply --file examples/https-origin-site/.raft/app.yaml
# or: raft apply --git git@github.com:example/https-origin-site.git
raft up
raft doctor
```
