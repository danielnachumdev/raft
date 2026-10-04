# Host-published ports

HTTP (via the router) plus mail-shaped ports with `expose: host` so the container publishes them on the host directly — the gate is not involved for those ports. Useful when client IP accuracy matters.

## When to use

- SMTP / submission / IMAPS (or similar) on the host network path
- Optional HTTPS for an admin UI via `tls: origin`

Host-exposed ports do **not** need `edge.streams`. Only gate-published listeners belong in settings.

## Certs

This sample uses `tls: origin`. Install PEMs **before** first deploy, or set `tls: off` in the manifest:

```text
~/.raft/certs/host-published-ports/origin.pem
~/.raft/certs/host-published-ports/origin.key
```

## Apply

```bash
raft apply --file examples/host-published-ports/.raft/app.yaml --ref "$SHA"
raft doctor
```

Deploy is on by default. After changing gate-published `edge:` ports (not host-exposed ones), run `raft gate recreate`.
