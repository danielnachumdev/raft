# HTTPS Origin site

Same shape as the HTTP-only sample, but `tls: origin` so the gate terminates HTTPS for this hostname using Origin PEMs on the host.

## When to use

- You want HTTPS on the VPS with Origin certificates
- `edge.https` is enabled in `~/.raft/settings.yaml` (default 443)

## Certs

Install PEMs **before** first deploy:

```text
~/.raft/certs/https-origin-site/origin.pem
~/.raft/certs/https-origin-site/origin.key
```

`raft doctor` fails `tls: origin` apps when these are missing. If PEMs are not ready yet: `raft apply … --no-deploy`, install certs, then apply again without `--no-deploy` (or `raft up`).

## Apply

```bash
raft apply --file examples/https-origin-site/.raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default. Prefer the same apply command in CI rather than `--no-deploy` + `redeploy`.
