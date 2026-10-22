# Examples

Copy-paste operator settings and App manifests. Hostnames use `*.example.com` only — replace before a real deploy.

These folders are **operator-facing samples**, not the minimal trees under `tests/fixtures/` used by automated tests. Prefer copying from here; do not treat fixture YAML as documentation.

## Pick a scenario

| Path | When |
|------|------|
| [`settings.yaml`](settings.yaml) | Operator settings (`logging`, `edge`, `healing`, `metrics`, `serviceLogs`, `acme`, `github`, `notifications`, `dashboard`, …) → `~/.raft/host/settings.yaml` |
| [`http-only-site/`](http-only-site/) | Single Host-routed HTTP app (`tls: off`); richest field comments + optional `${{ if }}` scaling snippet |
| [`https-acme-site/`](https-acme-site/) | Direct HTTPS via `tls: acme` (Let's Encrypt on the gate; DNS + ports 80/443 + `acme.email`) |
| [`https-origin-site/`](https-origin-site/) | HTTPS via `tls: origin` (Cloudflare Origin PEMs on the host) |
| [`http-plus-stream/`](http-plus-stream/) | HTTP + gate `expose: stream` (needs `edge.streams`) |
| [`host-published-ports/`](host-published-ports/) | HTTP + `expose: host` ports (gate not involved for those) |
| [`grouped-volume-app/`](grouped-volume-app/) | `spec.group` + `volumes` + `envFile` + `expose: none` |
| [`worker-app/`](worker-app/) | Worker App (`ports: []`, `readiness: none`, `tls: off`) |
| [`firewall/rules.yaml`](firewall/rules.yaml) | Ordered edge firewall sample → `raft firewall replace --file …` |
| [`alerts/rules.yaml`](alerts/rules.yaml) | Alert rules sample → `raft alerts apply --file …` (needs notification channels) |

Manifest preprocess (`${VAR}`, `${{ if }}`, `--env` vs durable `spec.envFile`) and name↔source identity live in [`http-only-site/.raft/app.yaml`](http-only-site/.raft/app.yaml) header comments. Secrets modes: [`grouped-volume-app/`](grouped-volume-app/). Healing and per-app scale-to-zero are independent opt-ins — off until you enable `healing:` in settings or add `spec.scaling` on an HTTP + `publicHost` App.

## Try one

1. Copy ideas from [`settings.yaml`](settings.yaml) into `~/.raft/host/settings.yaml`.
2. Pick a folder that matches how you expose the app.
3. TLS prep:
 - `tls: acme` — DNS A/AAAA, ports 80/443, set `acme.email` (no PEMs to paste).
 - `tls: origin` — install `origin.{pem,key}` under `~/.raft/services/<metadata.name>/certs/` **before** deploy.
4. Apply (deploy is **on** by default — first boot or cutover):

```bash
raft apply --file examples/<folder>/.raft/app.yaml --ref "$SHA"
# CI often also passes --env / --env-file
raft doctor
```

Use `--no-deploy` only when you intentionally register without starting (e.g. several apps, then one `raft up`). Do not treat `--no-deploy` + `raft redeploy` as the default path — `redeploy` needs the app service already running.

After changing gate-published ports in settings, run `raft redeploy gate`.
