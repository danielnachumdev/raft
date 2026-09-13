# Examples

Copy-paste samples for operator settings and App manifests. Hostnames use
`*.example.com` only — replace before deploying.

| Path | Scenario |
|------|----------|
| [`settings.yaml`](settings.yaml) | Operator settings (`logging` + `edge`) → `~/.raft/settings.yaml` |
| [`http-only-site/`](http-only-site/) | TLS off, single `expose: http` port (richest field comments) |
| [`https-origin-site/`](https-origin-site/) | `tls: origin` + Origin PEM notes |
| [`http-plus-stream/`](http-plus-stream/) | HTTP + `expose: stream` (needs `edge.streams`) |
| [`host-published-ports/`](host-published-ports/) | HTTP + `expose: host` mail-shaped ports |

Each service folder has `.raft/app.yaml`, a short `README.md`, and a `Dockerfile`
when the sample builds on the VPS.

## Quick start

1. Copy [`settings.yaml`](settings.yaml) ideas into `~/.raft/settings.yaml`.
2. Pick a service folder that matches your exposure model.
3. `raft apply --file examples/<folder>/.raft/app.yaml` (or `--git` from a real repo).
4. For `tls: origin`, install PEMs under `~/.raft/certs/<metadata.name>/`.
5. `raft up` then `raft doctor`.

After changing gate-published ports in settings, run `raft gate recreate`.
