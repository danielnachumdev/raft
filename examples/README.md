# Examples

Copy-paste samples for operator settings and App manifests. Hostnames use
`*.example.com` only — replace before deploying.

| Path | Scenario |
|------|----------|
| [`settings.yaml`](settings.yaml) | Operator settings (`logging` + `edge` + optional `healing`) → `~/.raft/settings.yaml` |
| [`http-only-site/`](http-only-site/) | TLS off, single `expose: http` port (richest field comments, including `spec.resources` → Compose `deploy.resources`) |
| [`https-origin-site/`](https-origin-site/) | `tls: origin` + Origin PEM notes |
| [`http-plus-stream/`](http-plus-stream/) | HTTP + `expose: stream` (needs `edge.streams`) |
| [`host-published-ports/`](host-published-ports/) | HTTP + `expose: host` mail-shaped ports |
| [`grouped-volume-app/`](grouped-volume-app/) | `spec.group` + `volumes` + `expose: none` (manifest-only sample) |

`raft-controller` always runs with the stack; self-heal stays **off** until you uncomment/enable `healing:` in settings (Phase 1: one Compose restart, then one cutover/redeploy; apps only).

Each service folder has `.raft/app.yaml`; most also have a short `README.md` and a `Dockerfile`
when the sample builds on the VPS.

## Quick start

1. Copy [`settings.yaml`](settings.yaml) ideas into `~/.raft/settings.yaml`.
2. Pick a service folder that matches your exposure model.
3. For `tls: origin`, install PEMs under `~/.raft/certs/<metadata.name>/` **before** deploy.
4. `raft apply --file examples/<folder>/.raft/app.yaml` (or `--git` from a real repo) — **deploy is on by default** (first boot or cutover). Pass `--ref` / `--env` in CI the same way.
5. `raft doctor`.

Do not treat `--no-deploy` + `raft redeploy` as the default: `redeploy` needs the app service already running. Use `--no-deploy` only to register without starting (e.g. several apps, then one `raft up`).

After changing gate-published ports in settings, run `raft gate recreate`.
