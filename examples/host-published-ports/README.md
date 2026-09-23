# Host-published ports (mail-shaped)

HTTP admin UI via the router, plus mail ports with `expose: host` so the
container publishes them on the VPS directly (gate not involved). Good when
client IP accuracy matters.

## When to use

- SMTP / submission / IMAPS (or similar) on the host network path
- Optional HTTPS for the admin UI via `tls: origin`

Host ports do **not** need `edge.streams`. Only gate-published listeners belong
in settings.

## Certs (because this sample uses `tls: origin`)

```text
~/.raft/certs/host-published-ports/origin.pem
~/.raft/certs/host-published-ports/origin.key
```

Install PEMs **before** first deploy. Set `tls: off` in the manifest if you skip PEMs.

## Apply (recommended)

```bash
raft apply --file examples/host-published-ports/.raft/app.yaml
# CI: raft apply --file .raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default (first boot or cutover). Prefer that over
`--no-deploy` + `redeploy` for new apps.

After changing `edge:` published ports (not host-exposed ones), run
`raft gate recreate`.
