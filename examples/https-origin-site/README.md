# HTTPS Origin site

Same shape as the HTTP-only sample, but `tls: origin` so the gate terminates HTTPS using **operator-installed Origin PEMs** (typical behind Cloudflare Full / Origin CA).

## When to use

- An upstream proxy presents the browser-trusted cert; the gate only needs Origin material
- `edge.https` is enabled in `~/.raft/settings.yaml` (default 443)

For **direct** browser → VPS HTTPS (Let's Encrypt on the gate), use [`../https-acme-site/`](../https-acme-site/) (`tls: acme`) instead — that path does **not** use `origin.*` PEMs.

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
